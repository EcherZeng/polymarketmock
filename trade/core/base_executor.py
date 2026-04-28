"""Base interface for order executors (real and mock)."""

from __future__ import annotations

from abc import ABC, abstractmethod

from core.types import LiveFill, LiveSignal


class BaseExecutor(ABC):
    """Abstract order executor — implemented by real and mock variants."""

    @abstractmethod
    async def start(self) -> None: ...

    @abstractmethod
    async def stop(self) -> None: ...

    @property
    @abstractmethod
    def is_ready(self) -> bool: ...

    @abstractmethod
    async def place_order(self, signal: LiveSignal, session_slug: str = "") -> LiveFill | None: ...

    @abstractmethod
    async def cancel_all(self) -> None: ...

    @abstractmethod
    async def cancel_order(self, order_id: str) -> None: ...

    async def get_balance(self) -> float | None:
        """Get USDC balance from exchange. Returns None if unsupported."""
        return None

    async def check_allowance(self) -> bool:
        """Verify token approval is set. Returns True if OK or unsupported."""
        return True
