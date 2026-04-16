"""BacktestExecutor — unified IO + CPU scheduling layer.

Single responsibility: schedule backtest → evaluate → on_result callback.
Workers load archive data internally — no large-object IPC over OS pipes.
Uses loky ProcessPoolExecutor for resilient worker management: crashed
workers are automatically replaced instead of poisoning the pool.

archive_sem  bounds concurrent in-flight operations (worker memory).
cpu_sem      bounds concurrent worker submissions.

Two entry-points:
  run_one(...)                 — one (slug, config) pair; used by BatchRunner.
  run_slug_multi_config(...)   — one slug, N configs (worker loads once, runs all);
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

from loky import ProcessPoolExecutor

from config import config
from core.evaluator import compute_drawdown_curve, compute_drawdown_events, evaluate
from core.registry import StrategyRegistry
from core.types import BacktestSession


# ── Worker process helpers (module-level so they are picklable) ───────────────

_worker_registry: StrategyRegistry | None = None
_worker_data_dir: str | None = None


def _init_worker(strategies_dir: str, data_dir: str) -> None:
    """Called once per worker process. Sets up strategy registry and token map."""
    import logging as _log
    import sys
    from pathlib import Path

    # Ensure Strategy root dir is importable inside spawned workers.
    strategy_root = str(Path(strategies_dir).parent)
    if strategy_root not in sys.path:
        sys.path.insert(0, strategy_root)

    _log.basicConfig(level=logging.WARNING)

    # Token map is required by data_loader decode functions.
    from core.data_scanner import load_token_map
    load_token_map(Path(data_dir))

    global _worker_registry, _worker_data_dir
    from core.registry import StrategyRegistry as _Reg

    _worker_registry = _Reg()
    _worker_registry.scan(Path(strategies_dir))
    _worker_data_dir = data_dir


def _run_backtest_in_worker(
    strategy: str,
    slug: str,
    merged_cfg: dict,
    initial_balance: float,
    settlement_result: dict[str, float] | None,
    btc_klines: list[dict] | None,
    matching_mode: str = "vwap",
) -> dict:
    """Worker entry point for single (slug, config). Loads data internally.

    ``merged_cfg`` is already merged+normalised by the main process;
    the worker skips registry name lookup and config merge.
    """
    import gc as _gc
    import time as _time
    import traceback as _tb
    from pathlib import Path

    global _worker_registry, _worker_data_dir
    if _worker_registry is None or _worker_data_dir is None:
        raise RuntimeError("Worker process not initialised (_worker_registry is None)")

    from core.data_loader import load_archive
    from core.runner import run_backtest as _rb

    skip_ob = matching_mode == "simple"

    # ── Load data inside worker — no large-object IPC ────────────────
    t0 = _time.monotonic()
    try:
        data = load_archive(Path(_worker_data_dir), slug, skip_ob_deltas=skip_ob)
    except Exception as e:
        return {
            "error_phase": "data_load", "error": str(e), "error_tb": _tb.format_exc(),
            "stats": {}, "dt_load_ms": (_time.monotonic() - t0) * 1000,
            "dt_run_ms": 0.0, "session": None,
        }
    dt_load_ms = (_time.monotonic() - t0) * 1000

    stats = {
        "prices_count": len(data.prices),
        "orderbooks_count": len(data.orderbooks),
        "ob_deltas_count": len(data.ob_deltas),
        "live_trades_count": len(data.live_trades),
    }

    if not data.prices and not data.orderbooks:
        return {
            "error_phase": "data_load", "error": "Archive is empty (no prices/orderbooks)",
            "stats": stats, "dt_load_ms": dt_load_ms, "dt_run_ms": 0.0, "session": None,
        }

    # ── Run backtest ─────────────────────────────────────────────────
    t1 = _time.monotonic()
    try:
        session = _rb(
            _worker_registry, strategy, slug, {},  initial_balance,
            data, settlement_result, btc_klines,
            pre_merged_config=merged_cfg,
            matching_mode=matching_mode,
        )
    except Exception as e:
        return {
            "error_phase": "backtest", "error": str(e), "error_tb": _tb.format_exc(),
            "stats": stats, "dt_load_ms": dt_load_ms,
            "dt_run_ms": (_time.monotonic() - t1) * 1000, "session": None,
        }
    dt_run_ms = (_time.monotonic() - t1) * 1000

    del data  # free memory before pickling result back
    _gc.collect()  # reclaim pymalloc arenas to reduce RSS fragmentation
    return {
        "error_phase": None, "error": None, "stats": stats,
        "dt_load_ms": dt_load_ms, "dt_run_ms": dt_run_ms, "session": session,
    }


def _run_backtest_multi_in_worker(
    strategy: str,
    slug: str,
    configs: list[tuple[int, dict]],
    initial_balance: float,
    settlement_result: dict[str, float] | None,
    btc_klines: list[dict] | None,
) -> dict:
    """Worker entry point for one slug × N configs. Loads data once.

    Each config in ``configs`` is already merged+normalised by the main process.
    """
    import gc as _gc
    import time as _time
    import traceback as _tb
    from pathlib import Path

    global _worker_registry, _worker_data_dir
    if _worker_registry is None or _worker_data_dir is None:
        raise RuntimeError("Worker process not initialised (_worker_registry is None)")

    from core.data_loader import load_archive
    from core.runner import run_backtest as _rb

    t0 = _time.monotonic()
    try:
        data = load_archive(Path(_worker_data_dir), slug)
    except Exception as e:
        return {
            "error_phase": "data_load", "error": str(e), "error_tb": _tb.format_exc(),
            "stats": {}, "dt_load_ms": (_time.monotonic() - t0) * 1000, "results": [],
        }
    dt_load_ms = (_time.monotonic() - t0) * 1000

    stats = {
        "prices_count": len(data.prices),
        "orderbooks_count": len(data.orderbooks),
        "ob_deltas_count": len(data.ob_deltas),
        "live_trades_count": len(data.live_trades),
    }

    if not data.prices and not data.orderbooks:
        return {
            "error_phase": "data_load", "error": "Archive is empty (no prices/orderbooks)",
            "stats": stats, "dt_load_ms": dt_load_ms, "results": [],
        }

    results: list[tuple[int, dict]] = []
    for cfg_idx, merged in configs:
        t1 = _time.monotonic()
        try:
            session = _rb(
                _worker_registry, strategy, slug, {}, initial_balance,
                data, settlement_result, btc_klines,
                pre_merged_config=merged,
            )
            results.append((cfg_idx, {
                "session": session, "error": None,
                "dt_run_ms": (_time.monotonic() - t1) * 1000,
            }))
        except Exception as e:
            results.append((cfg_idx, {
                "session": None, "error": str(e), "tb": _tb.format_exc(),
                "dt_run_ms": (_time.monotonic() - t1) * 1000,
            }))

    del data
    _gc.collect()  # reclaim pymalloc arenas to reduce RSS fragmentation
    return {
        "error_phase": None, "stats": stats,
        "dt_load_ms": dt_load_ms, "results": results,
    }

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
        # loky ProcessPoolExecutor — resilient against worker crashes.
        # Workers that die are automatically replaced (no BrokenProcessPool).
        # Workers load archive data internally so only lightweight scalars
        # cross the process boundary (no large-object pickle IPC).
        self._process_pool = ProcessPoolExecutor(
            max_workers=config.max_concurrency,
            initializer=_init_worker,
            initargs=(str(config.strategies_dir), str(config.data_dir)),
        )
        self._task_count = 0  # track submissions for periodic pool recycle

    def close(self) -> None:
        """Shutdown the worker process pool (call from lifespan cleanup)."""
        self._process_pool.shutdown(wait=False, kill_workers=True)

    def recycle_pool(self) -> None:
        """Kill current workers and create a fresh pool.

        Call between batch chunks to reclaim CPython pymalloc arena
        fragmentation that accumulates across hundreds of load→run→free
        cycles.  loky doesn't support max_tasks_per_child, so this is
        the equivalent mechanism.
        """
        logger.info("Recycling worker pool (task_count=%d)", self._task_count)
        self._process_pool.shutdown(wait=True, kill_workers=True)
        self._process_pool = ProcessPoolExecutor(
            max_workers=config.max_concurrency,
            initializer=_init_worker,
            initargs=(str(config.strategies_dir), str(config.data_dir)),
        )
        self._task_count = 0

    def _merge_config(self, strategy_name: str, user_config: dict) -> dict:
        """Merge + normalise config using the main-process registry.

        This is the single authoritative merge point before handing off to
        a worker process.  Workers receive the result and skip registry
        lookup entirely.
        """
        default_config = self._registry.get_default_config(strategy_name)
        if user_config:
            merged = {k: user_config.get(k, default_config.get(k)) for k in user_config}
        else:
            merged = dict(default_config)
        return self._registry.normalize_config(merged)

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
        matching_mode: str = "vwap",
    ) -> BacktestRunResult:
        """Run a single (slug, config) pair.

        Config is merged+normalised in the main process using the
        authoritative registry, then sent to the worker as pre_merged_config
        so the worker never needs to look up preset names.
        """
        # ── Pre-merge config in main process (authoritative registry) ─
        merged_cfg = self._merge_config(strategy, cfg)

        async with self._archive_sem:
            self._task_count += 1
            t_wall = time.monotonic()
            try:
                async with self._cpu_sem:
                    loop = asyncio.get_running_loop()
                    wr = await asyncio.wait_for(
                        loop.run_in_executor(
                            self._process_pool,
                            _run_backtest_in_worker,
                            strategy, slug, merged_cfg, initial_balance,
                            settlement_result, btc_klines, matching_mode,
                        ),
                        timeout=timeout,
                    )
            except asyncio.TimeoutError:
                return BacktestRunResult(
                    error_phase="backtest",
                    error_msg=f"Timed out after {timeout}s",
                    timed_out=True,
                    dt_run_ms=(time.monotonic() - t_wall) * 1000,
                )
            except Exception as e:
                return BacktestRunResult(
                    error_phase="backtest",
                    error_msg=str(e),
                    error_tb=traceback.format_exc(),
                    dt_run_ms=(time.monotonic() - t_wall) * 1000,
                )

            # Unpack worker result
            stats = wr.get("stats", {})
            result = BacktestRunResult(
                dt_load_ms=wr.get("dt_load_ms", 0.0),
                dt_run_ms=wr.get("dt_run_ms", 0.0),
                data_prices_count=stats.get("prices_count", 0),
                data_orderbooks_count=stats.get("orderbooks_count", 0),
                data_ob_deltas_count=stats.get("ob_deltas_count", 0),
                data_live_trades_count=stats.get("live_trades_count", 0),
            )

            # Worker-side error (data_load or backtest)
            if wr.get("error_phase"):
                result.error_phase = wr["error_phase"]
                result.error_msg = wr.get("error", "")
                result.error_tb = wr.get("error_tb", "")
                return result

            session = wr["session"]
            del wr  # release pickle buffer immediately
            if session.status == "failed":
                result.error_phase = "backtest"
                result.error_msg = "Runner returned failed status"
                return result

            # ── Evaluate phase (main process, outside cpu_sem) ────────
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
        """One worker loads slug archive once; runs all configs sequentially.

        Returns a flat list of ``(cfg_idx, BacktestRunResult)`` — one per config.
        """
        async with self._archive_sem:
            t_wall = time.monotonic()
            batch_timeout = timeout * len(merged_configs)
            try:
                async with self._cpu_sem:
                    loop = asyncio.get_running_loop()
                    wr = await asyncio.wait_for(
                        loop.run_in_executor(
                            self._process_pool,
                            _run_backtest_multi_in_worker,
                            strategy, slug, merged_configs,
                            initial_balance, settlement_result, btc_klines,
                        ),
                        timeout=batch_timeout,
                    )
            except asyncio.TimeoutError:
                err = BacktestRunResult(
                    error_phase="backtest",
                    error_msg=f"Timed out after {batch_timeout}s (batch)",
                    timed_out=True,
                    dt_run_ms=(time.monotonic() - t_wall) * 1000,
                )
                return [(idx, err) for idx, _ in merged_configs]
            except asyncio.CancelledError:
                raise
            except Exception as e:
                err = BacktestRunResult(
                    error_phase="backtest",
                    error_msg=str(e),
                    error_tb=traceback.format_exc(),
                    dt_run_ms=(time.monotonic() - t_wall) * 1000,
                )
                return [(idx, err) for idx, _ in merged_configs]

            stats = wr.get("stats", {})
            dt_load_ms = wr.get("dt_load_ms", 0.0)
            stat_kw = {
                "data_prices_count": stats.get("prices_count", 0),
                "data_orderbooks_count": stats.get("orderbooks_count", 0),
                "data_ob_deltas_count": stats.get("ob_deltas_count", 0),
                "data_live_trades_count": stats.get("live_trades_count", 0),
            }

            # Data-load error → all configs fail
            if wr.get("error_phase"):
                err = BacktestRunResult(
                    error_phase=wr["error_phase"],
                    error_msg=wr.get("error", ""),
                    error_tb=wr.get("error_tb", ""),
                    dt_load_ms=dt_load_ms,
                    **stat_kw,
                )
                return [(idx, err) for idx, _ in merged_configs]

            # Per-config results
            output: list[tuple[int, BacktestRunResult]] = []
            for cfg_idx, cr in wr.get("results", []):
                rr = BacktestRunResult(
                    dt_load_ms=dt_load_ms,
                    dt_run_ms=cr.get("dt_run_ms", 0.0),
                    **stat_kw,
                )

                if cr.get("error"):
                    rr.error_phase = "backtest"
                    rr.error_msg = cr["error"]
                    rr.error_tb = cr.get("tb", "")
                    output.append((cfg_idx, rr))
                    continue

                session = cr["session"]

                # ── Evaluate (main process) ───────────────────────────
                t2 = time.monotonic()
                try:
                    metrics = evaluate(session)
                    session.metrics = metrics
                    session.drawdown_curve = compute_drawdown_curve(session.equity_curve)
                    session.drawdown_events = compute_drawdown_events(session.equity_curve)
                except Exception as e:
                    rr.error_phase = "evaluate"
                    rr.error_msg = str(e)
                    rr.error_tb = traceback.format_exc()
                    rr.dt_eval_ms = (time.monotonic() - t2) * 1000
                    output.append((cfg_idx, rr))
                    continue
                rr.dt_eval_ms = (time.monotonic() - t2) * 1000

                # ── Persist callback ──────────────────────────────────
                if self._on_result:
                    try:
                        self._on_result(session)
                    except Exception as e:
                        rr.persist_error = str(e)
                        logger.error("on_result callback failed: %s", e)

                rr.session = session
                output.append((cfg_idx, rr))

            return output
