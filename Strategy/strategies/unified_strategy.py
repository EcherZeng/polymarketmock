"""统一策略 — 所有预设策略共用的参数化入场逻辑。

通过 strategy_presets.json 中的特性开关控制检查项:
  use_momentum_check   — 10 分钟动量检查 (solid_core, main_force)
  use_direction_check  — 10 分钟方向一致性检查 (high_freq_coverage)
  use_std_check        — 波动率标准差检查 (solid_core, main_force)
  use_drawdown_check   — 窗口最大回撤检查 (solid_core, main_force)
  use_amplitude_check  — 振幅范围检查
  use_reverse_check    — 反转检测检查

统一规则 (TP/SL/强制平仓/降仓) 由 UnifiedBaseStrategy 基类处理。
"""

from __future__ import annotations

import math

from core.types import Signal, TickContext
from core.unified_base import UnifiedBaseStrategy


class UnifiedStrategy(UnifiedBaseStrategy):
    name = "unified"
    description = "统一参数化策略 — 通过预设配置驱动不同入场条件组合"
    version = "0.2.0"

    def init_strategy(self, config: dict) -> None:
        # ── Price & time ──
        self.min_price: float = config.get("min_price", 0.85)
        self.time_remaining_ratio: float = config.get("time_remaining_ratio", 0.333)

        # ── Feature toggles ──
        self.use_momentum: bool = config.get("use_momentum_check", True)
        self.use_direction: bool = config.get("use_direction_check", False)
        self.use_std: bool = config.get("use_std_check", True)
        self.use_drawdown: bool = config.get("use_drawdown_check", True)
        self.use_amplitude: bool = config.get("use_amplitude_check", True)
        self.use_reverse: bool = config.get("use_reverse_check", True)

        # ── Momentum params ──
        self.momentum_window: int = int(config.get("momentum_window", 600))
        self.momentum_min: float = config.get("momentum_min", 0.0020)

        # ── Direction params ──
        self.direction_window: int = int(config.get("direction_window", 600))

        # ── Volatility / amplitude params ──
        self.volatility_window: int = int(config.get("volatility_window", 900))
        self.amplitude_min: float = config.get("amplitude_min", 0.0012)
        self.amplitude_max: float = config.get("amplitude_max", 0.0022)
        self.max_std: float = config.get("max_std", 0.0015)
        self.max_drawdown_limit: float = config.get("max_drawdown", 0.0010)

        # ── Position sizing ──
        self.position_min_pct: float = config.get("position_min_pct", 0.10)
        self.position_max_pct: float = config.get("position_max_pct", 0.30)

        # ── Reverse detection ──
        self.reverse_tick_window: int = int(config.get("reverse_tick_window", 30))
        self.reverse_threshold: float = config.get("reverse_threshold", 0.002)

        self._entered: bool = False
        self._entry_count: int = 0

    # ── Entry logic ──────────────────────────────────────────────────────────

    def compute_entry_signals(self, ctx: TickContext) -> list[Signal]:
        if self._entered:
            return []

        # 1. Time gate
        remaining_ratio = (ctx.total_ticks - ctx.index) / ctx.total_ticks if ctx.total_ticks > 0 else 1.0
        if remaining_ratio > self.time_remaining_ratio:
            return []

        # Minimum history: only require reverse_tick_window (30) as hard floor.
        # Individual checks (momentum, volatility, etc.) use slicing that
        # naturally adapts to shorter histories — no need to gate on the
        # largest window which may exceed the market's total duration.
        min_history = self.reverse_tick_window

        for token_id, snapshot in ctx.tokens.items():
            mid = snapshot.mid_price
            if mid <= 0 or mid < self.min_price:
                continue

            history = ctx.price_history.get(token_id, [])
            if len(history) < min_history:
                continue

            # 2. Momentum check (optional)
            if self.use_momentum:
                momentum_slice = history[-self.momentum_window:]
                if momentum_slice[0] == 0:
                    continue
                momentum = (momentum_slice[-1] - momentum_slice[0]) / momentum_slice[0]
                if momentum < self.momentum_min:
                    continue

            # 3. Direction consistency check (optional)
            if self.use_direction:
                dir_slice = history[-self.direction_window:]
                up_count = sum(1 for i in range(1, len(dir_slice)) if dir_slice[i] > dir_slice[i - 1])
                down_count = sum(1 for i in range(1, len(dir_slice)) if dir_slice[i] < dir_slice[i - 1])
                if up_count + down_count == 0 or up_count <= down_count:
                    continue

            # 4. Amplitude check (optional)
            if self.use_amplitude:
                vol_window = min(self.volatility_window, len(history))
                vol_slice = history[-vol_window:]
                high, low = max(vol_slice), min(vol_slice)
                if low == 0:
                    continue
                amplitude = (high - low) / low
                if amplitude < self.amplitude_min or amplitude > self.amplitude_max:
                    continue
            else:
                vol_window = min(self.volatility_window, len(history))
                vol_slice = history[-vol_window:]

            # 5. Std check (optional)
            if self.use_std:
                mean_price = sum(vol_slice) / len(vol_slice)
                if mean_price == 0:
                    continue
                variance = sum((p - mean_price) ** 2 for p in vol_slice) / len(vol_slice)
                std_pct = math.sqrt(variance) / mean_price
                if std_pct > self.max_std:
                    continue

            # 6. Max drawdown check (optional)
            if self.use_drawdown:
                peak = vol_slice[0]
                max_dd = 0.0
                for p in vol_slice:
                    if p > peak:
                        peak = p
                    dd = (peak - p) / peak if peak > 0 else 0.0
                    if dd > max_dd:
                        max_dd = dd
                if max_dd > self.max_drawdown_limit:
                    continue

            # 7. Reverse movement check (optional)
            if self.use_reverse:
                reverse_window = min(self.reverse_tick_window, len(history))
                recent = history[-reverse_window:]
                has_reverse = any(
                    recent[i - 1] > 0 and (recent[i] - recent[i - 1]) / recent[i - 1] < -self.reverse_threshold
                    for i in range(1, len(recent))
                )
                if has_reverse:
                    continue

            # 8. Position sizing
            target_pct = (self.position_min_pct + self.position_max_pct) / 2
            buy_budget = ctx.balance * target_pct
            if buy_budget <= 0 or mid <= 0:
                continue

            amount = math.floor(buy_budget / mid)
            if amount <= 0:
                continue

            self._entered = True
            self._entry_count += 1
            return [Signal(token_id=token_id, side="BUY", amount=float(amount))]

        return []

    def end_strategy(self) -> dict:
        return {
            "entered": self._entered,
            "entry_count": self._entry_count,
            "strategy_type": "hold_to_settlement",
        }
