"""AI Optimizer — iterative LLM-guided parameter exploration.

Orchestrates multi-round backtest loops:
  Round 1: AI receives param_schema + market profile → outputs N candidate configs
  Round 2..N: AI receives accumulated config→metrics table → refines parameters
  Final: returns best config + all round summaries

Data sent to LLM is always compact digests (~2KB per run), never raw time-series.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
import time
import traceback
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone

import httpx

from config import config
from core.data_loader import load_archive
from core.evaluator import compute_drawdown_curve, compute_drawdown_events, evaluate
from core.market_profiler import profile_market
from core.registry import StrategyRegistry
from core.result_digest import digest_for_ai_table, digest_session
from core.runner import run_backtest
from core.types import ArchiveData

logger = logging.getLogger(__name__)


# ── Data structures ──────────────────────────────────────────────────────────


@dataclass
class RoundResult:
    """Result of a single optimization round."""

    round_number: int
    configs: list[dict] = field(default_factory=list)  # configs tried this round
    digests: list[dict] = field(default_factory=list)  # compact results per config
    ai_reasoning: str = ""  # AI's explanation for parameter choices
    best_metric_value: float = 0.0
    duration_ms: float = 0.0


@dataclass
class OptimizeTask:
    """Tracks an AI optimization task across multiple rounds."""

    task_id: str
    strategy: str
    slugs: list[str]
    base_config: dict
    optimize_target: str  # metric name to optimize
    max_rounds: int
    runs_per_round: int
    initial_balance: float
    settlement_result: dict[str, float] | None = None

    status: str = "running"  # "running" | "completed" | "cancelled" | "failed"
    created_at: str = ""
    current_round: int = 0
    total_runs: int = 0
    completed_runs: int = 0

    rounds: list[RoundResult] = field(default_factory=list)
    all_digests: list[dict] = field(default_factory=list)  # accumulated across rounds
    market_profiles: dict[str, dict] = field(default_factory=dict)
    best_config: dict = field(default_factory=dict)
    best_metric: float = float("-inf")
    best_session_id: str = ""
    error: str = ""  # kept for backward compat (last fatal error)
    errors: list[dict] = field(default_factory=list)  # accumulated structured errors
    persist_errors: list[str] = field(default_factory=list)  # callback persistence failures

    # AI interaction log
    ai_messages: list[dict] = field(default_factory=list)


# ── Prompt builder ───────────────────────────────────────────────────────────


_SYSTEM_PROMPT = (
    "你是一个量化策略参数优化专家。你的任务是根据回测结果调整策略参数，"
    "使目标指标最优化。\n\n"
    "规则：\n"
    "1. 输出必须是严格的 JSON 数组，每个元素是一组参数配置\n"
    "2. 所有参数值必须在 schema 规定的 min/max 范围内\n"
    "3. bool 类型参数只能是 true 或 false\n"
    "4. 每轮给出简短的调整理由（reason 字段）\n"
    "5. 基于历史结果中表现好的参数方向进行收敛\n"
    "6. 避免极端参数组合，优先探索表现好的参数邻域\n\n"
    "输出格式：\n"
    '{"configs": [...], "reason": "调整理由"}'
)


def _build_round_prompt(
    round_number: int,
    param_schema: dict,
    base_config: dict,
    market_profiles: dict[str, dict],
    optimize_target: str,
    runs_per_round: int,
    history_table: list[dict],
    param_keys: list[str],
) -> str:
    """Build the user prompt for one optimization round."""
    # Parameter schema (compact: only name, type, min, max, step)
    schema_lines: list[str] = []
    for name, info in param_schema.items():
        if name not in param_keys:
            continue
        ptype = info.get("type", "float")
        pmin = info.get("min", "")
        pmax = info.get("max", "")
        step = info.get("step", "")
        schema_lines.append(f"  {name}: {ptype} [{pmin}, {pmax}] step={step}")
    schema_text = "\n".join(schema_lines)

    # Market characteristics
    market_lines: list[str] = []
    for slug, profile in market_profiles.items():
        duration = profile.get("duration_seconds", 0)
        token_count = profile.get("token_count", 0)
        tokens_info: list[str] = []
        for tid, tdata in profile.get("tokens", {}).items():
            short_id = tid[:8] + "..." if len(tid) > 12 else tid
            tokens_info.append(
                f"    {short_id}: price=[{tdata['price_min']:.4f}, {tdata['price_max']:.4f}], "
                f"vol={tdata['volatility']:.6f}, spread={tdata['avg_spread']:.4f}"
            )
        market_lines.append(
            f"  {slug}: duration={duration:.0f}s, tokens={token_count}\n"
            + "\n".join(tokens_info)
        )
    market_text = "\n".join(market_lines)

    # Base config
    base_text = json.dumps(
        {k: v for k, v in base_config.items() if k in param_keys},
        indent=2,
        ensure_ascii=False,
    )

    parts: list[str] = [
        f"## 优化轮次 {round_number}",
        f"优化目标: {optimize_target} (越高越好)",
        f"每轮生成: {runs_per_round} 组参数",
        "",
        "## 可调参数范围",
        schema_text,
        "",
        "## 数据源特征",
        market_text,
        "",
        f"## 基准参数",
        base_text,
    ]

    if history_table:
        # Build a markdown table of past results
        headers = list(history_table[0].keys())
        header_line = "| " + " | ".join(headers) + " |"
        sep_line = "| " + " | ".join("---" for _ in headers) + " |"
        rows: list[str] = []
        for row in history_table:
            cells = []
            for h in headers:
                v = row.get(h, "")
                if isinstance(v, float):
                    cells.append(f"{v:.4f}")
                else:
                    cells.append(str(v))
            rows.append("| " + " | ".join(cells) + " |")
        table_text = "\n".join([header_line, sep_line, *rows])
        parts.extend([
            "",
            f"## 历史结果 (共 {len(history_table)} 次回测)",
            table_text,
        ])
    else:
        parts.extend(["", "## 无历史结果 (首轮探索)"])

    parts.extend([
        "",
        f"请生成 {runs_per_round} 组新参数（JSON 格式），目标是最大化 {optimize_target}。",
    ])

    return "\n".join(parts)


# ── LLM caller ───────────────────────────────────────────────────────────────


async def _call_llm(
    client: httpx.AsyncClient,
    api_url: str,
    api_key: str,
    model: str,
    system_prompt: str,
    user_prompt: str,
) -> str:
    """Call OpenAI-compatible chat completion endpoint using a shared client."""
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0.7,
        "response_format": {"type": "json_object"},
    }

    resp = await client.post(api_url, json=payload, headers=headers)
    resp.raise_for_status()

    data = resp.json()
    content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
    return content


def _parse_ai_configs(raw: str, param_schema: dict, runs_per_round: int) -> tuple[list[dict], str]:
    """Parse and validate AI-generated configs.

    Returns (configs, reason).
    Clamps values to schema min/max. Discards invalid entries.
    """
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        # Try to extract JSON from markdown code block
        match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", raw, re.DOTALL)
        if match:
            parsed = json.loads(match.group(1))
        else:
            raise ValueError(f"Failed to parse AI response as JSON: {raw[:200]}")

    configs_raw = parsed.get("configs", [])
    reason = parsed.get("reason", "")

    if not isinstance(configs_raw, list):
        configs_raw = [configs_raw]

    configs: list[dict] = []
    for cfg in configs_raw[:runs_per_round]:
        if not isinstance(cfg, dict):
            continue
        # Clamp to schema ranges
        clamped: dict = {}
        for key, val in cfg.items():
            if key not in param_schema:
                clamped[key] = val
                continue
            schema = param_schema[key]
            ptype = schema.get("type", "float")
            if ptype == "bool":
                clamped[key] = bool(val)
            elif ptype == "int":
                v = int(val)
                if "min" in schema:
                    v = max(v, int(schema["min"]))
                if "max" in schema:
                    v = min(v, int(schema["max"]))
                clamped[key] = v
            elif ptype == "float":
                v = float(val)
                if "min" in schema:
                    v = max(v, float(schema["min"]))
                if "max" in schema:
                    v = min(v, float(schema["max"]))
                clamped[key] = round(v, 6)
            else:
                clamped[key] = val
        configs.append(clamped)

    return configs, reason


# ── Optimizer ────────────────────────────────────────────────────────────────


class AIOptimizer:
    """Multi-round LLM-guided parameter optimizer."""

    def __init__(
        self,
        registry: StrategyRegistry,
        on_result: callable | None = None,
    ) -> None:
        self._registry = registry
        self._semaphore = asyncio.Semaphore(config.max_concurrency)
        self._tasks: dict[str, OptimizeTask] = {}
        self._running: dict[str, asyncio.Task] = {}
        self._on_result = on_result

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
        settlement_result: dict[str, float] | None = None,
    ) -> str:
        """Submit an AI optimization task. Returns task_id."""
        task_id = uuid.uuid4().hex[:12]

        # Resolve param_keys: which parameters AI can tune
        if not param_keys:
            schema = self._registry.get_param_schema()
            # Exclude toggles and risk params by default — focus on entry/volatility/position
            param_keys = [
                k for k, v in schema.items()
                if v.get("group") in ("entry", "volatility", "position")
                and v.get("type") != "bool"
            ]

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
            created_at=datetime.now(timezone.utc).isoformat(),
            total_runs=max_rounds * runs_per_round * len(slugs),
        )
        self._tasks[task_id] = task

        # Resolve LLM model
        resolved_model = llm_model or config.llm_default_model

        # Launch background task
        async_task = asyncio.create_task(
            self._run_optimization(task_id, resolved_model, param_keys)
        )
        self._running[task_id] = async_task
        return task_id

    async def _run_optimization(
        self,
        task_id: str,
        llm_model: str,
        param_keys: list[str],
    ) -> None:
        """Execute the multi-round optimization loop."""
        task = self._tasks[task_id]
        param_schema = self._registry.get_param_schema()

        try:
            # ── Phase 1: Load data + build market profiles (once) ────────
            data_cache: dict[str, ArchiveData] = {}
            for slug in task.slugs:
                data = await asyncio.to_thread(load_archive, config.data_dir, slug)
                data_cache[slug] = data
                task.market_profiles[slug] = profile_market(slug, data)

            # ── Phase 2: Iterative rounds (shared HTTP client) ───────────
            async with httpx.AsyncClient(timeout=120) as llm_client:
              for round_num in range(1, task.max_rounds + 1):
                if task.status == "cancelled":
                    break

                task.current_round = round_num
                t_round = time.monotonic()

                # Build AI context
                history_table = digest_for_ai_table(task.all_digests, param_keys)
                user_prompt = _build_round_prompt(
                    round_num, param_schema, task.base_config,
                    task.market_profiles, task.optimize_target,
                    task.runs_per_round, history_table, param_keys,
                )

                # Log AI interaction
                task.ai_messages.append({
                    "round": round_num,
                    "role": "user",
                    "content_length": len(user_prompt),
                    "content": user_prompt,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                })

                # Call LLM
                try:
                    raw_response = await _call_llm(
                        llm_client,
                        config.llm_api_url, config.llm_api_key, llm_model,
                        _SYSTEM_PROMPT, user_prompt,
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

                # Parse AI response
                try:
                    configs, reason = _parse_ai_configs(raw_response, param_schema, task.runs_per_round)
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

                # ── Run backtests for this round ─────────────────────────
                round_result = RoundResult(
                    round_number=round_num,
                    configs=configs,
                    ai_reasoning=reason,
                )

                for cfg_idx, ai_config in enumerate(configs):
                    if task.status == "cancelled":
                        break

                    # Merge: base_config overridden by AI-suggested params
                    merged_config = {**task.base_config, **ai_config}

                    for slug in task.slugs:
                        if task.status == "cancelled":
                            break

                        async with self._semaphore:
                            try:
                                session = await asyncio.wait_for(
                                    asyncio.to_thread(
                                        run_backtest,
                                        self._registry,
                                        task.strategy,
                                        slug,
                                        merged_config,
                                        task.initial_balance,
                                        data_cache.get(slug),
                                        task.settlement_result,
                                    ),
                                    timeout=config.slug_timeout,
                                )

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
                                        err_msg = f"[round_{round_num}] persist failed for config {cfg_idx} slug {slug}: {e}"
                                        logger.error("on_result callback failed: %s", e)
                                        task.persist_errors.append(err_msg)

                                # Extract digest (compact)
                                digest = digest_session(session)
                                digest["round"] = round_num
                                digest["config_index"] = cfg_idx
                                round_result.digests.append(digest)
                                task.all_digests.append(digest)

                                # Track best
                                metric_val = getattr(metrics, task.optimize_target, None)
                                if metric_val is not None and metric_val > task.best_metric:
                                    task.best_metric = metric_val
                                    task.best_config = merged_config
                                    task.best_session_id = session.session_id

                            except asyncio.TimeoutError:
                                err_msg = f"[round_{round_num}] config {cfg_idx} slug {slug} timed out after {config.slug_timeout}s"
                                logger.warning(
                                    "AI optimizer %s round %d config %d slug %s timed out",
                                    task_id, round_num, cfg_idx, slug,
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
                            except Exception as e:
                                tb = traceback.format_exc()
                                err_msg = f"[round_{round_num}] config {cfg_idx} slug {slug} error: {e}"
                                logger.error(
                                    "AI optimizer %s round %d config %d slug %s error: %s",
                                    task_id, round_num, cfg_idx, slug, e,
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

                        task.completed_runs += 1

                # Round summary
                round_metrics = [
                    d["metrics"].get(task.optimize_target, 0)
                    for d in round_result.digests
                    if d.get("metrics")
                ]
                round_result.best_metric_value = max(round_metrics) if round_metrics else 0.0
                round_result.duration_ms = (time.monotonic() - t_round) * 1000
                task.rounds.append(round_result)

                logger.info(
                    "AI optimizer %s round %d done: %d runs, best %s=%.4f, reason: %s",
                    task_id, round_num, len(round_result.digests),
                    task.optimize_target, round_result.best_metric_value,
                    reason[:100],
                )

            # ── Done ─────────────────────────────────────────────────────
            if task.status != "cancelled":
                task.status = "completed"

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
        return True

    def get_task(self, task_id: str) -> OptimizeTask | None:
        return self._tasks.get(task_id)

    def list_tasks(self) -> list[OptimizeTask]:
        return list(self._tasks.values())
