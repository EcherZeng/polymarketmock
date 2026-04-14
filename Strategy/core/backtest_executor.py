"""BacktestExecutor — unified IO + CPU scheduling layer.

Single responsibility: load archive → run_backtest → evaluate → on_result callback.

archive_sem  bounds how many ArchiveData objects exist in memory at once.
cpu_sem      bounds how many run_backtest threads run concurrently.

Two entry-points:
  run_one(...)                 — one (slug, config) pair; used by BatchRunner.
  run_slug_multi_config(...)   — one slug, N configs (share one load_archive call);
                                 used by AIOptimizer for O(N_slug) data loads
                                 instead of O(N_cfg × N_slug).
"""

from __future__ import annotations

import asyncio
import logging
import time
import traceback
from collections.abc import Callable
from dataclasses import dataclass, field

from config import config
from core.data_loader import load_archive
from core.evaluator import compute_drawdown_curve, compute_drawdown_events, evaluate
from core.registry import StrategyRegistry
from core.runner import run_backtest
from core.types import BacktestSession

logger = logging.getLogger(__name__)


# ── Result dataclass ─────────────────────────────────────────────────────────


@dataclass
class BacktestRunResult:
    """Outcome of a single (slug, config) backtest run.

    Carries enough information for callers to emit step logs (timing, counts)
    and accumulate error lists without re-reading the session object.
    """

    session: BacktestSession | None = None

    # None → success; non-None → phase where error occurred
    error_phase: str | None = None  # "data_load" | "backtest" | "evaluate"
    error_msg: str = ""
    error_tb: str = ""
    timed_out: bool = False  # only meaningful when error_phase == "backtest"

    # Timing (milliseconds) — for step-log emit by caller
    dt_load_ms: float = 0.0
    dt_run_ms: float = 0.0
    dt_eval_ms: float = 0.0

    # Data stats — for data_load step-log message by caller
    data_prices_count: int = 0
    data_orderbooks_count: int = 0
    data_ob_deltas_count: int = 0
    data_live_trades_count: int = 0

    # on_result callback error (caller may append to persist_errors)
    persist_error: str = ""

    @property
    def ok(self) -> bool:
        """True iff run succeeded (session is valid and evaluate completed)."""
        return self.error_phase is None and self.session is not None


# ── Executor ─────────────────────────────────────────────────────────────────


