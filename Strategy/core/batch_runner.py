"""Batch runner — workflow-style parallel backtest scheduling with step logging."""

from __future__ import annotations

import asyncio
import logging
import traceback
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone

from config import config
from core.data_loader import load_archive
from core.evaluator import compute_drawdown_curve, compute_drawdown_events, evaluate
from core.registry import StrategyRegistry
from core.runner import run_backtest
from core.types import ArchiveData, BacktestSession

logger = logging.getLogger(__name__)


# ── Step log entry ───────────────────────────────────────────────────────────


@dataclass
class StepLog:
    """One log entry for a workflow step."""

    timestamp: str
    step: str  # "data_load" | "strategy_init" | "tick_loop" | "evaluate" | "done" | "error"
    status: str  # "ok" | "fail" | "skip"
    message: str = ""
    detail: str = ""  # traceback or extra info
    duration_ms: float = 0.0


@dataclass
class SlugWorkflow:
    """Per-slug workflow tracking with step logs."""

    slug: str
    status: str = "pending"  # "pending" | "running" | "completed" | "failed" | "skipped"
    steps: list[StepLog] = field(default_factory=list)
    error: str = ""

    def log(
        self,
        step: str,
        status: str,
        message: str = "",
        detail: str = "",
        duration_ms: float = 0.0,
    ) -> None:
        self.steps.append(
            StepLog(
                timestamp=datetime.now(timezone.utc).isoformat(),
                step=step,
                status=status,
                message=message,
                detail=detail,
                duration_ms=round(duration_ms, 1),
            )
        )


@dataclass
class BatchTask:
    """Tracks a batch of backtest runs."""

    batch_id: str
    strategy: str
    slugs: list[str]
    config: dict
    initial_balance: float
    settlement_result: dict[str, float] | None = None
    status: str = "running"  # "running" | "completed" | "cancelled"
    created_at: str = ""
    total: int = 0
    completed_count: int = 0
    results: dict[str, BacktestSession] = field(default_factory=dict)
    errors: dict[str, str] = field(default_factory=dict)
    workflows: dict[str, SlugWorkflow] = field(default_factory=dict)


