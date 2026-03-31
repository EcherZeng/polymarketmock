"""统一策略基类 — 实现所有策略共享的止盈/止损/强制平仓/连续亏损降仓规则。"""

from __future__ import annotations

import logging
import math
from abc import abstractmethod

from core.base_strategy import BaseStrategy
from core.types import FillInfo, Signal, TickContext

logger = logging.getLogger(__name__)


class UnifiedBaseStrategy(BaseStrategy):
    """所有策略的统一基类，封装止盈/止损/强制平仓/连续亏损降仓逻辑。

    子类实现 init_strategy() 和 compute_entry_signals() 即可。
    统一规则参数从 strategy_presets.json → unified_rules 读取（通过 registry 注入 default_config）。
    """

    # ── BaseStrategy interface ───────────────────────────────────────────────

    def on_init(self, config: dict) -> None:
        # Unified rule parameters
        self._tp_price: float = config.get("take_profit_price", 0.99)
        self._sl_price: float = config.get("stop_loss_price", 0.65)
        self._force_close_seconds: int = int(config.get("force_close_remaining_seconds", 30))
        self._consec_loss_threshold: int = int(config.get("consecutive_loss_threshold", 3))
        self._loss_reduction_pct: float = config.get("loss_position_reduction_pct", 0.5)

        # Internal state
        self._consecutive_losses: int = 0
        self._position_scale: float = 1.0
        self._entry_prices: dict[str, float] = {}

        # Delegate to child
        self.init_strategy(config)

    def on_tick(self, ctx: TickContext) -> list[Signal]:
        signals: list[Signal] = []

        # ── 1. Force close near expiry (remaining <= 30s) ───────────────────
        remaining_seconds = ctx.total_ticks - ctx.index  # 1 tick ≈ 1 second
        if remaining_seconds <= self._force_close_seconds:
            for token_id, qty in ctx.positions.items():
                if qty > 0:
                    signals.append(Signal(token_id=token_id, side="SELL", amount=qty))
            return signals

        # ── 2. Take profit / Stop loss ──────────────────────────────────────
        for token_id, snapshot in ctx.tokens.items():
            qty = ctx.positions.get(token_id, 0)
            if qty <= 0:
                continue
            mid = snapshot.mid_price
            if mid >= self._tp_price or mid <= self._sl_price:
                signals.append(Signal(token_id=token_id, side="SELL", amount=qty))

        if signals:
            return signals

        # ── 3. Delegate to child strategy for entry signals ─────────────────
        child_signals = self.compute_entry_signals(ctx)

        # Apply position scale reduction from consecutive losses
        if self._position_scale < 1.0 and child_signals:
            for sig in child_signals:
                sig.amount = max(1.0, math.floor(sig.amount * self._position_scale))

        return child_signals

    def on_fill(self, fill: FillInfo) -> None:
        if fill.side == "BUY":
            self._entry_prices[fill.token_id] = fill.avg_price
        elif fill.side == "SELL":
            entry = self._entry_prices.pop(fill.token_id, 0)
            if entry > 0:
                if fill.avg_price < entry:
                    self._consecutive_losses += 1
                    if self._consecutive_losses >= self._consec_loss_threshold:
                        self._position_scale *= (1.0 - self._loss_reduction_pct)
                else:
                    self._consecutive_losses = 0
        self.on_strategy_fill(fill)

    def on_end(self) -> dict:
        child_summary = self.end_strategy()
        return {
            **child_summary,
            "unified_rules": {
                "consecutive_losses": self._consecutive_losses,
                "position_scale": round(self._position_scale, 4),
            },
        }

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
