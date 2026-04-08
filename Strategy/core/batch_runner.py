"""Batch runner — workflow-style parallel backtest scheduling with step logging.

Optimised for large batches:
- Per-slug timeout (config.slug_timeout) prevents runaway backtests
- Chunked gather (config.batch_chunk_size) avoids creating all coroutines at once
- Sessions are released from memory after persisting to disk (only summary kept)
- Data cache is evicted per-chunk to limit peak memory
"""

from __future__ import annotations

import asyncio
import gc
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
class ResultSummary:
    """Lightweight summary kept in memory after session is persisted to disk."""

    session_id: str
    status: str
    initial_balance: float
    final_equity: float
    total_return_pct: float
    sharpe_ratio: float
    total_trades: int
    win_rate: float
    max_drawdown: float
    avg_slippage: float
    profit_factor: float


@dataclass
class BatchTask:
    """Tracks a batch of backtest runs."""

    batch_id: str
    strategy: str
    slugs: list[str]
    config: dict
    initial_balance: float
    settlement_result: dict[str, float] | None = None
    cumulative_capital: bool = False
    status: str = "running"  # "running" | "completed" | "cancelled"
    created_at: str = ""
    total: int = 0
    completed_count: int = 0
    results: dict[str, BacktestSession] = field(default_factory=dict)
    results_summary: dict[str, ResultSummary] = field(default_factory=dict)
    errors: dict[str, str] = field(default_factory=dict)
    persist_errors: list[str] = field(default_factory=list)  # callback persistence failures
    workflows: dict[str, SlugWorkflow] = field(default_factory=dict)
    capital_chain: list[dict] = field(default_factory=list)  # cumulative mode: [{slug, start, end}]


