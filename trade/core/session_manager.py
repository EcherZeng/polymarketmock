"""Session manager — dual-slot orchestrator for continuous BTC 15-minute trading.

Manages the lifecycle: discover → prepare → active → closing → settled,
with seamless handoff between consecutive sessions.
"""

from __future__ import annotations

import asyncio
import logging
import time
from datetime import datetime, timezone

from config import settings
from core.base_executor import BaseExecutor
from core.data_store import DataStore
from core.live_hub import LiveHub
from core.market_scanner import MarketScanner
from core.orderbook_builder import OrderbookBuilder
from core.position_tracker import PositionTracker
from core.settlement_tracker import SettlementTracker
from core.strategy_engine import get_strategy
from core.types import (
    ErrorAction,
    LiveFill,
    LiveMarketContext,
    LiveSignal,
    SessionInfo,
    SessionResult,
    SessionState,
    TradeError,
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
        }

    # ── Config update ─────────────────────────────────────────

    def update_config(self, config: dict) -> None:
        self._strategy_config.update(config)
        logger.info("Strategy config updated: %s", config)

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

        # ── 4. Handle active session expiry → rotate immediately ──
        if self._current and self._current.state == SessionState.ACTIVE:
            remaining = self._current.session.end_epoch - now_ts
            if remaining <= 0:
                # Session ended — move to settling (background) and rotate
                await self._expire_and_rotate()
            elif not self._paused:
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
        """Current session ended — move to settling, promote next immediately."""
        old = self._current
        assert old is not None

        old.state = SessionState.CLOSING
        self._store.save_session(old.session, SessionState.CLOSING)
        self._settling.append(old)
        logger.info("Session expired → settling: %s", old.session.slug)

        # Immediately promote next → current
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
        else:
            logger.warning("No next session available after rotation")

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
        """Run strategy logic for the active session."""
        if not slot.strategy:
            return

        # Build context
        ctx = self._build_context(slot, remaining)

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
            "Session SETTLED: %s | outcome=%s | PnL=$%.4f",
            slot.session.slug, winning_outcome, result.total_pnl,
        )
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
        """Route WS events to the appropriate session's orderbook builder."""
        for slot in (self._current, self._next):
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
