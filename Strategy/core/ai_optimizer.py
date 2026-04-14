"""AI Optimizer — iterative LLM-guided parameter exploration.

Orchestrates multi-round backtest loops:
  Round 1: AI receives param_schema + market profile → outputs N candidate configs
  Round 2..N: AI receives accumulated config→metrics table → refines parameters
  Final: returns best config + all round summaries

Data sent to LLM is always compact digests (~2KB per run), never raw time-series.

Sub-modules (split for maintainability):
  core/ai_types.py          — RoundResult, OptimizeTask, serialization helpers
  core/ai_prompt_builder.py — System prompt + round/group prompt construction
  core/ai_config_parser.py  — LLM response parsing, param validation, clamping
  core/llm_client.py        — httpx OpenAI API call wrapper
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
import traceback
import uuid
from datetime import datetime, timezone
from pathlib import Path

import httpx

from config import config
from core.ai_config_parser import parse_ai_configs
from core.ai_prompt_builder import SYSTEM_PROMPT, build_group_prompt
from core.ai_types import OptimizeTask, RoundResult, task_from_dict, task_to_dict
from core.btc_data import fetch_btc_klines
from core.data_loader import load_archive
from core.evaluator import compute_drawdown_curve, compute_drawdown_events, evaluate
from core.llm_client import call_llm
from core.market_profiler import profile_market
from core.registry import StrategyRegistry
from core.result_digest import digest_session
from core.runner import run_backtest
from core.types import ArchiveData, btc_trend_enabled, parse_slug_window

logger = logging.getLogger(__name__)


# ── Optimizer ────────────────────────────────────────────────────────────────


class AIOptimizer:
    """Multi-round LLM-guided parameter optimizer."""

    def __init__(
        self,
        registry: StrategyRegistry,
        on_result: callable | None = None,
        tasks_dir: Path | None = None,
        semaphore: asyncio.Semaphore | None = None,
    ) -> None:
        self._registry = registry
        # Use caller-supplied semaphore (service-level pool) when available;
        # fall back to a local one so AIOptimizer can still be used standalone.
        self._semaphore = semaphore or asyncio.Semaphore(config.max_concurrency)
        self._tasks: dict[str, OptimizeTask] = {}
        self._running: dict[str, asyncio.Task] = {}
        self._on_result = on_result
        self._tasks_dir = tasks_dir
        if self._tasks_dir:
            self._tasks_dir.mkdir(parents=True, exist_ok=True)

    # ── Persistence ──────────────────────────────────────────────────────────

    def load_tasks(self) -> int:
        """Load persisted tasks from disk. Returns count loaded."""
        if not self._tasks_dir or not self._tasks_dir.exists():
            return 0
        count = 0
        for f in sorted(self._tasks_dir.glob("opt_*.json")):
            try:
                raw = f.read_text("utf-8")
                d = json.loads(raw)
                task = task_from_dict(d)
                self._tasks[task.task_id] = task
                count += 1
            except Exception as e:
                logger.warning("Failed to load AI task %s: %s", f.name, e)
        if count:
            logger.info("Loaded %d persisted AI optimization tasks", count)
        return count

    def _persist_task(self, task: OptimizeTask) -> None:
        """Save a single task to disk."""
        if not self._tasks_dir:
            return
        try:
            path = self._tasks_dir / f"opt_{task.task_id}.json"
            path.write_text(
                json.dumps(task_to_dict(task), ensure_ascii=False, default=str),
                encoding="utf-8",
            )
        except Exception as e:
            logger.error("Failed to persist AI task %s: %s", task.task_id, e)

    async def submit(
        self,
        strategy: str,
        slugs: list[str],
        base_config: dict,
        optimize_target: str,
        max_rounds: int,
        runs_per_round: int,
        initial_balance: float,
        llm_model: str | None = None,
        param_keys: list[str] | None = None,
        active_params: list[str] | None = None,
        settlement_result: dict[str, float] | None = None,
    ) -> str:
        """Submit an AI optimization task. Returns task_id."""
        task_id = uuid.uuid4().hex[:12]

        # Resolve active_params: which parameters exist in the config at all
        if not active_params:
            active_params = list(base_config.keys())
        active_set = set(active_params)

        # Resolve param_keys: which parameters AI can tune
        if not param_keys:
            schema = self._registry.get_param_schema()
            # Default: all non-bool params (entry/volatility/position/risk)
            param_keys = [
                k for k, v in schema.items()
                if v.get("type") != "bool"
            ]

        # Constrain param_keys to active params only
        param_keys = [k for k in param_keys if k in active_set]

        # Filter base_config to active params only
        base_config = {k: v for k, v in base_config.items() if k in active_set}

        task = OptimizeTask(
            task_id=task_id,
            strategy=strategy,
            slugs=slugs,
            base_config=base_config,
            optimize_target=optimize_target,
            max_rounds=max_rounds,
            runs_per_round=runs_per_round,
            initial_balance=initial_balance,
            settlement_result=settlement_result,
            param_keys=param_keys,
            active_params=active_params,
            created_at=datetime.now(timezone.utc).isoformat(),
            total_runs=1 * len(slugs) + max_rounds * runs_per_round * len(slugs),
        )
        self._tasks[task_id] = task

        # Persist initial snapshot so the task is findable after a server restart.
        self._persist_task(task)

        # Resolve LLM model
        resolved_model = llm_model or config.llm_default_model

        # Launch background task
        async_task = asyncio.create_task(
            self._run_optimization(task_id, resolved_model, param_keys)
        )
        self._running[task_id] = async_task
        return task_id

    # ── Per-backtest helper ───────────────────────────────────────────────────

    async def _run_one_backtest(
        self,
        task: "OptimizeTask",
        round_num: int,
        cfg_idx: int,
        merged_config: dict,
        slug: str,
        btc_cache: "dict[str, list[dict] | None]",
    ) -> "tuple[int, str, dict | None]":
        """Load data on-demand, run one backtest, evaluate, persist.

        Acquires the shared backtest semaphore so total concurrent threads
        across the whole service stay within max_concurrency.  Data is loaded
        *inside* the semaphore guard and deleted immediately after run_backtest
        returns, so peak memory is O(max_concurrency) archive objects, not O(N).

        BTC klines are supplied via btc_cache (pre-fetched once per task in
        _run_optimization) to avoid ~2000 redundant Binance requests per task.

        Returns (cfg_idx, slug, digest) or (cfg_idx, slug, None) on failure.
        """
        if task.status == "cancelled":
            return cfg_idx, slug, None

        async with self._semaphore:
            if task.status == "cancelled":
                return cfg_idx, slug, None

            try:
                # BTC klines are resolved from the task-level cache; no per-backtest
                # network request needed.  btc_cache.get(slug) returns None when BTC
                # filter is not enabled or prefetch failed — run_backtest handles None
                # gracefully (allows entry, logs warning).
                btc_klines: list[dict] | None = btc_cache.get(slug)

                # Load data on-demand — never held beyond this backtest call
                data = await asyncio.to_thread(load_archive, config.data_dir, slug)
                try:
                    session = await asyncio.wait_for(
                        asyncio.to_thread(
                            run_backtest,
                            self._registry,
                            task.strategy,
                            slug,
                            merged_config,
                            task.initial_balance,
                            data,
                            task.settlement_result,
                            btc_klines,
                        ),
                        timeout=config.slug_timeout,
                    )
                finally:
                    del data  # release ASAP regardless of outcome

                # Evaluate
                metrics = evaluate(session)
                session.metrics = metrics
                session.drawdown_curve = compute_drawdown_curve(session.equity_curve)
                session.drawdown_events = compute_drawdown_events(session.equity_curve)

                # Persist individual result
                if self._on_result:
                    try:
                        self._on_result(session)
                    except Exception as e:
                        task.persist_errors.append(
                            f"[round_{round_num}] persist failed cfg {cfg_idx} slug {slug}: {e}"
                        )
                        logger.error("on_result callback failed: %s", e)

                # Extract compact digest
                digest = digest_session(session)
                digest["round"] = round_num
                digest["config_index"] = cfg_idx
                return cfg_idx, slug, digest

            except asyncio.TimeoutError:
                err_msg = (
                    f"[round_{round_num}] config {cfg_idx} slug {slug} "
                    f"timed out after {config.slug_timeout}s"
                )
                logger.warning(
                    "AI optimizer %s round %d config %d slug %s timed out",
                    task.task_id, round_num, cfg_idx, slug,
                )
                task.errors.append({
                    "round": round_num,
                    "phase": "backtest",
                    "config_index": cfg_idx,
                    "slug": slug,
                    "message": err_msg,
                    "detail": "",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                })
                return cfg_idx, slug, None

            except asyncio.CancelledError:
                raise  # propagate so asyncio.gather can exit cleanly

            except Exception as e:
                tb = traceback.format_exc()
                err_msg = f"[round_{round_num}] config {cfg_idx} slug {slug} error: {e}"
                logger.error(
                    "AI optimizer %s round %d config %d slug %s error: %s",
                    task.task_id, round_num, cfg_idx, slug, e,
                )
                task.errors.append({
                    "round": round_num,
                    "phase": "backtest",
                    "config_index": cfg_idx,
                    "slug": slug,
                    "message": err_msg,
                    "detail": tb,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                })
                return cfg_idx, slug, None

    async def _run_optimization(
        self,
        task_id: str,
        llm_model: str,
        param_keys: list[str],
    ) -> None:
        """Execute the multi-round optimization loop."""
        task = self._tasks[task_id]
        param_schema = self._registry.get_param_schema()
        active_set = set(task.active_params)

        try:
            # ── Phase 1: Build market profiles ────────────────────────────
            # Load each slug one at a time and discard the ArchiveData
            # immediately after profiling.  This keeps memory at O(1) rather
            # than O(N slugs) before any backtest even starts.
            for slug in task.slugs:
                data = await asyncio.to_thread(load_archive, config.data_dir, slug)
                task.market_profiles[slug] = profile_market(slug, data)
                # data goes out of scope here — GC can reclaim immediately

            # ── Pre-fetch BTC klines (task-level cache) ────────────────────
            # All slugs share the same BTC window resolution; cache once here
            # so each backtest call (N_rounds × N_configs × N_slugs) reuses the
            # pre-fetched result instead of hitting Binance ~2000 extra times.
            btc_cache: dict[str, list[dict] | None] = {}
            if btc_trend_enabled(task.base_config):
                for slug in task.slugs:
                    try:
                        slug_window = parse_slug_window(slug)
                        if slug_window:
                            btc_cache[slug] = await fetch_btc_klines(slug_window[0], slug_window[1])
                        else:
                            btc_cache[slug] = None
                    except Exception as _btc_err:
                        logger.warning(
                            "AI optimizer %s btc prefetch failed slug %s: %s",
                            task_id, slug, _btc_err,
                        )
                        btc_cache[slug] = None
                logger.info(
                    "AI optimizer %s btc prefetch done: %d/%d slugs cached",
                    task_id,
                    sum(1 for v in btc_cache.values() if v is not None),
                    len(task.slugs),
                )

            # ── Phase 2: Baseline (round 0) + AI rounds ───────────────────
            async with httpx.AsyncClient(timeout=120) as llm_http:
                for round_num in range(0, task.max_rounds + 1):
                    if task.status == "cancelled":
                        break

                    task.current_round = round_num
                    t_round = time.monotonic()

                    if round_num == 0:
                        # Round 0: baseline — run user's original config
                        baseline_params = {
                            k: task.base_config[k]
                            for k in param_keys
                            if k in task.base_config
                        }
                        configs = [baseline_params]
                        reason = "基准测试 — 使用策略原始参数建立 baseline"
                        task.ai_messages.append({
                            "round": round_num,
                            "role": "system",
                            "content_length": 0,
                            "content": reason,
                            "timestamp": datetime.now(timezone.utc).isoformat(),
                        })
                    else:
                        # AI round: build prompt + call LLM
                        baseline_digests = [
                            d for d in task.all_digests if d.get("round") == 0
                        ]
                        prev_round = round_num - 1
                        prev_digests = [
                            d for d in task.all_digests if d.get("round") == prev_round
                        ]
                        user_prompt = build_group_prompt(
                            round_number=round_num,
                            param_schema=param_schema,
                            base_config=task.base_config,
                            market_profiles=task.market_profiles,
                            optimize_target=task.optimize_target,
                            runs_per_round=task.runs_per_round,
                            baseline_digests=baseline_digests,
                            prev_round_digests=prev_digests,
                            prev_round_number=prev_round,
                            param_keys=param_keys,
                            best_metric=task.best_metric,
                            best_total_trades=task.best_total_trades,
                        )

                        task.ai_messages.append({
                            "round": round_num,
                            "role": "user",
                            "content_length": len(user_prompt),
                            "content": user_prompt,
                            "timestamp": datetime.now(timezone.utc).isoformat(),
                        })

                        try:
                            raw_response = await call_llm(
                                llm_http,
                                config.llm_api_url, config.llm_api_key, llm_model,
                                SYSTEM_PROMPT, user_prompt,
                            )
                        except Exception as e:
                            tb = traceback.format_exc()
                            err_msg = f"[round_{round_num}] LLM error: {e}"
                            logger.error("AI optimizer %s round %d LLM call failed: %s", task_id, round_num, e)
                            task.errors.append({
                                "round": round_num,
                                "phase": "llm_call",
                                "message": err_msg,
                                "detail": tb,
                                "timestamp": datetime.now(timezone.utc).isoformat(),
                            })
                            task.error = err_msg
                            task.status = "failed"
                            break

                        task.ai_messages.append({
                            "round": round_num,
                            "role": "assistant",
                            "content_length": len(raw_response),
                            "content": raw_response,
                            "timestamp": datetime.now(timezone.utc).isoformat(),
                        })

                        try:
                            configs, reason = parse_ai_configs(
                                raw_response, param_schema, task.runs_per_round, active_set
                            )
                        except Exception as e:
                            tb = traceback.format_exc()
                            err_msg = f"[round_{round_num}] Parse error: {e}"
                            logger.error("AI optimizer %s round %d parse failed: %s", task_id, round_num, e)
                            task.errors.append({
                                "round": round_num,
                                "phase": "parse",
                                "message": err_msg,
                                "detail": tb,
                                "timestamp": datetime.now(timezone.utc).isoformat(),
                            })
                            task.error = err_msg
                            task.status = "failed"
                            break

                        if not configs:
                            err_msg = f"[round_{round_num}] AI produced no valid configs"
                            logger.warning("AI optimizer %s round %d produced no configs", task_id, round_num)
                            task.errors.append({
                                "round": round_num,
                                "phase": "parse",
                                "message": err_msg,
                                "detail": "",
                                "timestamp": datetime.now(timezone.utc).isoformat(),
                            })
                            task.error = err_msg
                            task.status = "failed"
                            break

                    # ── Parallel gather: all (cfg × slug) pairs this round ──
                    # Prepare merged configs once to avoid re-merging inside coroutines
                    merged_configs: list[tuple[int, dict]] = []
                    for cfg_idx, ai_config in enumerate(configs):
                        merged = {**task.base_config, **ai_config}
                        merged = {k: v for k, v in merged.items() if k in active_set}
                        merged = self._registry.normalize_config(merged)
                        merged_configs.append((cfg_idx, merged))

                    # Each coroutine acquires the semaphore independently, so
                    # the service-level pool caps total concurrency across ALL
                    # tasks (batch + AI + sensitivity).
                    coros = [
                        self._run_one_backtest(task, round_num, cfg_idx, merged, slug, btc_cache)
                        for cfg_idx, merged in merged_configs
                        for slug in task.slugs
                    ]
                    # return_exceptions=True: prevents one unexpected raise from
                    # short-circuiting gather and silently discarding other results.
                    # _run_one_backtest already wraps all exceptions; any residual
                    # BaseException (e.g. MemoryError) surfaces here as a value
                    # and is handled in the digest-collection loop below.
                    raw_results_raw = await asyncio.gather(*coros, return_exceptions=True)
                    raw_results: list[tuple[int, str, dict | None]] = [
                        r if isinstance(r, tuple) else (0, "", None)
                        for r in raw_results_raw
                    ]

                    round_result = RoundResult(
                        round_number=round_num,
                        configs=configs,
                        ai_reasoning=reason,
                    )

                    # Collect digests
                    for _, _, digest in raw_results:
                        if digest is not None:
                            round_result.digests.append(digest)
                            task.all_digests.append(digest)

                    # completed_runs: per (config × slug) — matches total_runs granularity
                    task.completed_runs += len(merged_configs) * len(task.slugs)

                    # ── Group-level best tracking ─────────────────────────
                    # Build O(1) lookup: (cfg_idx, slug) → digest
                    digest_map: dict[tuple[int, str], dict] = {
                        (ci, s): d for ci, s, d in raw_results if d is not None
                    }

                    _MIN_TRADES_FOR_BEST = 5
                    for cfg_idx, merged in merged_configs:
                        _cfg_metric_vals: list[float] = []
                        _cfg_total_trades_vals: list[int] = []
                        _cfg_first_session_id: str = ""

                        for slug in task.slugs:
                            d = digest_map.get((cfg_idx, slug))
                            if d:
                                m = d.get("metrics", {})
                                metric_val = m.get(task.optimize_target)
                                if metric_val is not None:
                                    _cfg_metric_vals.append(metric_val)
                                    _cfg_total_trades_vals.append(m.get("total_trades", 0))
                                    if not _cfg_first_session_id:
                                        _cfg_first_session_id = d.get("session_id", "")

                        if _cfg_metric_vals:
                            group_metric = sum(_cfg_metric_vals) / len(_cfg_metric_vals)
                            group_total_trades = sum(_cfg_total_trades_vals)
                            avg_trades_per_slug = group_total_trades / len(_cfg_metric_vals)

                            new_enough = avg_trades_per_slug >= _MIN_TRADES_FOR_BEST
                            best_avg_trades = (
                                task.best_total_trades / len(task.slugs)
                                if task.slugs else task.best_total_trades
                            )
                            old_enough = best_avg_trades >= _MIN_TRADES_FOR_BEST

                            should_update = False
                            if task.best_metric == float("-inf"):
                                should_update = True
                            elif new_enough and not old_enough:
                                should_update = True
                            elif not new_enough and old_enough:
                                should_update = False
                            else:
                                should_update = group_metric > task.best_metric

                            if should_update:
                                task.best_metric = group_metric
                                task.best_config = merged
                                task.best_session_id = _cfg_first_session_id
                                task.best_total_trades = group_total_trades

                    # ── Round summary ─────────────────────────────────────
                    _rnd_config_metrics: dict[int, list[float]] = {}
                    for _d in round_result.digests:
                        _ci = _d.get("config_index", -1)
                        if _d.get("metrics"):
                            _v = _d["metrics"].get(task.optimize_target, None)
                            if _v is not None:
                                _rnd_config_metrics.setdefault(_ci, []).append(_v)
                    _group_avgs = [
                        sum(vals) / len(vals)
                        for vals in _rnd_config_metrics.values()
                        if vals
                    ]
                    round_result.best_metric_value = max(_group_avgs) if _group_avgs else 0.0
                    round_result.duration_ms = (time.monotonic() - t_round) * 1000
                    task.rounds.append(round_result)
                    self._persist_task(task)

                    logger.info(
                        "AI optimizer %s round %d done: %d runs, best %s=%.4f, reason: %s",
                        task_id, round_num, len(round_result.digests),
                        task.optimize_target, round_result.best_metric_value,
                        reason[:100],
                    )

            # ── Done ─────────────────────────────────────────────────────
            # Only mark completed if the loop ran to natural end.
            # "failed" set via break must not be silently overwritten.
            if task.status not in ("cancelled", "failed"):
                task.status = "completed"
            self._persist_task(task)

        except Exception as e:
            tb = traceback.format_exc()
            logger.error("AI optimizer %s failed: %s\n%s", task_id, e, tb)
            task.status = "failed"
            task.error = str(e)
            task.errors.append({
                "round": task.current_round,
                "phase": "unknown",
                "message": str(e),
                "detail": tb,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })
            self._persist_task(task)

        self._running.pop(task_id, None)

    def cancel(self, task_id: str) -> bool:
        """Cancel a running optimization task."""
        task = self._tasks.get(task_id)
        if task is None:
            return False
        task.status = "cancelled"
        async_task = self._running.pop(task_id, None)
        if async_task:
            async_task.cancel()
        self._persist_task(task)
        return True

    def get_task(self, task_id: str) -> OptimizeTask | None:
        return self._tasks.get(task_id)

    def list_tasks(self) -> list[OptimizeTask]:
        return list(self._tasks.values())