def _extract_summary(session: BacktestSession) -> ResultSummary:
    """Extract lightweight summary from a BacktestSession."""
    m = session.metrics
    return ResultSummary(
        session_id=session.session_id,
        status=session.status,
        initial_balance=session.initial_balance,
        final_equity=session.final_equity,
        total_return_pct=m.total_return_pct,
        sharpe_ratio=m.sharpe_ratio,
        total_trades=m.total_trades,
        win_rate=m.win_rate,
        max_drawdown=m.max_drawdown,
        avg_slippage=m.avg_slippage,
        profit_factor=m.profit_factor,
    )


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
        cumulative_capital: bool = False,
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
            cumulative_capital=cumulative_capital,
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
        """Execute all backtests in a batch with concurrency control.

        Slugs are processed in chunks to limit peak memory. Within each chunk
        asyncio.gather runs up to max_concurrency tasks in parallel.
        """
        task = self._tasks[batch_id]
        slug_timeout = config.slug_timeout
        chunk_size = config.batch_chunk_size

        # Per-chunk data cache (evicted between chunks)
        data_cache: dict[str, ArchiveData] = {}
        _lock = asyncio.Lock()

        async def load_data(slug: str) -> ArchiveData:
            async with _lock:
                if slug not in data_cache:
                    data_cache[slug] = await asyncio.to_thread(
                        load_archive, config.data_dir, slug,
                    )
            return data_cache[slug]

        async def run_one(slug: str, override_balance: float | None = None) -> BacktestSession | None:
            """Run a single slug backtest. Returns session on success (for cumulative mode)."""
            wf = task.workflows[slug]
            if task.status == "cancelled":
                wf.status = "skipped"
                wf.log("cancelled", "skip", "Batch was cancelled before this slug started")
                async with _lock:
                    task.completed_count += 1
                return None

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
                    return None
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
                    return None

                wf.log(
                    "data_load", "ok",
                    f"{len(data.prices)} prices, {len(data.orderbooks)} orderbooks, "
                    f"{len(data.ob_deltas)} deltas, {len(data.live_trades)} trades",
                    duration_ms=dt_load,
                )

                # ── Step 2: Run backtest (strategy init + tick loop) ─────
                slug_balance = override_balance if override_balance is not None else task.initial_balance
                t1 = time.monotonic()
                try:
                    session = await asyncio.wait_for(
                        asyncio.to_thread(
                            run_backtest,
                            self._registry,
                            task.strategy,
                            slug,
                            task.config,
                            slug_balance,
                            data,
                            task.settlement_result,
                        ),
                        timeout=slug_timeout,
                    )
                except asyncio.TimeoutError:
                    wf.log(
                        "tick_loop", "fail",
                        f"Backtest timed out after {slug_timeout}s",
                    )
                    wf.status = "failed"
                    wf.error = f"[tick_loop] Timed out after {slug_timeout}s"
                    task.errors[slug] = wf.error
                    logger.error("Batch %s slug %s timed out after %ds", batch_id, slug, slug_timeout)
                    async with _lock:
                        task.completed_count += 1
                    return None
                except Exception as e:
                    tb = traceback.format_exc()
                    wf.log("tick_loop", "fail", f"Backtest execution error: {e}", detail=tb)
                    wf.status = "failed"
                    wf.error = f"[tick_loop] {e}"
                    task.errors[slug] = wf.error
                    logger.error("Batch %s slug %s tick_loop failed: %s\n%s", batch_id, slug, e, tb)
                    async with _lock:
                        task.completed_count += 1
                    return None
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
                    return None

                wf.log(
                    "tick_loop", "ok",
                    f"{len(session.equity_curve)} equity points, "
                    f"{len(session.trades)} trades, "
                    f"duration={session.duration_seconds:.2f}s",
                    duration_ms=dt_run,
                )

                # Tag capital mode
                if task.cumulative_capital:
                    session.capital_mode = "cumulative"

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
                    return None
                dt_eval = (time.monotonic() - t2) * 1000

                wf.log(
                    "evaluate", "ok",
                    f"return={metrics.total_return_pct:.2f}%, "
                    f"sharpe={metrics.sharpe_ratio:.4f}, "
                    f"trades={metrics.total_trades}",
                    duration_ms=dt_eval,
                )

                # ── Persist result immediately ───────────────────────────
                if self._on_result:
                    try:
                        self._on_result(session)
                    except Exception as e:
                        err_msg = f"[{slug}] persist failed: {e}"
                        logger.error("on_result callback failed for %s: %s", slug, e)
                        task.persist_errors.append(err_msg)
                        wf.log("persist", "fail", err_msg)

                # ── Keep only lightweight summary, release full session ──
                summary = _extract_summary(session)
                task.results_summary[slug] = summary
                # Store in results temporarily for on_batch_complete access
                # but do NOT keep large curves in memory
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

                async with _lock:
                    task.completed_count += 1

                return session

        # ── Process slugs ────────────────────────────────────────────────
        slugs = task.slugs

        if task.cumulative_capital:
            # ── Cumulative capital mode: serial execution ─────────────────
            current_balance = task.initial_balance
            for slug in slugs:
                if task.status == "cancelled":
                    break
                task.capital_chain.append({
                    "slug": slug,
                    "start_balance": round(current_balance, 6),
                    "end_balance": None,
                    "status": "pending",
                })
                session = await run_one(slug, override_balance=current_balance)
                chain_entry = task.capital_chain[-1]
                if session is not None and session.status == "completed":
                    chain_entry["end_balance"] = round(session.final_equity, 6)
                    chain_entry["status"] = "completed"
                    current_balance = session.final_equity
                    # Capital exhausted — stop all subsequent slugs
                    if current_balance <= 0:
                        chain_entry["status"] = "capital_exhausted"
                        # Mark remaining slugs as skipped
                        remaining_idx = slugs.index(slug) + 1
                        for rem_slug in slugs[remaining_idx:]:
                            wf_rem = task.workflows[rem_slug]
                            wf_rem.status = "skipped"
                            wf_rem.log(
                                "cancelled", "skip",
                                f"Capital exhausted after {slug} (balance={current_balance:.2f})",
                            )
                            task.capital_chain.append({
                                "slug": rem_slug,
                                "start_balance": 0.0,
                                "end_balance": 0.0,
                                "status": "capital_exhausted",
                            })
                            task.completed_count += 1
                        break
                else:
                    chain_entry["end_balance"] = round(current_balance, 6)
                    chain_entry["status"] = "failed"
                    # On failure in cumulative mode, keep current_balance unchanged

                # Release session from memory
                task.results.pop(slug, None)
                data_cache.pop(slug, None)
                gc.collect()
        else:
            # ── Fixed capital mode: parallel chunked execution ────────────
            for chunk_start in range(0, len(slugs), chunk_size):
                if task.status == "cancelled":
                    break
                chunk = slugs[chunk_start : chunk_start + chunk_size]
                await asyncio.gather(*(run_one(slug) for slug in chunk))

            # Release full sessions from previous chunk — summaries are kept
            for slug in chunk:
                task.results.pop(slug, None)

            # Evict data cache for completed slugs (next chunk may need different data)
            completed_slugs = {s for s in chunk if task.workflows[s].status in ("completed", "failed", "skipped")}
            for s in completed_slugs:
                data_cache.pop(s, None)

            # Periodic GC to reclaim memory between chunks
            gc.collect()
            logger.info(
                "Batch %s chunk %d-%d done (%d/%d total)",
                batch_id, chunk_start, chunk_start + len(chunk),
                task.completed_count, task.total,
            )

        if task.status != "cancelled":
            task.status = "completed"
        self._running.pop(batch_id, None)

        # Notify batch completion for persistence
        if self._on_batch_complete:
            try:
                self._on_batch_complete(task)
            except Exception as e:
                err_msg = f"batch_complete persist failed: {e}"
                logger.error("on_batch_complete callback failed for %s: %s", batch_id, e)
                task.persist_errors.append(err_msg)

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

    def purge_task(self, batch_id: str) -> bool:
        """Remove a completed/cancelled task from in-memory registry."""
        task = self._tasks.get(batch_id)
        if task is None:
            return False
        if task.status == "running":
            return False  # do not purge running tasks
        del self._tasks[batch_id]
        self._running.pop(batch_id, None)
        return True

    def purge_completed(self) -> int:
        """Remove all completed/cancelled/failed tasks from memory."""
        to_remove = [
            bid for bid, t in self._tasks.items()
            if t.status in ("completed", "cancelled")
        ]
        for bid in to_remove:
            del self._tasks[bid]
            self._running.pop(bid, None)
        return len(to_remove)
