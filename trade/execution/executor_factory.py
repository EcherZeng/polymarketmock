"""Executor factory — creates real or mock executor based on config."""

from __future__ import annotations

import logging

from execution.base_executor import BaseExecutor

logger = logging.getLogger(__name__)


def create_executor(mode: str) -> BaseExecutor:
    """Create executor instance based on mode setting.

    Args:
        mode: "real" or "mock"
    """
    if mode == "real":
        from execution.order_executor import OrderExecutor
        logger.info("Creating REAL order executor")
        return OrderExecutor()
    elif mode == "mock":
        from execution.mock_executor import MockExecutor
        logger.info("Creating MOCK order executor")
        return MockExecutor()
    else:
        raise ValueError(f"Unknown executor_mode: {mode!r}. Use 'real' or 'mock'.")
