"""BTC 15-minute live trading strategy.

Adapted from the backtest UnifiedStrategy parameter system.
Observes for the first ~10 minutes, then enters when conditions are met.
Holds to settlement unless take-profit/stop-loss triggers.
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
    description = "BTC 15-minute session — observe then enter, hold to settlement"
    version = "1.0.0"
    default_config = {
        "min_price": 0.85,
        "observation_s": 600,           # 10 minutes observation period
        "profit_margin": 0.03,
        "position_min_pct": 0.10,
        "position_max_pct": 0.30,
        "take_profit_price": 0.95,
        "stop_loss_price": 0.0,         # 0 = disabled
        "force_close_remaining_s": 120,  # 2 minutes before end
        "min_close_profit": 0.02,       # don't close if profit < $0.02
    }

    def on_session_start(self, session: SessionInfo, config: dict) -> None:
        self._session = session
        self._cfg = {**self.default_config, **config}

        self.min_price: float = self._cfg["min_price"]
        self.observation_s: int = int(self._cfg["observation_s"])
        self.profit_margin: float = self._cfg["profit_margin"]
        self.position_min_pct: float = self._cfg["position_min_pct"]
        self.position_max_pct: float = self._cfg["position_max_pct"]
        self.tp_price: float = self._cfg["take_profit_price"]
        self.sl_price: float = self._cfg["stop_loss_price"]
        self.force_close_remaining_s: int = int(self._cfg["force_close_remaining_s"])
        self.min_close_profit: float = self._cfg["min_close_profit"]

        self._entered = False
        self._entry_token: str | None = None
        self._entry_side: str | None = None
        self._entry_price: float = 0.0

        logger.info(
            "Strategy started for %s | min_price=%.2f obs=%ds tp=%.2f sl=%.2f",
            session.slug, self.min_price, self.observation_s,
            self.tp_price, self.sl_price,
        )

    def on_market_update(self, ctx: LiveMarketContext) -> list[LiveSignal] | None:
        # Don't enter twice
        if self._entered:
            return None

        # Observation period — collect data, don't trade
        elapsed = ctx.session.duration_s - ctx.time_remaining_s
        if elapsed < self.observation_s:
            return None

        # Evaluate entry for each token
        for token_id, mkt in ctx.tokens.items():
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
            # Calculate expected profit from closing
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
            "Session %s ended — trade_pnl: $%.4f, settlement_pnl: $%.4f, total: $%.4f",
            result.session.slug, result.trade_pnl, result.settlement_pnl, result.total_pnl,
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

        # Profit margin check
        entry_ask = mkt.best_ask if mkt.best_ask > 0 else mid
        tp_target = self.tp_price if self.tp_price > 0 else 1.0
        if abs(tp_target - entry_ask) < self.profit_margin:
            return None

        # Price trend check — use accumulated history
        history = ctx.price_history.get(token_id, [])
        if len(history) >= 10:
            recent = history[-10:]
            early = history[:10]
            avg_recent = sum(recent) / len(recent)
            avg_early = sum(early) / len(early)
            # Require price to be trending up (for UP side)
            side = _price_side(mid)
            if side == "UP" and avg_recent < avg_early:
                return None
            if side == "DOWN" and avg_recent > avg_early:
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
            "Entry signal: %s | price=%.4f ask=%.4f budget=$%.2f",
            token_id[:12], mid, entry_ask, buy_budget,
        )

        return LiveSignal(
            token_id=token_id,
            side="BUY",
            amount_usdc=buy_budget,
            limit_price=price_for_order,
            reason="entry",
        )
