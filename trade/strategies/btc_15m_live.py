"""BTC 15-minute live trading strategy.

Entry: BTC two-window sita gated, composite branch selection by amplitude.
Exit: take_profit, stop_loss, force_close near expiry.
Config comes from Strategy service — no hardcoded defaults.
"""

from __future__ import annotations

import logging

from models.types import (
    LiveFill,
    LiveMarketContext,
    LiveSignal,
    SessionInfo,
    SessionResult,
)

logger = logging.getLogger(__name__)


def _price_side(price: float) -> str:
    return "UP" if price >= 0.5 else "DOWN"


def _effective_price(price: float, side: str) -> float:
    return price if side == "UP" else (1.0 - price)


class Btc15mLiveStrategy:

    def on_session_start(self, session: SessionInfo, config: dict) -> None:
        self._session = session
        cfg = config

        # Entry filters
        self.min_price: float = float(cfg.get("min_price", 0))
        self.profit_margin: float = float(cfg.get("profit_margin", 0))

        # Position sizing
        self.position_min_pct: float = float(cfg.get("position_min_pct", 0.10))
        self.position_max_pct: float = float(cfg.get("position_max_pct", 0.30))

        # Risk management
        self.tp_price: float = float(cfg.get("take_profit_price", 0))
        self.sl_price: float = float(cfg.get("stop_loss_price", 0))
        self.force_close_remaining_s: int = int(cfg.get("force_close_remaining_s", 120))
        self.min_close_profit: float = float(cfg.get("min_close_profit", 0))

        # State
        self._entered = False
        self._entry_token: str | None = None
        self._entry_side: str | None = None
        self._entry_price: float = 0.0
        self.session_skipped = False
        self.btc_trend_direction: str = "UNKNOWN"
        self.btc_amplitude: float = 0.0

    def on_btc_trend_result(self, trend_info: dict) -> None:
        self.btc_trend_direction = trend_info.get("direction", "UNKNOWN")
        self.btc_amplitude = trend_info.get("amplitude", 0.0)
        if not trend_info.get("passed", False):
            self.session_skipped = True

    def on_market_update(self, ctx: LiveMarketContext) -> list[LiveSignal] | None:
        if self._entered or self.session_skipped:
            return None

        preferred_side = self.btc_trend_direction
        # Try preferred side first, then fallback
        for token_id, mkt in ctx.tokens.items():
            if _price_side(mkt.mid_price) == preferred_side:
                signal = self._evaluate_entry(token_id, mkt, ctx)
                if signal:
                    return [signal]
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
        if _price_side(ref_price) != entry_side:
            return None

        effective = _effective_price(ref_price, entry_side)
        sell_price = mkt.best_bid if mkt.best_bid > 0 else ref_price

        # Take profit
        if self.tp_price > 0 and effective >= self.tp_price:
            return LiveSignal(token_id=token_id, side="SELL", amount_usdc=shares,
                              limit_price=sell_price, reason="take_profit")

        # Stop loss
        if self.sl_price > 0 and effective <= self.sl_price:
            return LiveSignal(token_id=token_id, side="SELL", amount_usdc=shares,
                              limit_price=sell_price, reason="stop_loss")

        # Force close near expiry — only if profitable, let stop-loss handle losses
        if ctx.time_remaining_s <= self.force_close_remaining_s:
            profit = (sell_price - self._entry_price) * shares
            if profit > 0:  # Only close if profitable
                return LiveSignal(token_id=token_id, side="SELL", amount_usdc=shares,
                                  limit_price=sell_price, reason="force_close")
            # If losing, let stop-loss or settlement handle it
            return None

        return None

    def on_fill(self, fill: LiveFill) -> None:
        if fill.side == "BUY":
            self._entered = True
            self._entry_token = fill.token_id
            self._entry_side = _price_side(fill.avg_price)
            self._entry_price = fill.avg_price

    def on_session_end(self, result: SessionResult) -> None:
        logger.info(
            "Session %s — trade_pnl=$%.4f settlement_pnl=$%.4f total=$%.4f skipped=%s",
            result.session.slug, result.trade_pnl, result.settlement_pnl,
            result.total_pnl, self.session_skipped,
        )

    # ── Entry evaluation ──────────────────────────────────────

    def _evaluate_entry(self, token_id: str, mkt, ctx: LiveMarketContext) -> LiveSignal | None:
        mid = mkt.mid_price
        if mid <= 0 or mid < self.min_price:
            return None

        entry_ask = mkt.best_ask if mkt.best_ask > 0 else mid
        tp_target = self.tp_price if self.tp_price > 0 else 1.0
        if self.profit_margin > 0 and abs(tp_target - entry_ask) < self.profit_margin:
            return None

        target_pct = (self.position_min_pct + self.position_max_pct) / 2
        buy_budget = ctx.balance * target_pct
        if buy_budget < 10.0:
            buy_budget = min(ctx.balance, 10.0)
            if buy_budget < 10.0:
                return None

        logger.info(
            "Entry: %s price=%.4f ask=%.4f budget=$%.2f dir=%s amp=%.6f",
            token_id[:12], mid, entry_ask, buy_budget,
            self.btc_trend_direction, self.btc_amplitude,
        )
        return LiveSignal(
            token_id=token_id, side="BUY", amount_usdc=buy_budget,
            limit_price=entry_ask, reason=f"entry_btc_{self.btc_trend_direction.lower()}",
        )
