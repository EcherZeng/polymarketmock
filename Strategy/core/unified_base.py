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
        # Unified rule parameters — absolute price mode
        self._tp_price: float = config.get("take_profit_price", 0.99)
        self._sl_price: float = config.get("stop_loss_price", 0.65)
        # Relative pct mode — anchored to per-token entry price
        self._tp_pct: float = config.get("take_profit_pct", 0) or 0
        self._sl_pct: float = config.get("stop_loss_pct", 0) or 0
        self._force_close_seconds: int = int(config.get("force_close_remaining_seconds", 30))
        self._consec_loss_threshold: int = int(config.get("consecutive_loss_threshold", 3))
        self._loss_reduction_pct: float = config.get("loss_position_reduction_pct", 0.5)

        # Exit sell mode: ideal (mid price) vs orderbook (VWAP with protections)
        self._exit_use_orderbook: bool = bool(config.get("exit_use_orderbook_mode", False))
        self._exit_min_sell_price: float = float(config.get("exit_min_sell_price", 0.0))
        self._exit_reduction_pct: float = float(config.get("exit_reduction_pct", 1.0))

        # Internal state
        self._consecutive_losses: int = 0
        self._position_scale: float = 1.0
        self._entry_effective_prices: dict[str, float] = {}
        self._entry_price_sides: dict[str, str] = {}

        # Delegate to child
        self.init_strategy(config)

    def _make_exit_signal(self, token_id: str, qty: float) -> Signal:
        """Build an exit SELL signal with the configured sell mode."""
        if self._exit_use_orderbook:
            amount = max(1.0, qty * self._exit_reduction_pct)
            return Signal(
                token_id=token_id,
                side="SELL",
                amount=amount,
                sell_mode="orderbook",
                min_sell_price=self._exit_min_sell_price if self._exit_min_sell_price > 0 else None,
            )
        else:
            return Signal(
                token_id=token_id,
                side="SELL",
                amount=qty,
                sell_mode="ideal",
            )

    def on_tick(self, ctx: TickContext) -> list[Signal]:
        signals: list[Signal] = []

        # ── 1. Force close near expiry (remaining <= 30s) ───────────────────
        remaining_seconds = ctx.total_ticks - ctx.index  # 1 tick ≈ 1 second
        if remaining_seconds <= self._force_close_seconds:
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

        # ── 2. Take profit / Stop loss (per-token, pct + absolute) ────────
        for token_id, snapshot in ctx.tokens.items():
            qty = ctx.positions.get(token_id, 0)
            if qty <= 0:
                continue
            mid = snapshot.mid_price
            entry_side = self._entry_price_sides.get(token_id)
            if entry_side is not None and self._price_side(mid) != entry_side:
                continue

            price_side = entry_side or self._price_side(mid)
            effective_mid = self._effective_price(mid, price_side)
            entry = self._entry_effective_prices.get(token_id)
            should_close = False

            # Relative pct mode — anchored to entry price per token
            if entry is not None and entry > 0:
                if self._tp_pct > 0 and effective_mid >= entry * (1 + self._tp_pct):
                    should_close = True
                if self._sl_pct > 0 and effective_mid <= entry * (1 - self._sl_pct):
                    should_close = True

            # Absolute price mode
            if effective_mid >= self._tp_price:
                should_close = True
            if self._sl_price > 0 and effective_mid <= self._sl_price:
                should_close = True

            if should_close:
                signals.append(self._make_exit_signal(token_id, qty))

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
            price_side = self._price_side(fill.avg_price)
            self._entry_price_sides[fill.token_id] = price_side
            self._entry_effective_prices[fill.token_id] = self._effective_price(fill.avg_price, price_side)
        elif fill.side == "SELL":
            entry_side = self._entry_price_sides.get(fill.token_id)
            if entry_side is None:
                entry_side = self._price_side(fill.avg_price)
            entry = self._entry_effective_prices.get(fill.token_id, 0)
            exit_effective_price = self._effective_price(fill.avg_price, entry_side)
            if entry > 0:
                if exit_effective_price < entry:
                    self._consecutive_losses += 1
                    if self._consecutive_losses >= self._consec_loss_threshold:
                        self._position_scale *= (1.0 - self._loss_reduction_pct)
                else:
                    self._consecutive_losses = 0

            if fill.position_after <= 0:
                self._entry_effective_prices.pop(fill.token_id, None)
                self._entry_price_sides.pop(fill.token_id, None)
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

    @staticmethod
    def _price_side(price: float) -> str:
        return "UP" if price >= 0.5 else "DOWN"

    @staticmethod
    def _effective_price(price: float, side: str) -> float:
        return price if side == "UP" else (1.0 - price)
