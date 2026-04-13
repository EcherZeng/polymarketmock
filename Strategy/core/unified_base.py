"""统一策略基类 — 实现所有策略共享的止盈/止损/强制平仓规则。"""

from __future__ import annotations

import logging
from abc import abstractmethod

from core.base_strategy import BaseStrategy
from core.types import FillInfo, Signal, TickContext, param_active

logger = logging.getLogger(__name__)


class UnifiedBaseStrategy(BaseStrategy):
    """所有策略的统一基类，封装止盈/止损/强制平仓逻辑。

    子类实现 init_strategy() 和 compute_entry_signals() 即可。
    统一规则参数从 strategy_presets.json → unified_rules 读取（通过 registry 注入 default_config）。
    """

    # ── BaseStrategy interface ───────────────────────────────────────────────

    def on_init(self, config: dict) -> None:
        self._config = config
        # Unified rule parameters — only set when activated
        self._tp_price: float | None = config.get("take_profit_price") if param_active(config, "take_profit_price") else None
        self._sl_price: float | None = config.get("stop_loss_price") if param_active(config, "stop_loss_price") else None
        self._force_close_seconds: int | None = int(config["force_close_remaining_seconds"]) if param_active(config, "force_close_remaining_seconds") else None

        # Entry side tracking for TP/SL price comparison
        self._entry_price_sides: dict[str, str] = {}

        # Delegate to child
        self.init_strategy(config)

    @staticmethod
    def _make_exit_signal(token_id: str, qty: float) -> Signal:
        """Build an exit SELL signal (ideal mode)."""
        return Signal(
            token_id=token_id,
            side="SELL",
            amount=qty,
            sell_mode="ideal",
        )

    def on_tick(self, ctx: TickContext) -> list[Signal]:
        signals: list[Signal] = []

        # ── 1. Force close near expiry (remaining <= threshold) ──────────────
        remaining_seconds = ctx.total_ticks - ctx.index  # 1 tick ≈ 1 second
        if self._force_close_seconds is not None and remaining_seconds <= self._force_close_seconds:
            for token_id, qty in ctx.positions.items():
                if qty > 0:
                    entry_side = self._entry_price_sides.get(token_id)
                    snapshot = ctx.tokens.get(token_id)
                    if snapshot is not None and entry_side is not None:
                        current_side = self._price_side(snapshot.mid_price)
                        if current_side != entry_side:
                            continue
                    signals.append(self._make_exit_signal(token_id, qty))
            return signals

        # ── 2. Take profit / Stop loss (per-token, absolute price) ──────────
        for token_id, snapshot in ctx.tokens.items():
            qty = ctx.positions.get(token_id, 0)
            if qty <= 0:
                continue
            mid = snapshot.mid_price
            # Use anchor_price for TP/SL when available (more reliable than raw mid)
            ref_price = snapshot.anchor_price if snapshot.anchor_price > 0 else mid
            entry_side = self._entry_price_sides.get(token_id)
            if entry_side is not None and self._price_side(ref_price) != entry_side:
                continue

            price_side = entry_side or self._price_side(ref_price)
            effective_ref = self._effective_price(ref_price, price_side)
            should_close = False

            if self._tp_price is not None and effective_ref >= self._tp_price:
                should_close = True
            if self._sl_price is not None and self._sl_price > 0 and effective_ref <= self._sl_price:
                should_close = True

            if should_close:
                signals.append(self._make_exit_signal(token_id, qty))

        if signals:
            return signals

        # ── 3. Delegate to child strategy for entry signals ─────────────────
        return self.compute_entry_signals(ctx)

    def on_fill(self, fill: FillInfo) -> None:
        if fill.side == "BUY":
            self._entry_price_sides[fill.token_id] = self._price_side(fill.avg_price)
        elif fill.side == "SELL":
            if fill.position_after <= 0:
                self._entry_price_sides.pop(fill.token_id, None)
        self.on_strategy_fill(fill)

    def on_end(self) -> dict:
        return self.end_strategy()

    # ── Child hooks (subclass implements these) ──────────────────────────────

    @abstractmethod
    def init_strategy(self, config: dict) -> None:
        """Initialize strategy-specific parameters."""
        ...

    @abstractmethod
    def compute_entry_signals(self, ctx: TickContext) -> list[Signal]:
        """Compute entry signals (risk management already handled by base)."""
        ...

    def on_strategy_fill(self, fill: FillInfo) -> None:
        """Optional: react to fills in child strategy."""
        pass

    def end_strategy(self) -> dict:
        """Optional: return child summary at end."""
        return {}

    @staticmethod
    def _price_side(price: float) -> str:
        return "UP" if price >= 0.5 else "DOWN"

    @staticmethod
    def _effective_price(price: float, side: str) -> float:
        return price if side == "UP" else (1.0 - price)
