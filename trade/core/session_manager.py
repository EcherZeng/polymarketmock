"""Session manager — dual-slot orchestrator for continuous BTC 15-minute trading.

Manages the lifecycle: discover → prepare → active → closing → settled,
with seamless handoff between consecutive sessions.

Integrates BTC two-window sita mechanism:
- After window_2 time elapses, computes BTC trend from Binance klines
- Feeds trend result to strategy (gatekeeper for entry)
- Supports composite strategy: selects branch config by BTC amplitude
"""

from __future__ import annotations

import asyncio
import logging
import time
from datetime import datetime, timezone

from config import settings
from core.base_executor import BaseExecutor
from core.btc_trend import compute_session_btc_trend
from core.data_store import DataStore
from core.live_hub import LiveHub
from core.market_scanner import MarketScanner
from core.orderbook_builder import OrderbookBuilder
from core.position_tracker import PositionTracker
from core.settlement_tracker import SettlementTracker
from core.strategy_engine import CompositeConfig, get_strategy
from core.types import (
    ErrorAction,
    LiveFill,
    LiveMarketContext,
    LiveSignal,
    SessionInfo,
    SessionResult,
    SessionState,
    TradeError,
    slug_to_iso,
)
from core.ws_client import PolymarketWSClient
from strategies.base_live import BaseLiveStrategy

logger = logging.getLogger(__name__)


class SessionSlot:
    """State for one trading session."""

    def __init__(self, session: SessionInfo) -> None:
        self.session = session
        self.state = SessionState.DISCOVERED
        self.strategy: BaseLiveStrategy | None = None
        self.ob = OrderbookBuilder()
        self.trades: list[LiveFill] = []
        self.error: str = ""
        # Per-session BTC price history (recorded during ACTIVE window)
        self.btc_history: list[dict] = []
        # BTC trend computation state
        self.btc_trend_computed = False
        self.btc_trend_info: dict = {}
        self.matched_branch: str | None = None
        # Whether the session ended without any trades
        self.no_trades = False
        # Per-session Poly Up/Down price history (recorded during ACTIVE window)
        # token_id → list of {mid, bid, ask, anchor, timestamp}
        self.poly_price_history: dict[str, list[dict]] = {}


