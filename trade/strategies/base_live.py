"""Base live strategy interface — all live trading strategies inherit from this."""

from __future__ import annotations

from abc import ABC, abstractmethod

from core.types import (
    ErrorAction,
    LiveFill,
    LiveMarketContext,
    LiveSignal,
    SessionInfo,
    SessionResult,
    TradeError,
)


class BaseLiveStrategy(ABC):
    """Abstract base for live trading strategies.

    Unlike the backtest BaseStrategy (tick-driven on a time grid),
    this interface is event-driven by WebSocket market updates.
    """

    name: str = "unnamed"
    description: str = ""
    version: str = "0.1.0"
    default_config: dict = {}

    @abstractmethod
    def on_session_start(self, session: SessionInfo, config: dict) -> None:
        """Called when a new trading session begins.

        Initialize strategy state, set parameters from config.
        """
        ...

    @abstractmethod
    def on_market_update(self, ctx: LiveMarketContext) -> list[LiveSignal] | None:
        """Called on each WS market event (orderbook update, price change, etc.).

        Return a list of signals to execute, or None/empty to skip.
        This is the main decision method — replaces backtest on_tick().
        """
        ...

    @abstractmethod
    def should_close(self, ctx: LiveMarketContext) -> LiveSignal | None:
        """Evaluate whether to close existing positions.

        Called separately from on_market_update to isolate exit logic.
        Return a SELL signal if closing, None otherwise.
        """
        ...

    def on_fill(self, fill: LiveFill) -> None:
        """Called after an order is filled. Optional override."""
        pass

    def on_session_end(self, result: SessionResult) -> None:
        """Called when a session ends (settled or timed out). Optional override."""
        pass

    def on_error(self, error: TradeError) -> ErrorAction:
        """Decide how to handle an error.

        Default: cancel if no position, retry if holding.
        """
        if error.has_position:
            return ErrorAction.RETRY
        return ErrorAction.CANCEL
