"""Batch runner — workflow-style parallel backtest scheduling with step logging.

Concurrency and memory are bounded by the BacktestExecutor's archive_sem and
cpu_sem (both set to max_concurrency at startup), replacing the old per-batch
data_cache + manual chunk loop.  The executor holds an ArchiveData object only
for the duration of one slug's load → run → evaluate cycle; del data is called
before archive_sem is released, so peak memory stays at O(max_concurrency)
ArchiveData objects regardless of batch size.
 
For fixed-capital mode, all slugs are gathered at once — archive_sem acts as
the natural throttle.  For cumulative-capital mode the serial loop is unchanged
because each slug's initial balance depends on the previous slug's final equity.
"""

from __future__ import annotations

import asyncio
import gc
import logging
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone

from config import config
from core.backtest_executor import BacktestExecutor
from core.btc_data import fetch_btc_klines
from core.registry import StrategyRegistry
from core.types import BacktestSession, btc_trend_enabled, parse_slug_window

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
        executor: BacktestExecutor,
        on_batch_complete: Callable[[BatchTask], None] | None = None,
    ) -> None:
        self._executor = executor
        self._tasks: dict[str, BatchTask] = {}
        self._running: dict[str, asyncio.Task] = {}
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
        """Execute all backtests in a batch.

        archive_sem in the executor throttles concurrent ArchiveData objects;
        no manual chunk loop or data_cache is needed.
        """
        task = self._tasks[batch_id]

        async def run_one(slug: str, override_balance: float | None = None) -> BacktestSession | None:
            """Run a single slug backtest. Returns session on success (for cumulative mode)."""
            wf = task.workflows[slug]
            if task.status == "cancelled":
                wf.status = "skipped"
                wf.log("cancelled", "skip", "Batch was cancelled before this slug started")
                task.completed_count += 1
                return None

            wf.status = "running"

            # ── BTC klines prefetch ──────────────────────────────────────
            btc_klines: list[dict] | None = None
            if btc_trend_enabled(task.config):
                try:
                    slug_window = parse_slug_window(slug)
                    if slug_window:
                        btc_klines = await fetch_btc_klines(slug_window[0], slug_window[1])
                except Exception as e:
                    logger.warning(
                        "Batch %s slug %s BTC klines prefetch failed: %s", batch_id, slug, e
                    )

            slug_balance = (
                override_balance if override_balance is not None else task.initial_balance
            )

            # ── Delegate to executor ─────────────────────────────────────
            result = await self._executor.run_one(
                slug=slug,
                strategy=task.strategy,
                cfg=task.config,
                initial_balance=slug_balance,
                settlement_result=task.settlement_result,
                btc_klines=btc_klines,
                timeout=config.slug_timeout,
            )

            # ── Step 1: Data load ────────────────────────────────────────
            if result.error_phase == "data_load":
                wf.log(
                    "data_load", "fail",
                    f"Failed to load data: {result.error_msg}",
                    detail=result.error_tb,
                    duration_ms=result.dt_load_ms,
                )
                wf.status = "failed"
                wf.error = f"[data_load] {result.error_msg}"
                task.errors[slug] = wf.error
                logger.error("Batch %s slug %s data_load failed: %s", batch_id, slug, result.error_msg)
                task.completed_count += 1
                return None

            wf.log(
                "data_load", "ok",
                f"{result.data_prices_count} prices, {result.data_orderbooks_count} orderbooks, "
                f"{result.data_ob_deltas_count} deltas, {result.data_live_trades_count} trades",
                duration_ms=result.dt_load_ms,
            )

            # ── Step 2: Run backtest ─────────────────────────────────────
            if result.error_phase == "backtest":
                if result.timed_out:
                    wf.log(
                        "tick_loop", "fail",
                        f"Backtest timed out after {config.slug_timeout}s",
                    )
                    wf.error = f"[tick_loop] Timed out after {config.slug_timeout}s"
                    logger.error(
                        "Batch %s slug %s timed out after %ds", batch_id, slug, config.slug_timeout
                    )
                elif result.error_msg == "Runner returned failed status":
                    wf.log(
                        "tick_loop", "fail",
                        "Runner returned failed status (strategy not found or data insufficient)",
                        duration_ms=result.dt_run_ms,
                    )
                    wf.error = "[tick_loop] Runner returned failed status"
                    logger.warning("Batch %s slug %s runner returned failed", batch_id, slug)
                else:
                    wf.log(
                        "tick_loop", "fail",
                        f"Backtest execution error: {result.error_msg}",
                        detail=result.error_tb,
                    )
                    wf.error = f"[tick_loop] {result.error_msg}"
                    logger.error(
                        "Batch %s slug %s tick_loop failed: %s", batch_id, slug, result.error_msg
                    )
                wf.status = "failed"
                task.errors[slug] = wf.error
                task.completed_count += 1
                return None

            session = result.session
            wf.log(
                "tick_loop", "ok",
                f"{len(session.equity_curve)} equity points, "
                f"{len(session.trades)} trades, "
                f"duration={session.duration_seconds:.2f}s",
                duration_ms=result.dt_run_ms,
            )

            # ── Step 3: Evaluate ─────────────────────────────────────────
            if result.error_phase == "evaluate":
                wf.log(
                    "evaluate", "fail",
                    f"Metrics evaluation error: {result.error_msg}",
                    detail=result.error_tb,
                )
                wf.status = "failed"
                wf.error = f"[evaluate] {result.error_msg}"
                task.errors[slug] = wf.error
                logger.error("Batch %s slug %s evaluate failed: %s", batch_id, slug, result.error_msg)
                task.completed_count += 1
                return None

            metrics = session.metrics
            wf.log(
                "evaluate", "ok",
                f"return={metrics.total_return_pct:.2f}%, "
                f"sharpe={metrics.sharpe_ratio:.4f}, "
                f"trades={metrics.total_trades}",
                duration_ms=result.dt_eval_ms,
            )

            # ── Persist error from executor ──────────────────────────────
            if result.persist_error:
                err_msg = f"[{slug}] persist failed: {result.persist_error}"
                logger.error("on_result callback failed for %s: %s", slug, result.persist_error)
                task.persist_errors.append(err_msg)
                wf.log("persist", "fail", err_msg)

            # Tag capital mode AFTER executor returns (session belongs to caller)
            if task.cumulative_capital:
                session.capital_mode = "cumulative"

            # ── Keep lightweight summary; store session for on_batch_complete
            summary = _extract_summary(session)
            task.results_summary[slug] = summary
            task.results[slug] = session

            wf.status = "completed"
            wf.log(
                "done", "ok",
                f"Final equity={session.final_equity:.2f}, "
                f"total_time={result.dt_load_ms + result.dt_run_ms + result.dt_eval_ms:.0f}ms",
            )
            logger.info(
                "Batch %s slug %s completed: return=%.2f%% in %.1fs",
                batch_id, slug,
                metrics.total_return_pct, session.duration_seconds,
            )

            task.completed_count += 1
            return session

        # ── Process slugs ────────────────────────────────────────────────
        slugs = task.slugs

        if task.cumulative_capital:
            # ── Cumulative capital mode: serial execution ─────────────────
            # Order is significant: each slug's initial balance is the previous
            # slug's final equity.  Do NOT convert to gather.
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

                # Release session from memory after capital chain is updated
                task.results.pop(slug, None)
                gc.collect()
        else:
            # ── Fixed capital mode: fully parallel ────────────────────────
            # archive_sem in the executor throttles concurrent ArchiveData
            # objects; no manual chunk loop needed.
            await asyncio.gather(*(run_one(slug) for slug in slugs))
            # Release sessions from memory (summaries retained)
            for slug in slugs:
                task.results.pop(slug, None)
            gc.collect()

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
