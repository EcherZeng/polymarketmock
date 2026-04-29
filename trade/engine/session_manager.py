"""Session manager — dual-slot orchestrator for BTC 15-minute live trading."""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import asdict
from datetime import datetime, timezone

from config import settings
from engine.btc_trend import compute_session_btc_trend
from engine.strategy_engine import CompositeConfig
from execution.base_executor import BaseExecutor
from infra.data_store import DataStore
from infra.live_hub import LiveHub
from market.market_scanner import MarketScanner
from market.orderbook_builder import OrderbookBuilder
from market.ws_client import PolymarketWSClient
from models.types import (
    LiveFill,
    LiveMarketContext,
    LiveSignal,
    SessionInfo,
    SessionResult,
    SessionState,
    slug_to_iso,
)
from portfolio.position_tracker import PositionTracker
from portfolio.settlement_tracker import SettlementTracker
from strategies.btc_15m_live import Btc15mLiveStrategy

logger = logging.getLogger(__name__)

_MAX_SETTLING = 20


class SessionSlot:
    __slots__ = (
        "session", "state", "strategy", "ob", "trades",
        "btc_history", "btc_trend_computed", "btc_trend_info",
        "matched_branch", "no_trades", "skipped", "poly_price_history",
    )

    def __init__(self, session: SessionInfo) -> None:
        self.session = session
        self.state = SessionState.PENDING
        self.strategy: Btc15mLiveStrategy | None = None
        self.ob = OrderbookBuilder()
        self.trades: list[LiveFill] = []
        self.btc_history: list[dict] = []
        self.btc_trend_computed = False
        self.btc_trend_info: dict = {}
        self.matched_branch: str | None = None
        self.no_trades = False
        self.skipped = False
        self.poly_price_history: dict[str, list[dict]] = {}


