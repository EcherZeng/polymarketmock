"""Shared state — avoids circular imports between api modules."""

from __future__ import annotations

import asyncio

from api.result_store import BatchStore, PortfolioStore, ResultStore
from core.batch_runner import BatchRunner
from core.ai_optimizer import AIOptimizer
from core.sensitivity import SensitivityAnalyzer
from core.registry import StrategyRegistry

registry = StrategyRegistry()
# Service-level backtest concurrency pool — shared by BatchRunner, AIOptimizer,
# and SensitivityAnalyzer so that the total number of concurrent run_backtest
# threads never exceeds config.max_concurrency regardless of task origin.
backtest_semaphore: asyncio.Semaphore | None = None
batch_runner: BatchRunner | None = None
ai_optimizer: AIOptimizer | None = None
sensitivity_analyzer: SensitivityAnalyzer | None = None
result_store: ResultStore | None = None
batch_store: BatchStore | None = None
portfolio_store: PortfolioStore | None = None
