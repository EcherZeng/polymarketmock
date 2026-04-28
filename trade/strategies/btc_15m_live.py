"""BTC 15-minute live trading strategy.

Mirrors the backtest UnifiedStrategy + composite strategy logic:
- Uses BTC two-window sita (momentum) as entry gatekeeper
- Selects strategy parameters based on BTC amplitude (composite branches)
- Entry filters: min_price, profit_margin, time_remaining
- Exit: take_profit, stop_loss, force_close

Flow:
1. Wait for window_2 time to elapse (BTC data for both windows available)
2. Compute BTC trend (a1, a2) from Binance klines
3. If trend passes (same direction + sufficient momentum) → allow entry
4. If composite branches configured → select branch by amplitude
5. Apply entry filters (min_price, profit_margin)
6. Position sizing and order execution
"""

from __future__ import annotations

import logging
import math
import time

from core.types import (
    ErrorAction,
    LiveFill,
    LiveMarketContext,
    LiveSignal,
    SessionInfo,
    SessionResult,
    TradeError,
)
from strategies.base_live import BaseLiveStrategy

logger = logging.getLogger(__name__)


def _price_side(price: float) -> str:
    return "UP" if price >= 0.5 else "DOWN"


def _effective_price(price: float, side: str) -> float:
    return price if side == "UP" else (1.0 - price)


