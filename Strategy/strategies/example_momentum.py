"""Momentum strategy — buys when price rises N ticks, sells when it falls N ticks."""

from __future__ import annotations

from core.base_strategy import BaseStrategy
from core.types import FillInfo, Signal, TickContext


class MomentumStrategy(BaseStrategy):
    name = "momentum"
    description = "当价格连续上涨 N tick 时买入，连续下跌 N tick 时卖出"
    version = "0.1.0"
    default_config = {"lookback": 5, "position_size": 100}

    def on_init(self, config: dict) -> None:
        self.lookback = config.get("lookback", 5)
        self.position_size = config.get("position_size", 100)

    def on_tick(self, ctx: TickContext) -> list[Signal]:
        signals: list[Signal] = []
        for token_id, history in ctx.price_history.items():
            if len(history) < self.lookback:
                continue
            recent = history[-self.lookback:]

            # Consecutive up → buy
            if all(recent[i] < recent[i + 1] for i in range(len(recent) - 1)):
                if ctx.positions.get(token_id, 0) == 0:
                    signals.append(Signal(
                        token_id=token_id,
                        side="BUY",
                        amount=self.position_size,
                    ))
            # Consecutive down → sell
            elif all(recent[i] > recent[i + 1] for i in range(len(recent) - 1)):
                held = ctx.positions.get(token_id, 0)
                if held > 0:
                    signals.append(Signal(
                        token_id=token_id,
                        side="SELL",
                        amount=held,
                    ))
        return signals
