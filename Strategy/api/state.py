"""Shared state — avoids circular imports between api modules."""

from __future__ import annotations

from api.result_store import BatchStore, PortfolioStore, ResultStore
from core.batch_runner import BatchRunner
from core.ai_optimizer import AIOptimizer
from core.registry import StrategyRegistry

registry = StrategyRegistry()
batch_runner: BatchRunner | None = None
ai_optimizer: AIOptimizer | None = None
result_store: ResultStore | None = None
batch_store: BatchStore | None = None
portfolio_store: PortfolioStore | None = None