class BatchRunner:
    """Manages parallel backtest execution with concurrency control and step logging."""

    def __init__(
        self,
        registry: StrategyRegistry,
        max_concurrency: int | None = None,
        on_result: Callable[[BacktestSession], None] | None = None,
        on_batch_complete: Callable[[BatchTask], None] | None = None,
    ) -> None:
        self._registry = registry
        self._semaphore = asyncio.Semaphore(max_concurrency or config.max_concurrency)
        self._tasks: dict[str, BatchTask] = {}
        self._running: dict[str, asyncio.Task] = {}
        self._on_result = on_result
        self._on_batch_complete = on_batch_complete

    async def submit(
        self,
        strategy: str,
        slugs: list[str],
        user_config: dict,
        initial_balance: float,
        settlement_result: dict[str, float] | None = None,
    ) -> str:
        """Submit a batch of backtests. Returns batch_id."""
        batch_id = uuid.uuid4().hex[:12]
        task = BatchTask(
            batch_id=batch_id,
            strategy=strategy,
            slugs=slugs,
            config=user_config,
            initial_balance=initial_balance,
            settlement_result=settlement_result,
            created_at=datetime.now(timezone.utc).isoformat(),
            total=len(slugs),
            workflows={s: SlugWorkflow(slug=s) for s in slugs},
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
        _lock = asyncio.Lock()

        async def load_data(slug: str) -> ArchiveData:
            async with _lock:
                if slug not in data_cache:
                    data_cache[slug] = await asyncio.to_thread(
                        load_archive, config.data_dir, slug,
                    )
            return data_cache[slug]

        async def run_one(slug: str) -> None:
            wf = task.workflows[slug]
            if task.status == "cancelled":
                wf.status = "skipped"
                wf.log("cancelled", "skip", "Batch was cancelled before this slug started")
                async with _lock:
                    task.completed_count += 1
                return

            async with self._semaphore:
                wf.status = "running"
                import time

                # ── Step 1: Data load ────────────────────────────────────
                t0 = time.monotonic()
                try:
                    data = await load_data(slug)
                except Exception as e:
                    tb = traceback.format_exc()
                    wf.log("data_load", "fail", f"Failed to load data: {e}", detail=tb)
                    wf.status = "failed"
                    wf.error = f"[data_load] {e}"
                    task.errors[slug] = wf.error
                    logger.error("Batch %s slug %s data_load failed: %s", batch_id, slug, e)
                    async with _lock:
                        task.completed_count += 1
                    return
                dt_load = (time.monotonic() - t0) * 1000

                # Validate data
                if not data.prices and not data.orderbooks:
                    wf.log(
                        "data_load", "fail",
                        "Archive is empty — no prices and no orderbooks",
                        duration_ms=dt_load,
                    )
                    wf.status = "failed"
                    wf.error = "[data_load] Archive is empty (no prices/orderbooks)"
                    task.errors[slug] = wf.error
                    logger.warning("Batch %s slug %s has empty archive", batch_id, slug)
                    async with _lock:
                        task.completed_count += 1
                    return

                wf.log(
                    "data_load", "ok",
                    f"{len(data.prices)} prices, {len(data.orderbooks)} orderbooks, "
                    f"{len(data.ob_deltas)} deltas, {len(data.live_trades)} trades",
                    duration_ms=dt_load,
                )

                # ── Step 2: Run backtest (strategy init + tick loop) ─────
                t1 = time.monotonic()
                try:
                    session = await asyncio.to_thread(
                        run_backtest,
                        self._registry,
                        task.strategy,
                        slug,
                        task.config,
                        task.initial_balance,
                        data,
                        task.settlement_result,
                    )
                except Exception as e:
                    tb = traceback.format_exc()
                    wf.log("tick_loop", "fail", f"Backtest execution error: {e}", detail=tb)
                    wf.status = "failed"
                    wf.error = f"[tick_loop] {e}"
                    task.errors[slug] = wf.error
                    logger.error("Batch %s slug %s tick_loop failed: %s\n%s", batch_id, slug, e, tb)
                    async with _lock:
                        task.completed_count += 1
                    return
                dt_run = (time.monotonic() - t1) * 1000

                # Check if runner reported failure
                if session.status == "failed":
                    wf.log(
                        "tick_loop", "fail",
                        "Runner returned failed status (strategy not found or data insufficient)",
                        duration_ms=dt_run,
                    )
                    wf.status = "failed"
                    wf.error = "[tick_loop] Runner returned failed status"
                    task.errors[slug] = wf.error
                    logger.warning("Batch %s slug %s runner returned failed", batch_id, slug)
                    async with _lock:
                        task.completed_count += 1
                    return

                wf.log(
                    "tick_loop", "ok",
                    f"{len(session.equity_curve)} equity points, "
                    f"{len(session.trades)} trades, "
                    f"duration={session.duration_seconds:.2f}s",
                    duration_ms=dt_run,
                )

                # ── Step 3: Evaluate metrics ─────────────────────────────
                t2 = time.monotonic()
                try:
                    metrics = evaluate(session)
                    session.metrics = metrics
                    session.drawdown_curve = compute_drawdown_curve(session.equity_curve)
                    session.drawdown_events = compute_drawdown_events(session.equity_curve)
                except Exception as e:
                    tb = traceback.format_exc()
                    wf.log("evaluate", "fail", f"Metrics evaluation error: {e}", detail=tb)
                    wf.status = "failed"
                    wf.error = f"[evaluate] {e}"
                    task.errors[slug] = wf.error
                    logger.error("Batch %s slug %s evaluate failed: %s", batch_id, slug, e)
                    async with _lock:
                        task.completed_count += 1
                    return
                dt_eval = (time.monotonic() - t2) * 1000

                wf.log(
                    "evaluate", "ok",
                    f"return={metrics.total_return_pct:.2f}%, "
                    f"sharpe={metrics.sharpe_ratio:.4f}, "
                    f"trades={metrics.total_trades}",
                    duration_ms=dt_eval,
                )

                # ── Done ─────────────────────────────────────────────────
                task.results[slug] = session
                wf.status = "completed"
                wf.log(
                    "done", "ok",
                    f"Final equity={session.final_equity:.2f}, "
                    f"total_time={dt_load + dt_run + dt_eval:.0f}ms",
                )
                logger.info(
                    "Batch %s slug %s completed: return=%.2f%% in %.1fs",
                    batch_id, slug,
                    metrics.total_return_pct, session.duration_seconds,
                )

                # Immediately store result for /results + Dashboard visibility
                if self._on_result:
                    try:
                        self._on_result(session)
                    except Exception as e:
                        logger.error("on_result callback failed for %s: %s", slug, e)

                async with _lock:
                    task.completed_count += 1

        await asyncio.gather(*(run_one(slug) for slug in task.slugs))

        if task.status != "cancelled":
            task.status = "completed"
        self._running.pop(batch_id, None)

        # Notify batch completion for persistence
        if self._on_batch_complete:
            try:
                self._on_batch_complete(task)
            except Exception as e:
                logger.error("on_batch_complete callback failed for %s: %s", batch_id, e)

        # Summary log
        ok_count = sum(1 for w in task.workflows.values() if w.status == "completed")
        fail_count = sum(1 for w in task.workflows.values() if w.status == "failed")
        logger.info(
            "Batch %s finished: %d/%d completed, %d failed, %d errors",
            batch_id, ok_count, task.total, fail_count, len(task.errors),
        )

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
