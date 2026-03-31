"""Shared state — avoids circular imports between api modules."""

from __future__ import annotations

from api.result_store import BatchStore, ResultStore
from core.batch_runner import BatchRunner
from core.registry import StrategyRegistry

registry = StrategyRegistry()
batch_runner: BatchRunner | None = None
result_store: ResultStore | None = None
batch_store: BatchStore | None = None
