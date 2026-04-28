"""Base interface for order executors."""

from __future__ import annotations

from abc import ABC, abstractmethod

from models.types import LiveFill, LiveSignal


class BaseExecutor(ABC):

    @abstractmethod
    async def start(self) -> None: ...

    @abstractmethod
    async def stop(self) -> None: ...

    @property
    @abstractmethod
    def is_ready(self) -> bool: ...

    @abstractmethod
    async def place_order(self, signal: LiveSignal, session_slug: str = "") -> LiveFill | None: ...

    async def get_balance(self) -> float | None:
        return None

    async def check_allowance(self) -> bool:
        return True
