"""Mean reversion strategy — trades when price deviates from moving average."""

from __future__ import annotations

import math

from core.base_strategy import BaseStrategy
from core.types import FillInfo, Signal, TickContext


class MeanReversionStrategy(BaseStrategy):
    name = "mean_reversion"
    description = "价格偏离移动均线超过 N 个标准差时反向交易"
    version = "0.1.0"
    default_config = {
        "window": 20,
        "entry_std": 1.5,
        "exit_std": 0.5,
        "position_size": 100,
    }

    def on_init(self, config: dict) -> None:
        self.window = config.get("window", 20)
        self.entry_std = config.get("entry_std", 1.5)
        self.exit_std = config.get("exit_std", 0.5)
        self.position_size = config.get("position_size", 100)
        self._in_position: dict[str, str] = {}  # token_id → "long" | "short"

    def on_tick(self, ctx: TickContext) -> list[Signal]:
        signals: list[Signal] = []
        for token_id, history in ctx.price_history.items():
            if len(history) < self.window:
                continue

            window = history[-self.window:]
            mean = sum(window) / len(window)
            variance = sum((x - mean) ** 2 for x in window) / len(window)
            std = math.sqrt(variance) if variance > 0 else 0.0

            if std == 0:
                continue

            current = history[-1]
            z_score = (current - mean) / std

            held = ctx.positions.get(token_id, 0)
            direction = self._in_position.get(token_id)

            # Entry: price far below mean → buy (expect reversion up)
            if z_score < -self.entry_std and held == 0:
                signals.append(Signal(
                    token_id=token_id,
                    side="BUY",
                    amount=self.position_size,
                ))
                self._in_position[token_id] = "long"

            # Exit long: price reverted back to mean
            elif direction == "long" and held > 0 and z_score > -self.exit_std:
                signals.append(Signal(
                    token_id=token_id,
                    side="SELL",
                    amount=held,
                ))
                self._in_position.pop(token_id, None)

            # Entry: price far above mean → sell if holding (no shorting in prediction markets)
            elif z_score > self.entry_std and held > 0 and direction != "short_exit":
                signals.append(Signal(
                    token_id=token_id,
                    side="SELL",
                    amount=held,
                ))
                self._in_position[token_id] = "short_exit"

        return signals

    def on_end(self) -> dict:
        return {"positions_at_end": dict(self._in_position)}
