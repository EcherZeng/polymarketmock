"""Abstract base class for all strategies."""

from __future__ import annotations

from abc import ABC, abstractmethod

from core.types import FillInfo, Signal, TickContext


class BaseStrategy(ABC):
    """Strategy base class — users implement these methods."""

    name: str = "unnamed"
    description: str = ""
    version: str = "0.1.0"
    default_config: dict = {}

    @abstractmethod
    def on_init(self, config: dict) -> None:
        """Called once before backtest starts. Receive user config."""
        ...

    @abstractmethod
    def on_tick(self, ctx: TickContext) -> list[Signal]:
        """Called at each tick. Return trading signals (may be empty)."""
        ...

    def on_fill(self, fill: FillInfo) -> None:
        """Called after each trade fill (optional override)."""
        pass

    def on_end(self) -> dict:
        """Called when backtest ends (optional override). Return custom summary."""
        return {}