class Btc15mLiveStrategy(BaseLiveStrategy):
    name = "btc_15m_live"
    description = "BTC 15-minute session — two-window sita gated entry, hold to settlement"
    version = "2.0.0"
    default_config = {
        # ── BTC trend filter (two-window sita) ───────────────────
        "btc_trend_window_1": 5,        # first window in minutes
        "btc_trend_window_2": 10,       # second window in minutes (from session start)
        "btc_min_momentum": 0.001,      # minimum |a1+a2| to pass trend filter
        # ── Entry filters ────────────────────────────────────────
        "min_price": 0.85,
        "profit_margin": 0.03,
        "time_remaining_s": None,       # only enter if time_remaining <= this (None=disabled)
        # ── Position sizing ──────────────────────────────────────
        "position_min_pct": 0.10,
        "position_max_pct": 0.30,
        # ── Risk management ──────────────────────────────────────
        "take_profit_price": 0.95,
        "stop_loss_price": 0.0,         # 0 = disabled
        "force_close_remaining_s": 120,  # 2 minutes before end
        "min_close_profit": 0.02,       # don't close if profit < $0.02
    }

    def on_session_start(self, session: SessionInfo, config: dict) -> None:
        self._session = session
        self._cfg = {**self.default_config, **config}

        # BTC trend parameters
        self.btc_window_1: int = int(self._cfg["btc_trend_window_1"])
        self.btc_window_2: int = int(self._cfg["btc_trend_window_2"])
        self.btc_min_momentum: float = float(self._cfg["btc_min_momentum"])

        # Entry filters
        self.min_price: float = self._cfg["min_price"]
        self.profit_margin: float = self._cfg["profit_margin"]
        self.time_remaining_filter: int | None = (
            int(self._cfg["time_remaining_s"])
            if self._cfg.get("time_remaining_s") is not None
            else None
        )

        # Position sizing
        self.position_min_pct: float = self._cfg["position_min_pct"]
        self.position_max_pct: float = self._cfg["position_max_pct"]

        # Risk management
        self.tp_price: float = self._cfg["take_profit_price"]
        self.sl_price: float = self._cfg["stop_loss_price"]
        self.force_close_remaining_s: int = int(self._cfg["force_close_remaining_s"])
        self.min_close_profit: float = self._cfg["min_close_profit"]

        # State
        self._entered = False
        self._entry_token: str | None = None
        self._entry_side: str | None = None
        self._entry_price: float = 0.0
        self._btc_trend_checked = False
        self._btc_trend_passed = False
        self._btc_trend_direction: str = "UNKNOWN"
        self._btc_amplitude: float = 0.0
        self._session_skipped = False

        logger.info(
            "Strategy started for %s | w1=%dm w2=%dm min_mom=%.4f tp=%.2f sl=%.2f",
            session.slug, self.btc_window_1, self.btc_window_2,
            self.btc_min_momentum, self.tp_price, self.sl_price,
        )

    def on_btc_trend_result(self, trend_info: dict) -> None:
        """Called by session manager once BTC trend is computed (after window_2 elapsed).

        This is the gatekeeper: if trend doesn't pass, session is skipped.
        """
        self._btc_trend_checked = True
        self._btc_trend_passed = trend_info.get("passed", False)
        self._btc_trend_direction = trend_info.get("direction", "UNKNOWN")
        self._btc_amplitude = trend_info.get("amplitude", 0.0)

        if not self._btc_trend_passed:
            self._session_skipped = True
            logger.info(
                "BTC trend FAILED for %s — a1=%.6f a2=%.6f amp=%.6f (min=%.4f) → skip session",
                self._session.slug,
                trend_info.get("a1", 0),
                trend_info.get("a2", 0),
                self._btc_amplitude,
                self.btc_min_momentum,
            )
        else:
            logger.info(
                "BTC trend PASSED for %s — direction=%s amp=%.6f a1=%.6f a2=%.6f",
                self._session.slug,
                self._btc_trend_direction,
                self._btc_amplitude,
                trend_info.get("a1", 0),
                trend_info.get("a2", 0),
            )

    @property
    def btc_trend_checked(self) -> bool:
        return self._btc_trend_checked

    @property
    def session_skipped(self) -> bool:
        return self._session_skipped

    @property
    def btc_amplitude(self) -> float:
        return self._btc_amplitude

    def on_market_update(self, ctx: LiveMarketContext) -> list[LiveSignal] | None:
        # Don't enter twice
        if self._entered:
            return None

        # Session was skipped by BTC trend filter
        if self._session_skipped:
            return None

        # Wait for BTC trend computation (window_2 must have elapsed)
        if not self._btc_trend_checked:
            return None

        # Time remaining filter (from backtest: only enter when time_remaining <= threshold)
        if self.time_remaining_filter is not None:
            if ctx.time_remaining_s > self.time_remaining_filter:
                return None

        # Evaluate entry for each token — prefer the token matching BTC direction
        preferred_side = self._btc_trend_direction  # "UP" or "DOWN"

        # Try preferred side first
        for token_id, mkt in ctx.tokens.items():
            if _price_side(mkt.mid_price) == preferred_side:
                signal = self._evaluate_entry(token_id, mkt, ctx)
                if signal:
                    return [signal]

        # Fallback: try the other side
        for token_id, mkt in ctx.tokens.items():
            if _price_side(mkt.mid_price) != preferred_side:
                signal = self._evaluate_entry(token_id, mkt, ctx)
                if signal:
                    return [signal]

        return None

    def should_close(self, ctx: LiveMarketContext) -> LiveSignal | None:
        if not self._entered or not self._entry_token:
            return None

        token_id = self._entry_token
        mkt = ctx.tokens.get(token_id)
        if not mkt:
            return None

        shares = ctx.positions.get(token_id, 0)
        if shares <= 0:
            return None

        ref_price = mkt.anchor_price if mkt.anchor_price > 0 else mkt.mid_price
        entry_side = self._entry_side or _price_side(ref_price)

        # Only act on same price side as entry
        if _price_side(ref_price) != entry_side:
            return None

        effective = _effective_price(ref_price, entry_side)

        # Take profit
        if self.tp_price > 0 and effective >= self.tp_price:
            logger.info("Take profit triggered at %.4f (target %.4f)", effective, self.tp_price)
            return LiveSignal(
                token_id=token_id,
                side="SELL",
                amount_usdc=shares,
                limit_price=mkt.best_bid if mkt.best_bid > 0 else ref_price,
                reason="take_profit",
            )

        # Stop loss
        if self.sl_price > 0 and effective <= self.sl_price:
            logger.info("Stop loss triggered at %.4f (limit %.4f)", effective, self.sl_price)
            return LiveSignal(
                token_id=token_id,
                side="SELL",
                amount_usdc=shares,
                limit_price=mkt.best_bid if mkt.best_bid > 0 else ref_price,
                reason="stop_loss",
            )

        # Force close near expiry
        if ctx.time_remaining_s <= self.force_close_remaining_s:
            cost_basis = self._entry_price
            sell_price = mkt.best_bid if mkt.best_bid > 0 else ref_price
            profit_per_share = sell_price - cost_basis
            total_profit = profit_per_share * shares

            if total_profit < self.min_close_profit:
                logger.info(
                    "Force close skipped — profit $%.4f < $%.4f, holding to settlement",
                    total_profit, self.min_close_profit,
                )
                return None

            logger.info("Force close: %.2f remaining, profit $%.4f", ctx.time_remaining_s, total_profit)
            return LiveSignal(
                token_id=token_id,
                side="SELL",
                amount_usdc=shares,
                limit_price=sell_price,
                reason="force_close",
            )

        return None

    def on_fill(self, fill: LiveFill) -> None:
        if fill.side == "BUY":
            self._entered = True
            self._entry_token = fill.token_id
            self._entry_side = _price_side(fill.avg_price)
            self._entry_price = fill.avg_price
            logger.info(
                "Entry fill: %s @ %.4f (%s side)",
                fill.token_id[:12], fill.avg_price, self._entry_side,
            )
        elif fill.side == "SELL":
            pnl = (fill.avg_price - self._entry_price) * fill.filled_shares
            logger.info("Exit fill: %s @ %.4f, PnL: $%.4f", fill.token_id[:12], fill.avg_price, pnl)

    def on_session_end(self, result: SessionResult) -> None:
        logger.info(
            "Session %s ended — trade_pnl: $%.4f, settlement_pnl: $%.4f, total: $%.4f | skipped=%s",
            result.session.slug, result.trade_pnl, result.settlement_pnl, result.total_pnl,
            self._session_skipped,
        )

    def on_error(self, error: TradeError) -> ErrorAction:
        if error.has_position:
            logger.warning("Error with position held: %s — retrying", error.message)
            return ErrorAction.RETRY
        logger.warning("Error without position: %s — cancelling", error.message)
        return ErrorAction.CANCEL

    # ── Entry evaluation ──────────────────────────────────────

    def _evaluate_entry(
        self, token_id: str, mkt, ctx: LiveMarketContext,
    ) -> LiveSignal | None:
        mid = mkt.mid_price
        if mid <= 0:
            return None

        # Price filter
        if mid < self.min_price:
            return None

        # Profit margin check (mirrors backtest: gap between TP target and entry ask)
        entry_ask = mkt.best_ask if mkt.best_ask > 0 else mid
        tp_target = self.tp_price if self.tp_price > 0 else 1.0
        if abs(tp_target - entry_ask) < self.profit_margin:
            return None

        # Position sizing
        target_pct = (self.position_min_pct + self.position_max_pct) / 2
        buy_budget = ctx.balance * target_pct
        if buy_budget < 10.0:  # minimum trade $10
            buy_budget = min(ctx.balance, 10.0)
            if buy_budget < 10.0:
                return None

        price_for_order = entry_ask

        logger.info(
            "Entry signal: %s | price=%.4f ask=%.4f budget=$%.2f direction=%s amp=%.6f",
            token_id[:12], mid, entry_ask, buy_budget,
            self._btc_trend_direction, self._btc_amplitude,
        )

        return LiveSignal(
            token_id=token_id,
            side="BUY",
            amount_usdc=buy_budget,
            limit_price=price_for_order,
            reason=f"entry_btc_{self._btc_trend_direction.lower()}",
        )