class SessionManager:
    """Orchestrates the full trading lifecycle across consecutive sessions."""

    def __init__(
        self,
        scanner: MarketScanner,
        executor: BaseExecutor,
        tracker: PositionTracker,
        settlement: SettlementTracker,
        store: DataStore,
        hub: LiveHub | None = None,
        btc_streamer=None,
        strategy_name: str = "btc_15m_live",
        strategy_config: dict | None = None,
        composite_config: CompositeConfig | None = None,
    ) -> None:
        self._scanner = scanner
        self._executor = executor
        self._tracker = tracker
        self._settlement = settlement
        self._store = store
        self._hub = hub
        self._btc_streamer = btc_streamer
        self._strategy_name = strategy_name
        self._strategy_config = strategy_config or {}
        self._composite_config = composite_config  # None = single strategy mode

        self._ws: PolymarketWSClient | None = None
        self._current: SessionSlot | None = None
        self._next: SessionSlot | None = None
        # Sessions waiting for settlement in the background
        self._settling: list[SessionSlot] = []

        self._task: asyncio.Task | None = None
        self._stop = asyncio.Event()
        self._paused = False

        # Price snapshot throttle: token_id → last_write_time
        self._last_price_write: dict[str, float] = {}
        # BTC recording throttle (1s)
        self._last_btc_record: float = 0.0
        # Poly price recording throttle (1s)
        self._last_poly_record: float = 0.0

    # ── Public state ──────────────────────────────────────────

    @property
    def is_running(self) -> bool:
        return self._task is not None and not self._task.done()

    @property
    def is_paused(self) -> bool:
        return self._paused

    @property
    def current_session(self) -> SessionSlot | None:
        return self._current

    @property
    def next_session(self) -> SessionSlot | None:
        return self._next

    def get_status(self) -> dict:
        ws_connected = self._ws.connected if self._ws else False
        return {
            "running": self.is_running,
            "paused": self._paused,
            "ws_connected": ws_connected,
            "executor_ready": self._executor.is_ready,
            "current_session": self._slot_status(self._current),
            "next_session": self._slot_status(self._next),
            "settling_count": len(self._settling),
        }

    def _slot_status(self, slot: SessionSlot | None) -> dict | None:
        if not slot:
            return None
        now = datetime.now(timezone.utc)
        remaining = slot.session.end_epoch - now.timestamp()
        return {
            "slug": slot.session.slug,
            "state": slot.state.value,
            "time_remaining_s": round(max(0, remaining), 1),
            "trades": len(slot.trades),
            "has_position": self._tracker.has_position(),
            "btc_trend_computed": slot.btc_trend_computed,
            "btc_trend_passed": slot.btc_trend_info.get("passed") if slot.btc_trend_info else None,
            "btc_amplitude": slot.btc_trend_info.get("amplitude") if slot.btc_trend_info else None,
            "btc_direction": slot.btc_trend_info.get("direction") if slot.btc_trend_info else None,
            "matched_branch": slot.matched_branch,
            "no_trades": slot.no_trades,
        }

    # ── Config update ─────────────────────────────────────────

    def update_config(self, config: dict) -> None:
        self._strategy_config.update(config)
        logger.info("Strategy config updated: %s", config)

    def set_composite_config(self, composite: CompositeConfig | None) -> None:
        """Set or clear composite strategy configuration."""
        self._composite_config = composite
        if composite:
            logger.info("Composite strategy set: %s (%d branches)", composite.name, len(composite.branches))
        else:
            logger.info("Composite strategy cleared — using single strategy mode")

    @property
    def composite_config(self) -> CompositeConfig | None:
        return self._composite_config

    def pause(self) -> None:
        self._paused = True
        logger.info("Trading paused")

    def resume(self) -> None:
        self._paused = False
        logger.info("Trading resumed")

    # ── Lifecycle ─────────────────────────────────────────────

    async def start(self) -> None:
        self._stop.clear()

        # Create WS client
        self._ws = PolymarketWSClient(on_event=self._on_ws_event)
        await self._ws.start()

        self._task = asyncio.create_task(self._run_loop())
        logger.info("SessionManager started")

    async def stop(self) -> None:
        self._stop.set()
        if self._ws:
            await self._ws.stop()
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("SessionManager stopped")

    # ── Main loop ─────────────────────────────────────────────

    async def _run_loop(self) -> None:
        while not self._stop.is_set():
            try:
                await self._tick()
            except asyncio.CancelledError:
                return
            except Exception as e:
                logger.error("SessionManager tick error: %s", e, exc_info=True)
            await asyncio.sleep(1)

    async def _tick(self) -> None:
        now = datetime.now(timezone.utc)
        now_ts = now.timestamp()

        # ── 0. Record BTC price into active session (always, regardless of frontend) ──
        if self._current and self._current.state == SessionState.ACTIVE and self._btc_streamer:
            mono_now = time.monotonic()
            if mono_now - self._last_btc_record >= 1.0:
                self._last_btc_record = mono_now
                price = self._btc_streamer.last_price
                if price > 0:
                    point = {
                        "price": price,
                        "timestamp": now.isoformat(),
                    }
                    self._current.btc_history.append(point)

        # ── 0b. Record Poly Up/Down prices into active session ──
        if self._current and self._current.state == SessionState.ACTIVE:
            mono_now = time.monotonic()
            if mono_now - self._last_poly_record >= 1.0:
                self._last_poly_record = mono_now
                for i, token_id in enumerate(self._current.session.token_ids):
                    mkt = self._current.ob.get_market_data(token_id)
                    if mkt.mid_price > 0:
                        outcome = (
                            self._current.session.outcomes[i]
                            if i < len(self._current.session.outcomes)
                            else "Unknown"
                        )
                        point = {
                            "mid": mkt.mid_price,
                            "bid": mkt.best_bid,
                            "ask": mkt.best_ask,
                            "anchor": mkt.anchor_price,
                            "outcome": outcome,
                            "timestamp": now.isoformat(),
                        }
                        hist = self._current.poly_price_history.setdefault(token_id, [])
                        hist.append(point)
                        # Cap at 900 points (15 min @ 1s)
                        if len(hist) > 900:
                            self._current.poly_price_history[token_id] = hist[-900:]

        # ── 1. Discover sessions ──
        if not self._current and not self._next:
            info = self._scanner.get_current_or_next()
            if info:
                self._current = SessionSlot(info)
                self._current.state = SessionState.DISCOVERED
                self._store.save_session(info, SessionState.DISCOVERED)
                logger.info("Discovered session: %s", info.slug)
        if self._current and not self._next:
            info = self._scanner.get_next_after(self._current.session.slug)
            if info:
                self._next = SessionSlot(info)
                self._next.state = SessionState.DISCOVERED
                self._store.save_session(info, SessionState.DISCOVERED)
                logger.info("Discovered next session: %s", info.slug)

        # ── 2. Prepare next session (pre-connect WS) ──
        if self._next and self._next.state == SessionState.DISCOVERED:
            secs_until = self._next.session.start_epoch - now_ts
            if secs_until <= settings.session_prepare_ahead_s:
                await self._prepare_slot(self._next)

        # ── 3. Activate current session when start time arrives ──
        if self._current and self._current.state in (SessionState.DISCOVERED, SessionState.PREPARING):
            if now_ts >= self._current.session.start_epoch:
                await self._activate_slot(self._current)

        # ── 4. Handle active/skipped session expiry → rotate immediately ──
        if self._current and self._current.state in (SessionState.ACTIVE, SessionState.SKIPPED):
            remaining = self._current.session.end_epoch - now_ts
            if remaining <= 0:
                # Session ended — move to settling (background) and rotate
                await self._expire_and_rotate()
            elif not self._paused and self._current.state == SessionState.ACTIVE:
                await self._process_active_session(self._current, remaining)

        # ── 5. Background settlement processing ──
        await self._process_settling()

        # ── 6. Broadcast to WS clients (only when someone is watching) ──
        if self._hub and self._hub.client_count > 0:
            await self._hub.broadcast("session", self.get_status())
            if self._current and self._current.state == SessionState.ACTIVE:
                market = self._build_market_broadcast(self._current)
                if market:
                    await self._hub.broadcast("market", market)

    async def _expire_and_rotate(self) -> None:
        """Current session ended — finalize before moving to settling.

        1. Attempt one final close check (force-close open positions).
        2. Mark whether any trades happened (no_trades flag).
        3. Transition to CLOSING → settling queue.
        4. Promote next session.
        WS events continue to flow to settling sessions via _on_ws_event.
        """
        old = self._current
        assert old is not None

        # ── 1. Finalize session: force-close attempt if positions open ──
        await self._finalize_session(old)

        # ── 2. Mark no-trades if the session had zero fills ──
        if len(old.trades) == 0:
            old.no_trades = True
            logger.info("Session %s ended with no trades", old.session.slug)

        # ── 3. Transition to CLOSING and add to settling queue ──
        old.state = SessionState.CLOSING
        self._store.save_session(old.session, SessionState.CLOSING)
        self._settling.append(old)
        logger.info(
            "Session expired → settling: %s (trades=%d, no_trades=%s)",
            old.session.slug, len(old.trades), old.no_trades,
        )

        # ── 4. Promote next → current ──
        self._current = self._next
        self._next = None

        # If the promoted session's start time has arrived, activate it now
        if self._current:
            now_ts = datetime.now(timezone.utc).timestamp()
            if now_ts >= self._current.session.start_epoch:
                await self._activate_slot(self._current)
            logger.info("Promoted next → current: %s", self._current.session.slug)

            # Broadcast new session state to any connected frontend clients
            if self._hub and self._hub.client_count > 0:
                await self._hub.broadcast("session", self.get_status())
                # Send empty btc_history for the new session (will fill as data arrives)
                await self._hub.broadcast("btc_history", self._current.btc_history)
                # Send empty poly_price_history for the new session
                await self._hub.broadcast("poly_price_history", self._current.poly_price_history)
        else:
            logger.warning("No next session available after rotation")

    async def _finalize_session(self, slot: SessionSlot) -> None:
        """Complete session-end work before moving to settling.

        - If strategy holds a position, attempt a final force-close.
        - Let strategy know the session is ending.
        - WS stays connected so settlement can resolve later.
        """
        if not slot.strategy:
            return

        # Check if we still hold a position that should be force-closed
        if self._tracker.has_position():
            ctx = self._build_context(slot, remaining=0)
            # Give strategy one last chance to produce a close signal
            close_signal = slot.strategy.should_close(ctx)
            if close_signal:
                logger.info(
                    "Final close signal for %s: %s %s",
                    slot.session.slug, close_signal.side, close_signal.reason,
                )
                await self._execute_signal(slot, close_signal)

    async def _process_settling(self) -> None:
        """Process background settlement for all settling sessions."""
        done: list[SessionSlot] = []
        for slot in self._settling:
            resolved = await self._handle_settlement(slot)
            if resolved:
                done.append(slot)
        for slot in done:
            self._settling.remove(slot)

    # ── Slot operations ───────────────────────────────────────

    async def _prepare_slot(self, slot: SessionSlot) -> None:
        """Pre-connect WS and subscribe to token IDs."""
        slot.state = SessionState.PREPARING
        if self._ws:
            await self._ws.subscribe(slot.session.token_ids)
        logger.info("Preparing session: %s (subscribed WS)", slot.session.slug)

    async def _activate_slot(self, slot: SessionSlot) -> None:
        """Activate session — initialize strategy."""
        # Ensure WS subscribed
        if self._ws and slot.state != SessionState.PREPARING:
            await self._ws.subscribe(slot.session.token_ids)

        slot.state = SessionState.ACTIVE
        slot.strategy = get_strategy(self._strategy_name)
        slot.strategy.on_session_start(slot.session, self._strategy_config)
        self._tracker.reset_session()
        self._store.save_session(slot.session, SessionState.ACTIVE)
        logger.info("Session ACTIVE: %s", slot.session.slug)

    async def _process_active_session(self, slot: SessionSlot, remaining: float) -> None:
        """Run strategy logic for the active session.

        BTC trend integration:
        - Once window_2 time has elapsed, compute BTC trend from klines
        - Feed result to strategy (gatekeeper for entry)
        - If composite mode, select branch config by amplitude
        """
        if not slot.strategy:
            return

        # ── BTC trend computation (once per session, after window_2 elapsed) ──
        if not slot.btc_trend_computed:
            await self._maybe_compute_btc_trend(slot, remaining)

        # Build context
        ctx = self._build_context(slot, remaining)

        # If strategy decided to skip, don't process
        if hasattr(slot.strategy, 'session_skipped') and slot.strategy.session_skipped:
            return

        # Check close first
        close_signal = slot.strategy.should_close(ctx)
        if close_signal:
            await self._execute_signal(slot, close_signal)
            return

        # Check entry
        signals = slot.strategy.on_market_update(ctx)
        if signals:
            for signal in signals:
                await self._execute_signal(slot, signal)

    async def _maybe_compute_btc_trend(self, slot: SessionSlot, remaining: float) -> None:
        """Compute BTC trend once window_2 time has elapsed since session start."""
        # Determine window parameters (from composite or strategy config)
        if self._composite_config:
            w1 = self._composite_config.window_1
            w2 = self._composite_config.window_2
            min_mom = self._composite_config.btc_min_momentum
        else:
            w1 = int(self._strategy_config.get("btc_trend_window_1", 5))
            w2 = int(self._strategy_config.get("btc_trend_window_2", 10))
            min_mom = float(self._strategy_config.get("btc_min_momentum", 0.001))

        # Check if enough time has elapsed (window_2 minutes from session start)
        elapsed = slot.session.duration_s - remaining
        window_2_seconds = w2 * 60
        if elapsed < window_2_seconds:
            return  # Not yet time to compute

        # Compute BTC trend from Binance klines
        # Only fetch klines up to window_2 boundary (not entire session)
        iso_times = slug_to_iso(slot.session.slug)
        if not iso_times:
            start_dt = datetime.fromtimestamp(slot.session.start_epoch, tz=timezone.utc)
            start_iso = start_dt.isoformat()
        else:
            start_iso = iso_times[0]

        # end range = session_start + window_2 + 1min buffer (for the last kline)
        w2_end_dt = datetime.fromtimestamp(
            slot.session.start_epoch + window_2_seconds + 60, tz=timezone.utc
        )
        w2_end_iso = w2_end_dt.isoformat()

        trend_info = await compute_session_btc_trend(
            session_start_iso=start_iso,
            session_end_iso=w2_end_iso,
            window_1_min=w1,
            window_2_min=w2,
            min_momentum=min_mom,
        )

        slot.btc_trend_computed = True
        slot.btc_trend_info = trend_info

        # ── Composite branch selection ──
        effective_config = dict(self._strategy_config)
        if self._composite_config and trend_info.get("passed"):
            amplitude = trend_info.get("amplitude", 0.0)
            branch = self._composite_config.select_branch(amplitude)
            if branch:
                # Merge branch config into strategy config
                branch_cfg = branch.get("config", {})
                effective_config.update(branch_cfg)
                slot.matched_branch = branch.get("label", "unknown")
                logger.info(
                    "Composite branch '%s' selected for %s (amp=%.6f)",
                    slot.matched_branch, slot.session.slug, amplitude,
                )
            else:
                # No branch matched → skip session
                trend_info["passed"] = False
                logger.info(
                    "No composite branch matched for %s (amp=%.6f) → skip",
                    slot.session.slug, amplitude,
                )

        # Re-initialize strategy with effective config if composite branch was selected
        if slot.matched_branch and slot.strategy:
            slot.strategy.on_session_start(slot.session, effective_config)

        # Feed BTC trend result to strategy
        if hasattr(slot.strategy, 'on_btc_trend_result'):
            slot.strategy.on_btc_trend_result(trend_info)

        # Mark session as skipped if trend didn't pass
        if not trend_info.get("passed") and hasattr(slot.strategy, 'session_skipped'):
            if slot.strategy.session_skipped:
                slot.state = SessionState.SKIPPED
                self._store.save_session(slot.session, SessionState.SKIPPED)
                logger.info("Session %s SKIPPED by BTC trend filter", slot.session.slug)

    async def _execute_signal(self, slot: SessionSlot, signal: LiveSignal) -> None:
        """Execute a trading signal via the order executor."""
        if not self._executor.is_ready:
            logger.warning("Executor not ready — skipping signal")
            return

        # Validate minimum trade
        if signal.side == "BUY" and signal.amount_usdc < settings.min_trade_usdc:
            logger.warning("BUY amount $%.2f below minimum $%.2f", signal.amount_usdc, settings.min_trade_usdc)
            return

        logger.info(
            "Executing %s %s $%.2f @ %.4f [%s]",
            signal.side, signal.token_id[:12], signal.amount_usdc,
            signal.limit_price or 0, signal.reason,
        )

        retries = 0
        max_retries = settings.order_max_retries if self._tracker.has_position() else 1

        while retries < max_retries:
            fill = await self._executor.place_order(signal, slot.session.slug)
            if fill:
                self._tracker.apply_fill(fill)
                slot.trades.append(fill)
                self._store.save_trade(fill)
                if slot.strategy:
                    slot.strategy.on_fill(fill)
                # Broadcast trade to WS clients
                if self._hub:
                    from dataclasses import asdict
                    await self._hub.broadcast("trade", asdict(fill))
                return

            retries += 1
            if retries < max_retries:
                logger.warning("Order failed, retry %d/%d", retries, max_retries)
                await asyncio.sleep(2)

        # All retries failed
        error = TradeError(
            error_type="order_failed",
            message=f"Failed to execute {signal.side} after {max_retries} attempts",
            has_position=self._tracker.has_position(),
        )
        self._store.save_error(slot.session.slug, error.error_type, error.message)

        if slot.strategy:
            action = slot.strategy.on_error(error)
            if action == ErrorAction.STOP:
                slot.state = SessionState.ERROR
                slot.error = error.message

    async def _close_session(self, slot: SessionSlot) -> None:
        """Session time is up — transition to CLOSING (used by _expire_and_rotate)."""
        slot.state = SessionState.CLOSING
        self._store.save_session(slot.session, SessionState.CLOSING)
        logger.info("Session CLOSING: %s", slot.session.slug)

    async def _handle_settlement(self, slot: SessionSlot) -> bool:
        """Check for settlement and finalise PnL. Returns True if resolved."""
        resolution = await self._settlement.check_resolution(slot.session)
        if not resolution:
            return False  # Not yet resolved, will check again next tick

        winning_token = resolution.get("winning_token_id", "")
        winning_outcome = resolution.get("winning_outcome", "")

        # Apply settlement for all held positions
        settlement_pnl = 0.0
        for token_id in list(self._tracker.positions.keys()):
            is_winner = token_id == winning_token
            pnl = self._tracker.apply_settlement(token_id, is_winner)
            settlement_pnl += pnl

        # Build result
        result = SessionResult(
            session=slot.session,
            state=SessionState.SETTLED,
            trades=slot.trades,
            trade_pnl=self._tracker.realised_pnl - settlement_pnl,
            settlement_pnl=settlement_pnl,
            total_pnl=self._tracker.realised_pnl,
            settlement_outcome=winning_outcome,
        )

        slot.state = SessionState.SETTLED
        self._store.update_session_result(result)

        if slot.strategy:
            slot.strategy.on_session_end(result)

        logger.info(
            "Session SETTLED: %s | outcome=%s | PnL=$%.4f | no_trades=%s",
            slot.session.slug, winning_outcome, result.total_pnl, slot.no_trades,
        )

        # Unsubscribe old token IDs that are no longer needed by current/next
        active_tokens: set[str] = set()
        for s in (self._current, self._next):
            if s:
                active_tokens.update(s.session.token_ids)
        stale = set(slot.session.token_ids) - active_tokens
        if stale and self._ws:
            await self._ws.unsubscribe(list(stale))
            logger.debug("Unsubscribed stale tokens after settlement: %s", stale)

        return True

    # ── Context builder ───────────────────────────────────────

    def _build_context(self, slot: SessionSlot, remaining: float) -> LiveMarketContext:
        now = datetime.now(timezone.utc).isoformat()
        tokens = {}
        current_prices: dict[str, float] = {}

        for token_id in slot.session.token_ids:
            mkt = slot.ob.get_market_data(token_id)
            tokens[token_id] = mkt
            current_prices[token_id] = mkt.mid_price

            # Throttled price snapshots (every 5s)
            last = self._last_price_write.get(token_id, 0)
            if time.monotonic() - last > 5:
                self._store.save_price_snapshot(
                    slot.session.slug, token_id,
                    mkt.mid_price, mkt.best_bid, mkt.best_ask,
                    mkt.spread, mkt.anchor_price,
                )
                self._last_price_write[token_id] = time.monotonic()

        price_history = {
            tid: slot.ob.get_price_history(tid) for tid in slot.session.token_ids
        }

        return LiveMarketContext(
            timestamp=now,
            session=slot.session,
            time_remaining_s=remaining,
            tokens=tokens,
            balance=self._tracker.balance,
            positions=self._tracker.positions,
            equity=self._tracker.equity(current_prices),
            initial_balance=self._tracker.initial_balance,
            price_history=price_history,
            trade_history=[
                {"side": t.side, "price": t.avg_price, "shares": t.filled_shares}
                for t in slot.trades
            ],
            session_pnl=self._tracker.realised_pnl,
            unrealized_pnl=self._tracker.unrealised_pnl(current_prices),
            btc_trend=slot.btc_trend_info,
        )

    # ── Market broadcast builder ────────────────────────────────

    def _build_market_broadcast(self, slot: SessionSlot) -> dict | None:
        """Build market data snapshot for WS broadcast."""
        if not slot or not slot.session:
            return None
        result: dict = {"slug": slot.session.slug, "tokens": {}}
        for i, token_id in enumerate(slot.session.token_ids):
            mkt = slot.ob.get_market_data(token_id)
            outcome = slot.session.outcomes[i] if i < len(slot.session.outcomes) else "Unknown"
            result["tokens"][token_id] = {
                "outcome": outcome,
                "mid_price": mkt.mid_price,
                "best_bid": mkt.best_bid,
                "best_ask": mkt.best_ask,
                "spread": mkt.spread,
                "anchor_price": mkt.anchor_price,
                "bid_levels": [[p, s] for p, s in mkt.bid_levels[:5]],
                "ask_levels": [[p, s] for p, s in mkt.ask_levels[:5]],
            }
        return result

    # ── WS event handler ─────────────────────────────────────

    async def _on_ws_event(self, event_type: str, asset_id: str, data: dict) -> None:
        """Route WS events to the appropriate session's orderbook builder.

        Also routes to settling sessions so they can receive final price
        updates needed for settlement resolution.
        """
        all_slots = [self._current, self._next] + self._settling
        for slot in all_slots:
            if not slot:
                continue
            if asset_id not in slot.session.token_ids:
                continue

            if event_type == "book":
                slot.ob.handle_book(asset_id, data)
            elif event_type == "price_change":
                slot.ob.handle_price_change(asset_id, data)
            elif event_type == "last_trade_price":
                slot.ob.handle_last_trade_price(asset_id, data)
            elif event_type == "best_bid_ask":
                slot.ob.handle_best_bid_ask(asset_id, data)