class BacktestExecutor:
    """Bounded two-phase executor for backtest runs.

    Parameters
    ----------
    registry:     StrategyRegistry — passed through to run_backtest.
    cpu_sem:      Semaphore — limits concurrent run_backtest threads.
    archive_sem:  Semaphore — limits concurrent ArchiveData objects in memory.
                  Both semaphores are typically shared across BatchRunner,
                  AIOptimizer, and SensitivityAnalyzer via api/app.py.
    on_result:    Optional callback invoked after evaluate; must be cheap and
                  synchronous (it runs in the event loop).
    """

    def __init__(
        self,
        registry: StrategyRegistry,
        cpu_sem: asyncio.Semaphore,
        archive_sem: asyncio.Semaphore,
        on_result: Callable[[BacktestSession], None] | None = None,
    ) -> None:
        self._registry = registry
        self._cpu_sem = cpu_sem
        self._archive_sem = archive_sem
        self._on_result = on_result

    # ── Single run ───────────────────────────────────────────────────────────

    async def run_one(
        self,
        slug: str,
        strategy: str,
        cfg: dict,
        initial_balance: float,
        settlement_result: dict[str, float] | None,
        btc_klines: list[dict] | None,
        timeout: float,
    ) -> BacktestRunResult:
        """Run a single (slug, config) pair.

        archive_sem is acquired for the full duration of load → evaluate so
        that at most ``archive_sem._value`` ArchiveData objects live in memory
        simultaneously.
        """
        async with self._archive_sem:
            # ── IO phase ─────────────────────────────────────────────────
            t0 = time.monotonic()
            try:
                data = await asyncio.to_thread(load_archive, config.data_dir, slug)
            except Exception as e:
                return BacktestRunResult(
                    error_phase="data_load",
                    error_msg=str(e),
                    error_tb=traceback.format_exc(),
                    dt_load_ms=(time.monotonic() - t0) * 1000,
                )
            dt_load_ms = (time.monotonic() - t0) * 1000

            try:
                if not data.prices and not data.orderbooks:
                    return BacktestRunResult(
                        error_phase="data_load",
                        error_msg="Archive is empty (no prices/orderbooks)",
                        dt_load_ms=dt_load_ms,
                    )

                result = BacktestRunResult(
                    dt_load_ms=dt_load_ms,
                    data_prices_count=len(data.prices),
                    data_orderbooks_count=len(data.orderbooks),
                    data_ob_deltas_count=len(data.ob_deltas),
                    data_live_trades_count=len(data.live_trades),
                )

                # ── CPU phase ─────────────────────────────────────────────
                t1 = time.monotonic()
                try:
                    async with self._cpu_sem:
                        session = await asyncio.wait_for(
                            asyncio.to_thread(
                                run_backtest,
                                self._registry,
                                strategy,
                                slug,
                                cfg,
                                initial_balance,
                                data,
                                settlement_result,
                                btc_klines,
                            ),
                            timeout=timeout,
                        )
                except asyncio.TimeoutError:
                    result.error_phase = "backtest"
                    result.error_msg = f"Timed out after {timeout}s"
                    result.timed_out = True
                    result.dt_run_ms = (time.monotonic() - t1) * 1000
                    return result
                except Exception as e:
                    result.error_phase = "backtest"
                    result.error_msg = str(e)
                    result.error_tb = traceback.format_exc()
                    result.dt_run_ms = (time.monotonic() - t1) * 1000
                    return result
                result.dt_run_ms = (time.monotonic() - t1) * 1000

                if session.status == "failed":
                    result.error_phase = "backtest"
                    result.error_msg = "Runner returned failed status"
                    result.dt_run_ms = (time.monotonic() - t1) * 1000
                    return result

                # ── Evaluate phase (outside cpu_sem) ──────────────────────
                t2 = time.monotonic()
                try:
                    metrics = evaluate(session)
                    session.metrics = metrics
                    session.drawdown_curve = compute_drawdown_curve(session.equity_curve)
                    session.drawdown_events = compute_drawdown_events(session.equity_curve)
                except Exception as e:
                    result.error_phase = "evaluate"
                    result.error_msg = str(e)
                    result.error_tb = traceback.format_exc()
                    result.dt_eval_ms = (time.monotonic() - t2) * 1000
                    return result
                result.dt_eval_ms = (time.monotonic() - t2) * 1000

                # ── Persist callback ──────────────────────────────────────
                if self._on_result:
                    try:
                        self._on_result(session)
                    except Exception as e:
                        result.persist_error = str(e)
                        logger.error("on_result callback failed for %s: %s", slug, e)

                result.session = session
                return result

            finally:
                del data  # release ArchiveData before archive_sem is freed

    # ── Multi-config run (one slug, N configs) ───────────────────────────────

    async def run_slug_multi_config(
        self,
        slug: str,
        strategy: str,
        merged_configs: list[tuple[int, dict]],
        initial_balance: float,
        settlement_result: dict[str, float] | None,
        btc_klines: list[dict] | None,
        timeout: float,
    ) -> list[tuple[int, BacktestRunResult]]:
        """Load slug archive once; run all ``merged_configs`` sequentially.

        archive_sem is held for the entire slug (covering all N configs) so
        that the ArchiveData object is never duplicated.  This reduces
        load_archive calls from ``N_cfg × N_slug`` to ``N_slug`` per round.

        Returns a flat list of ``(cfg_idx, BacktestRunResult)`` — one per config.
        """
        async with self._archive_sem:
            # ── IO phase (one load for all configs) ───────────────────────
            t0 = time.monotonic()
            try:
                data = await asyncio.to_thread(load_archive, config.data_dir, slug)
            except Exception as e:
                tb = traceback.format_exc()
                dt_load_ms = (time.monotonic() - t0) * 1000
                err = BacktestRunResult(
                    error_phase="data_load",
                    error_msg=str(e),
                    error_tb=tb,
                    dt_load_ms=dt_load_ms,
                )
                return [(cfg_idx, err) for cfg_idx, _ in merged_configs]

            try:
                results: list[tuple[int, BacktestRunResult]] = []

                for cfg_idx, merged in merged_configs:
                    run_result = BacktestRunResult()

                    # ── CPU phase ─────────────────────────────────────────
                    t1 = time.monotonic()
                    try:
                        async with self._cpu_sem:
                            session = await asyncio.wait_for(
                                asyncio.to_thread(
                                    run_backtest,
                                    self._registry,
                                    strategy,
                                    slug,
                                    merged,
                                    initial_balance,
                                    data,
                                    settlement_result,
                                    btc_klines,
                                ),
                                timeout=timeout,
                            )
                    except asyncio.TimeoutError:
                        run_result.error_phase = "backtest"
                        run_result.error_msg = f"Timed out after {timeout}s"
                        run_result.timed_out = True
                        run_result.dt_run_ms = (time.monotonic() - t1) * 1000
                        results.append((cfg_idx, run_result))
                        continue
                    except asyncio.CancelledError:
                        raise
                    except Exception as e:
                        run_result.error_phase = "backtest"
                        run_result.error_msg = str(e)
                        run_result.error_tb = traceback.format_exc()
                        run_result.dt_run_ms = (time.monotonic() - t1) * 1000
                        results.append((cfg_idx, run_result))
                        continue
                    run_result.dt_run_ms = (time.monotonic() - t1) * 1000

                    # ── Evaluate (outside cpu_sem) ────────────────────────
                    try:
                        metrics = evaluate(session)
                        session.metrics = metrics
                        session.drawdown_curve = compute_drawdown_curve(session.equity_curve)
                        session.drawdown_events = compute_drawdown_events(session.equity_curve)
                    except Exception as e:
                        run_result.error_phase = "evaluate"
                        run_result.error_msg = str(e)
                        run_result.error_tb = traceback.format_exc()
                        results.append((cfg_idx, run_result))
                        continue

                    # ── Persist callback ──────────────────────────────────
                    if self._on_result:
                        try:
                            self._on_result(session)
                        except Exception as e:
                            run_result.persist_error = str(e)
                            logger.error("on_result callback failed: %s", e)

                    run_result.session = session
                    results.append((cfg_idx, run_result))

                return results

            finally:
                del data  # release ArchiveData before archive_sem is freed
