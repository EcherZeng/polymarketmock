"""稳固核心策略 — 高概率二元市场临近到期买入持有。

入场条件:
  - 剩余时间 <= 总时间的 1/3
  - 市场价格 >= 0.88
  - 过去 10 分钟涨幅 >= 0.25%
  - 15 分钟振幅在 0.15% ~ 0.20%
  - 波动率(标准差) <= 0.12%
  - 窗口内最大回撤 <= 0.08%
  - 无明显反向波动(最近 N 秒无单次跌幅 > 阈值)
仓位: 20% ~ 30% (余额)
持有到结算, 不主动卖出。
"""

from __future__ import annotations

import math

from core.base_strategy import BaseStrategy
from core.types import FillInfo, Signal, TickContext


class SolidCoreStrategy(BaseStrategy):
    name = "solid_core"
    description = "稳固核心 — 高概率二元市场临近到期时低波动顺势买入并持有到结算"
    version = "0.1.0"
    default_config = {
        "min_price": 0.88,
        "time_remaining_ratio": 0.333,
        "momentum_window": 600,
        "momentum_min": 0.0025,
        "volatility_window": 900,
        "amplitude_min": 0.0015,
        "amplitude_max": 0.0020,
        "max_std": 0.0012,
        "max_drawdown": 0.0008,
        "position_min_pct": 0.20,
        "position_max_pct": 0.30,
        "reverse_tick_window": 30,
        "reverse_threshold": 0.002,
    }

    def on_init(self, config: dict) -> None:
        self.min_price = config.get("min_price", 0.88)
        self.time_remaining_ratio = config.get("time_remaining_ratio", 0.333)
        self.momentum_window = int(config.get("momentum_window", 600))
        self.momentum_min = config.get("momentum_min", 0.0025)
        self.volatility_window = int(config.get("volatility_window", 900))
        self.amplitude_min = config.get("amplitude_min", 0.0015)
        self.amplitude_max = config.get("amplitude_max", 0.0020)
        self.max_std = config.get("max_std", 0.0012)
        self.max_drawdown_limit = config.get("max_drawdown", 0.0008)
        self.position_min_pct = config.get("position_min_pct", 0.20)
        self.position_max_pct = config.get("position_max_pct", 0.30)
        self.reverse_tick_window = int(config.get("reverse_tick_window", 30))
        self.reverse_threshold = config.get("reverse_threshold", 0.002)

        self._entered = False
        self._entry_count = 0

    def on_tick(self, ctx: TickContext) -> list[Signal]:
        # Already entered — hold to settlement, no further action
        if self._entered:
            return []

        # ── 1. Time check: only enter in final 1/3 of event ──
        remaining_ratio = (ctx.total_ticks - ctx.index) / ctx.total_ticks if ctx.total_ticks > 0 else 1.0
        if remaining_ratio > self.time_remaining_ratio:
            return []

        signals: list[Signal] = []

        for token_id, snapshot in ctx.tokens.items():
            mid = snapshot.mid_price
            if mid <= 0:
                continue

            # ── 2. Price threshold ──
            if mid < self.min_price:
                continue

            history = ctx.price_history.get(token_id, [])
            if len(history) < self.momentum_window:
                continue

            # ── 3. 10-minute momentum ──
            momentum_slice = history[-self.momentum_window:]
            if momentum_slice[0] == 0:
                continue
            momentum = (momentum_slice[-1] - momentum_slice[0]) / momentum_slice[0]
            if momentum < self.momentum_min:
                continue

            # ── 4. 15-minute amplitude and volatility ──
            vol_window = min(self.volatility_window, len(history))
            vol_slice = history[-vol_window:]

            high = max(vol_slice)
            low = min(vol_slice)
            if low == 0:
                continue
            amplitude = (high - low) / low
            if amplitude < self.amplitude_min or amplitude > self.amplitude_max:
                continue

            # Standard deviation as percentage of mean
            mean_price = sum(vol_slice) / len(vol_slice)
            if mean_price == 0:
                continue
            variance = sum((p - mean_price) ** 2 for p in vol_slice) / len(vol_slice)
            std_pct = math.sqrt(variance) / mean_price
            if std_pct > self.max_std:
                continue

            # ── 5. Max drawdown within window ──
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

            # ── 6. No significant reverse movement in recent ticks ──
            reverse_window = min(self.reverse_tick_window, len(history))
            recent = history[-reverse_window:]
            has_reverse = False
            for i in range(1, len(recent)):
                if recent[i - 1] > 0:
                    tick_change = (recent[i] - recent[i - 1]) / recent[i - 1]
                    if tick_change < -self.reverse_threshold:
                        has_reverse = True
                        break
            if has_reverse:
                continue

            # ── 7. All conditions met — compute position size ──
            # Use midpoint of [position_min_pct, position_max_pct]
            target_pct = (self.position_min_pct + self.position_max_pct) / 2
            buy_budget = ctx.balance * target_pct
            if buy_budget <= 0 or mid <= 0:
                continue

            amount = math.floor(buy_budget / mid)
            if amount <= 0:
                continue

            signals.append(Signal(
                token_id=token_id,
                side="BUY",
                amount=float(amount),
            ))
            self._entered = True
            self._entry_count += 1
            break  # Only enter once

        return signals

    def on_fill(self, fill: FillInfo) -> None:
        pass

    def on_end(self) -> dict:
        return {
            "entered": self._entered,
            "entry_count": self._entry_count,
            "strategy_type": "hold_to_settlement",
        }