class SessionManager:

    def __init__(
        self,
        scanner: MarketScanner,
        executor: BaseExecutor,
        tracker: PositionTracker,
        settlement: SettlementTracker,
        store: DataStore,
        hub: LiveHub | None = None,
        btc_streamer=None,
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
        self._strategy_config = strategy_config or {}
        self._composite_config = composite_config
        self._active_preset_name: str | None = None
        self._active_preset_type: str = "none"

        self._ws: PolymarketWSClient | None = None
        self._current: SessionSlot | None = None
        self._next: SessionSlot | None = None
        self._settling: list[SessionSlot] = []

        self._task: asyncio.Task | None = None
        self._stop = asyncio.Event()
        self._paused = False
        self._tick_lock = asyncio.Lock()

        self._last_price_write: dict[str, float] = {}
        self._last_btc_record: float = 0.0
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
        prices = self._current_prices()
        return {
            "running": self.is_running,
            "paused": self._paused,
            "ws_connected": self._ws.connected if self._ws else False,
            "executor_ready": self._executor.is_ready,
            "current_session": self._slot_status(self._current),
            "next_session": self._slot_status(self._next),
            "settling_count": len(self._settling),
            "portfolio": {
                "balance": round(self._tracker.balance, 6),
                "initial_balance": round(self._tracker.initial_balance, 6),
                "positions": {tid: round(s, 4) for tid, s in self._tracker.positions.items()},
                "equity": round(self._tracker.equity(prices), 6),
                "realised_pnl": round(self._tracker.realised_pnl, 6),
                "unrealised_pnl": round(self._tracker.unrealised_pnl(prices), 6),
            },
        }

    def _current_prices(self) -> dict[str, float]:
        if not self._current:
            return {}
        return {
            tid: self._current.ob.get_market_data(tid).mid_price
            for tid in self._current.session.token_ids
        }

    def _slot_status(self, slot: SessionSlot | None) -> dict | None:
        if not slot:
            return None
        remaining = slot.session.end_epoch - datetime.now(timezone.utc).timestamp()
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
            "btc_a1": slot.btc_trend_info.get("a1") if slot.btc_trend_info else None,
            "btc_a2": slot.btc_trend_info.get("a2") if slot.btc_trend_info else None,
            "btc_p0": slot.btc_trend_info.get("p0") if slot.btc_trend_info else None,
            "btc_p_w1": slot.btc_trend_info.get("p_w1") if slot.btc_trend_info else None,
            "btc_p_w2": slot.btc_trend_info.get("p_w2") if slot.btc_trend_info else None,
            "matched_branch": slot.matched_branch,
            "skipped": slot.skipped,
            "no_trades": slot.no_trades,
        }

    # ── Config ────────────────────────────────────────────────

    def update_config(self, config: dict) -> None:
        self._strategy_config.update(config)

    def set_composite_config(self, composite: CompositeConfig | None) -> None:
        self._composite_config = composite

    def set_active_preset(self, name: str | None, preset_type: str = "none") -> None:
        self._active_preset_name = name
        self._active_preset_type = preset_type

    @property
    def active_preset_name(self) -> str | None:
        return self._active_preset_name

    @property
    def active_preset_type(self) -> str:
        return self._active_preset_type

    @property
    def composite_config(self) -> CompositeConfig | None:
        return self._composite_config

    def pause(self) -> None:
        self._paused = True

    def resume(self) -> None:
        self._paused = False

    # ── Lifecycle ─────────────────────────────────────────────

    async def start(self) -> None:
        self._stop.clear()
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
                async with self._tick_lock:
                    await self._tick()
            except asyncio.CancelledError:
                return
            except Exception as e:
                logger.error("Tick error: %s", e, exc_info=True)
            await asyncio.sleep(1)

    async def _tick(self) -> None:
        now = datetime.now(timezone.utc)
        now_ts = now.timestamp()

        # ── 0. Record BTC + Poly prices into active session ──
        if self._current and self._current.state == SessionState.ACTIVE:
            self._record_prices(self._current, now)

        # ── 1. Discover sessions ──
        if not self._current and not self._next:
            info = self._scanner.get_current_or_next()
            if info:
                self._current = SessionSlot(info)
                self._store.save_session(info, SessionState.PENDING)
                logger.info("Discovered session: %s", info.slug)
        if self._current and not self._next:
            info = self._scanner.get_next_after(self._current.session.slug)
            if info:
                self._next = SessionSlot(info)
                self._store.save_session(info, SessionState.PENDING)
                logger.info("Discovered next session: %s", info.slug)

        # ── 2. Prepare next session (pre-subscribe WS) ──
        if self._next and self._next.state == SessionState.PENDING:
            if self._next.session.start_epoch - now_ts <= settings.session_prepare_ahead_s:
                if self._ws:
                    await self._ws.subscribe(self._next.session.token_ids)

        # ── 3. Activate current session when start time arrives ──
        if self._current and self._current.state == SessionState.PENDING:
            if now_ts >= self._current.session.start_epoch:
                await self._activate_slot(self._current)

        # ── 4. Handle active session ──
        if self._current and self._current.state == SessionState.ACTIVE:
            remaining = self._current.session.end_epoch - now_ts
            if remaining <= 0:
                await self._expire_and_rotate()
            elif not self._paused and not self._current.skipped:
                await self._process_active_session(self._current, remaining)

        # ── 5. Background settlement ──
        await self._process_settling()

        # ── 6. Broadcast to WS clients ──
        if self._hub and self._hub.client_count > 0:
            await self._hub.broadcast("session", self.get_status())
            if self._current and self._current.state == SessionState.ACTIVE:
                market = self._build_market_broadcast(self._current)
                if market:
                    await self._hub.broadcast("market", market)

    def _record_prices(self, slot: SessionSlot, now: datetime) -> None:
        mono = time.monotonic()
        # BTC price
        if self._btc_streamer and mono - self._last_btc_record >= 1.0:
            self._last_btc_record = mono
            price = self._btc_streamer.last_price
            if price > 0:
                slot.btc_history.append({"price": price, "timestamp": now.isoformat()})

        # Poly token prices
        if mono - self._last_poly_record >= 1.0:
            self._last_poly_record = mono
            for i, token_id in enumerate(slot.session.token_ids):
                mkt = slot.ob.get_market_data(token_id)
                if mkt.mid_price > 0:
                    outcome = slot.session.outcomes[i] if i < len(slot.session.outcomes) else "Unknown"
                    hist = slot.poly_price_history.setdefault(token_id, [])
                    hist.append({
                        "mid": mkt.mid_price, "bid": mkt.best_bid,
                        "ask": mkt.best_ask, "anchor": mkt.anchor_price,
                        "outcome": outcome, "timestamp": now.isoformat(),
                    })
                    if len(hist) > 900:
                        slot.poly_price_history[token_id] = hist[-900:]

    # ── Slot operations ───────────────────────────────────────

    async def _activate_slot(self, slot: SessionSlot) -> None:
        if self._ws:
            await self._ws.subscribe(slot.session.token_ids)
        slot.state = SessionState.ACTIVE
        slot.strategy = Btc15mLiveStrategy()
        slot.strategy.on_session_start(slot.session, self._strategy_config)
        self._tracker.reset_session()
        logger.info("Session ACTIVE: %s", slot.session.slug)

    async def _process_active_session(self, slot: SessionSlot, remaining: float) -> None:
        if not slot.strategy:
            return

        if not slot.btc_trend_computed:
            await self._maybe_compute_btc_trend(slot, remaining)
            # Wait until BTC trend is computed before allowing entry
            if not slot.btc_trend_computed:
                return

        ctx = self._build_context(slot, remaining)

        if slot.strategy.session_skipped:
            return

        close_signal = slot.strategy.should_close(ctx)
        if close_signal:
            await self._execute_signal(slot, close_signal)
            return

        signals = slot.strategy.on_market_update(ctx)
        if signals:
            for signal in signals:
                await self._execute_signal(slot, signal)

    async def _maybe_compute_btc_trend(self, slot: SessionSlot, remaining: float) -> None:
        if self._composite_config:
            w1 = self._composite_config.window_1
            w2 = self._composite_config.window_2
            min_mom = self._composite_config.btc_min_momentum
        else:
            w1 = int(self._strategy_config.get("btc_trend_window_1", 5))
            w2 = int(self._strategy_config.get("btc_trend_window_2", 10))
            min_mom = float(self._strategy_config.get("btc_min_momentum", 0.001))

        elapsed = slot.session.duration_s - remaining
        window_2_s = w2 * 60
        if elapsed < window_2_s:
            return

        iso_times = slug_to_iso(slot.session.slug)
        start_iso = iso_times[0] if iso_times else datetime.fromtimestamp(
            slot.session.start_epoch, tz=timezone.utc
        ).isoformat()
        w2_end_iso = datetime.fromtimestamp(
            slot.session.start_epoch + window_2_s + 60, tz=timezone.utc
        ).isoformat()

        trend_info = await compute_session_btc_trend(
            session_start_iso=start_iso,
            session_end_iso=w2_end_iso,
            window_1_min=w1,
            window_2_min=w2,
            min_momentum=min_mom,
        )

        slot.btc_trend_computed = True
        slot.btc_trend_info = trend_info

        # Composite branch selection
        effective_config = dict(self._strategy_config)
        if self._composite_config and trend_info.get("passed"):
            amplitude = trend_info.get("amplitude", 0.0)
            branch = self._composite_config.select_branch(amplitude)
            if branch:
                effective_config.update(branch.get("config", {}))
                slot.matched_branch = branch.get("label", "unknown")
            else:
                trend_info["passed"] = False

        if slot.matched_branch and slot.strategy:
            slot.strategy.on_session_start(slot.session, effective_config)

        if slot.strategy:
            slot.strategy.on_btc_trend_result(trend_info)

        if slot.strategy and slot.strategy.session_skipped:
            slot.skipped = True
            logger.info("Session %s SKIPPED by BTC trend", slot.session.slug)

    async def _execute_signal(self, slot: SessionSlot, signal: LiveSignal) -> None:
        if not self._executor.is_ready:
            logger.warning("Executor not ready — skipping signal")
            return

        if signal.side == "BUY" and signal.amount_usdc < settings.min_trade_usdc:
            return

        logger.info(
            "Executing %s %s $%.2f @ %.4f [%s]",
            signal.side, signal.token_id[:12], signal.amount_usdc,
            signal.limit_price or 0, signal.reason,
        )

        max_retries = settings.order_max_retries if self._tracker.has_position() else 1
        for attempt in range(max_retries):
            fill = await self._executor.place_order(signal, slot.session.slug)
            if fill:
                self._tracker.apply_fill(fill)
                slot.trades.append(fill)
                self._store.save_trade(fill)
                if slot.strategy:
                    slot.strategy.on_fill(fill)
                if self._hub:
                    await self._hub.broadcast("trade", asdict(fill))
                return
            if attempt + 1 < max_retries:
                logger.warning("Order failed, retry %d/%d", attempt + 1, max_retries)
                await asyncio.sleep(2)

        logger.error("Order failed [%s] %s after %d attempts", slot.session.slug, signal.side, max_retries)

    # ── Session rotation ──────────────────────────────────────

    async def _expire_and_rotate(self) -> None:
        old = self._current
        assert old is not None

        # Final close attempt
        if old.strategy and self._tracker.has_position():
            ctx = self._build_context(old, remaining=0)
            close_signal = old.strategy.should_close(ctx)
            if close_signal:
                await self._execute_signal(old, close_signal)

        if not old.trades:
            old.no_trades = True

        old.state = SessionState.SETTLING
        old.btc_history.clear()
        old.poly_price_history.clear()
        old.ob.reset()
        self._settling.append(old)
        logger.info("Session → settling: %s (trades=%d)", old.session.slug, len(old.trades))

        # Promote next
        self._current = self._next
        self._next = None
        if self._current:
            if datetime.now(timezone.utc).timestamp() >= self._current.session.start_epoch:
                await self._activate_slot(self._current)
            if self._hub and self._hub.client_count > 0:
                await self._hub.broadcast("session", self.get_status())
                await self._hub.broadcast("btc_history", self._current.btc_history)
                await self._hub.broadcast("poly_price_history", self._current.poly_price_history)

    async def _process_settling(self) -> None:
        done = [s for s in self._settling if await self._handle_settlement(s)]
        for s in done:
            self._settling.remove(s)
        while len(self._settling) > _MAX_SETTLING:
            evicted = self._settling.pop(0)
            logger.warning("Evicted stale settling session %s", evicted.session.slug)

    async def _handle_settlement(self, slot: SessionSlot) -> bool:
        resolution = await self._settlement.check_resolution(slot.session)
        if not resolution:
            return False

        winning_token = resolution.get("winning_token_id", "")
        winning_outcome = resolution.get("winning_outcome", "")

        settlement_pnl = 0.0
        for token_id in list(self._tracker.positions.keys()):
            settlement_pnl += self._tracker.apply_settlement(token_id, token_id == winning_token)

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
        self._store.settle_session(result)

        if slot.strategy:
            slot.strategy.on_session_end(result)

        logger.info("SETTLED: %s outcome=%s PnL=$%.4f", slot.session.slug, winning_outcome, result.total_pnl)

        # Push updated PnL to frontend
        if self._hub:
            pnl_data = {
                "total": self._store.get_total_pnl(),
                "recent": self._store.get_recent_pnl(10),
            }
            await self._hub.broadcast("pnl", pnl_data)

        # Unsubscribe stale tokens
        active_tokens: set[str] = set()
        for s in (self._current, self._next):
            if s:
                active_tokens.update(s.session.token_ids)
        stale = set(slot.session.token_ids) - active_tokens
        if stale and self._ws:
            await self._ws.unsubscribe(list(stale))

        return True

    # ── Context builder ───────────────────────────────────────

    def _build_context(self, slot: SessionSlot, remaining: float) -> LiveMarketContext:
        tokens = {}
        for token_id in slot.session.token_ids:
            mkt = slot.ob.get_market_data(token_id)
            tokens[token_id] = mkt

            # Throttled snapshot cache (every 5s)
            last = self._last_price_write.get(token_id, 0)
            if time.monotonic() - last > 5:
                self._store.push_snapshot(
                    slot.session.slug, token_id,
                    mkt.mid_price, mkt.best_bid, mkt.best_ask,
                    mkt.spread, mkt.anchor_price,
                )
                self._last_price_write[token_id] = time.monotonic()

        return LiveMarketContext(
            timestamp=datetime.now(timezone.utc).isoformat(),
            session=slot.session,
            time_remaining_s=remaining,
            tokens=tokens,
            balance=self._tracker.balance,
            positions=self._tracker.positions,
            btc_trend=slot.btc_trend_info,
        )

    def _build_market_broadcast(self, slot: SessionSlot) -> dict | None:
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
        for slot in (self._current, self._next):
            if not slot or asset_id not in slot.session.token_ids:
                continue
            if event_type == "book":
                slot.ob.handle_book(asset_id, data)
            elif event_type == "price_change":
                slot.ob.handle_price_change(asset_id, data)
            elif event_type == "last_trade_price":
                slot.ob.handle_last_trade_price(asset_id, data)
            elif event_type == "best_bid_ask":
                slot.ob.handle_best_bid_ask(asset_id, data)
