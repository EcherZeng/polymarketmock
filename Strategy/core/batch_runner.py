"""Batch runner — parallel backtest scheduling with asyncio + thread pool."""

from __future__ import annotations

import asyncio
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone

from config import config
from core.data_loader import load_archive
from core.registry import StrategyRegistry
from core.runner import run_backtest
from core.types import ArchiveData, BacktestSession

logger = logging.getLogger(__name__)


@dataclass
class BatchTask:
    """Tracks a batch of backtest runs."""

    batch_id: str
    strategy: str
    slugs: list[str]
    config: dict
    initial_balance: float
    status: str = "running"  # "running" | "completed" | "cancelled"
    created_at: str = ""
    total: int = 0
    completed_count: int = 0
    results: dict[str, BacktestSession] = field(default_factory=dict)
    errors: dict[str, str] = field(default_factory=dict)


class BatchRunner:
    """Manages parallel backtest execution with concurrency control."""

    def __init__(self, registry: StrategyRegistry, max_concurrency: int | None = None) -> None:
        self._registry = registry
        self._semaphore = asyncio.Semaphore(max_concurrency or config.max_concurrency)
        self._tasks: dict[str, BatchTask] = {}
        self._running: dict[str, asyncio.Task] = {}

    async def submit(
        self,
        strategy: str,
        slugs: list[str],
        user_config: dict,
        initial_balance: float,
    ) -> str:
        """Submit a batch of backtests. Returns batch_id."""
        batch_id = uuid.uuid4().hex[:12]
        task = BatchTask(
            batch_id=batch_id,
            strategy=strategy,
            slugs=slugs,
            config=user_config,
            initial_balance=initial_balance,
            created_at=datetime.now(timezone.utc).isoformat(),
            total=len(slugs),
        )
        self._tasks[batch_id] = task

        # Launch background task
        async_task = asyncio.create_task(self._run_batch(batch_id))
        self._running[batch_id] = async_task
        return batch_id

    async def _run_batch(self, batch_id: str) -> None:
        """Execute all backtests in a batch with concurrency control."""
        task = self._tasks[batch_id]

        # Pre-load data (same slug only loaded once)
        data_cache: dict[str, ArchiveData] = {}

        async def load_data(slug: str) -> ArchiveData:
            if slug not in data_cache:
                data_cache[slug] = await asyncio.to_thread(
                    load_archive, config.data_dir, slug,
                )
            return data_cache[slug]

        async def run_one(slug: str) -> None:
            if task.status == "cancelled":
                return
            async with self._semaphore:
                try:
                    data = await load_data(slug)
                    result = await asyncio.to_thread(
                        run_backtest,
                        self._registry,
                        task.strategy,
                        slug,
                        task.config,
                        task.initial_balance,
                        data,
                    )
                    task.results[slug] = result
                except Exception as e:
                    logger.error("Batch %s slug %s failed: %s", batch_id, slug, e)
                    task.errors[slug] = str(e)
                finally:
                    task.completed_count += 1

        await asyncio.gather(*(run_one(slug) for slug in task.slugs))

        if task.status != "cancelled":
            task.status = "completed"
        self._running.pop(batch_id, None)

    def cancel(self, batch_id: str) -> bool:
        """Cancel a running batch."""
        task = self._tasks.get(batch_id)
        if task is None:
            return False
        task.status = "cancelled"
        async_task = self._running.pop(batch_id, None)
        if async_task:
            async_task.cancel()
        return True

    def get_task(self, batch_id: str) -> BatchTask | None:
        return self._tasks.get(batch_id)

    def list_tasks(self) -> list[BatchTask]:
        return list(self._tasks.values())
