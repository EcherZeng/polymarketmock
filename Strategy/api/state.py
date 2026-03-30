"""Shared state — avoids circular imports between api modules."""

from __future__ import annotations

from core.batch_runner import BatchRunner
from core.registry import StrategyRegistry

registry = StrategyRegistry()
batch_runner: BatchRunner | None = None
