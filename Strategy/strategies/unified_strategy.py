"""统一策略 — 所有预设策略共用的参数化入场逻辑。

通过 strategy_presets.json 中的参数存在性控制入场条件（选中即启用）:
  min_price               — 入场最低价格过滤
  time_remaining_s        — 剩余时间门控（秒）

仓位管理:
  position_min_pct / position_max_pct — 仓位比例区间

统一规则 (TP/SL/强制平仓) 由 UnifiedBaseStrategy 基类处理。
"""

from __future__ import annotations

import math

from core.types import Signal, TickContext, param_active
from core.unified_base import UnifiedBaseStrategy


class UnifiedStrategy(UnifiedBaseStrategy):
    name = "unified"
    description = "统一参数化策略 — 通过预设配置驱动入场条件"
    version = "0.3.0"

    def init_strategy(self, config: dict) -> None:
        self._cfg = config
        # ── Price & time ── (None = filter disabled)
        self.min_price: float | None = config.get("min_price") if param_active(config, "min_price") else None
        self.time_remaining_s: int | None = int(config.get("time_remaining_s")) if param_active(config, "time_remaining_s") else None

        # ── Position sizing ──
        self.position_min_pct: float = config.get("position_min_pct", 0.10)
        self.position_max_pct: float = config.get("position_max_pct", 0.30)

        self._entered_tokens: set[str] = set()

    # ── Entry logic ──────────────────────────────────────────────────────────

    def compute_entry_signals(self, ctx: TickContext) -> list[Signal]:
        # Skip if all tokens already entered
        if len(self._entered_tokens) >= len(ctx.tokens):
            return []

        # 1. Time gate — skip if param not active
        if self.time_remaining_s is not None:
            remaining_seconds = ctx.total_ticks - ctx.index  # 1 tick ≈ 1 second
            if remaining_seconds > self.time_remaining_s:
                return []

        for token_id, snapshot in ctx.tokens.items():
            if token_id in self._entered_tokens:
                continue

            mid = snapshot.mid_price
            if mid <= 0:
                continue

            # 2. Price filter
            if self.min_price is not None and mid < self.min_price:
                continue

            # 3. Position sizing
            target_pct = (self.position_min_pct + self.position_max_pct) / 2
            buy_budget = ctx.balance * target_pct
            price_for_sizing = snapshot.best_ask if snapshot.best_ask > 0 else mid
            if buy_budget <= 0 or price_for_sizing <= 0:
                continue

            amount = math.floor(buy_budget / price_for_sizing)
            if amount <= 0:
                continue

            self._entered_tokens.add(token_id)
            return [Signal(token_id=token_id, side="BUY", amount=float(amount), max_cost=buy_budget)]

        return []

    def end_strategy(self) -> dict:
        return {
            "entered": len(self._entered_tokens) > 0,
            "entered_tokens": sorted(self._entered_tokens),
            "strategy_type": "hold_to_settlement",
        }
