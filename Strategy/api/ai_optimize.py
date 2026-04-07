"""AI-guided optimization API — submit, monitor, and cancel optimization tasks."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

import api.state as state
from config import config

router = APIRouter(prefix="/ai-optimize", tags=["AI Optimize"])


# ── Request / Response models ────────────────────────────────────────────────


class OptimizeRequest(BaseModel):
    strategy: str
    slugs: list[str]
    base_config: dict = Field(default_factory=dict)
    optimize_target: str = Field(default="sharpe_ratio")
    max_rounds: int = Field(default=5, ge=1, le=20)
    runs_per_round: int = Field(default=5, ge=1, le=20)
    initial_balance: float = Field(default=10000, gt=0)
    param_keys: list[str] | None = None
    settlement_result: dict[str, float] | None = None

    # LLM configuration
    llm_model: str = Field(default="deepseek-chat", description="Model name")


# ── Endpoints ────────────────────────────────────────────────────────────────


@router.get("/models")
async def list_available_models():
    """Return available LLM models and whether backend API key is configured."""
    return {
        "models": config.llm_available_models,
        "default_model": config.llm_default_model,
        "api_key_configured": bool(config.llm_api_key),
    }


@router.post("")
async def submit_optimization(req: OptimizeRequest):
    """Submit an AI-guided optimization task.

    The optimizer will:
    1. Load data + build market profiles
    2. Ask LLM for N candidate configs each round
    3. Run backtests, collect metrics
    4. Feed results back to LLM for next round
    5. Return best config after max_rounds
    """
    if state.ai_optimizer is None:
        raise HTTPException(status_code=503, detail="AI optimizer not initialized")

    if not state.registry.has(req.strategy):
        raise HTTPException(status_code=404, detail=f"Strategy '{req.strategy}' not found")

    # Use strategy default config as base if none provided
    base_config = req.base_config
    if not base_config:
        base_config = state.registry.get_default_config(req.strategy)

    task_id = await state.ai_optimizer.submit(
        strategy=req.strategy,
        slugs=req.slugs,
        base_config=base_config,
        optimize_target=req.optimize_target,
        max_rounds=req.max_rounds,
        runs_per_round=req.runs_per_round,
        initial_balance=req.initial_balance,
        llm_model=req.llm_model,
        param_keys=req.param_keys,
        settlement_result=req.settlement_result,
    )

    return {
        "task_id": task_id,
        "max_rounds": req.max_rounds,
        "runs_per_round": req.runs_per_round,
        "total_slugs": len(req.slugs),
        "estimated_total_runs": req.max_rounds * req.runs_per_round * len(req.slugs),
    }


@router.get("")
async def list_optimization_tasks():
    """List all AI optimization tasks."""
    if state.ai_optimizer is None:
        return []

    tasks = state.ai_optimizer.list_tasks()
    return [
        {
            "task_id": t.task_id,
            "strategy": t.strategy,
            "slugs": t.slugs,
            "status": t.status,
            "optimize_target": t.optimize_target,
            "max_rounds": t.max_rounds,
            "current_round": t.current_round,
            "completed_runs": t.completed_runs,
            "total_runs": t.total_runs,
            "best_metric": t.best_metric if t.best_metric != float("-inf") else None,
            "created_at": t.created_at,
        }
        for t in tasks
    ]


@router.get("/{task_id}")
async def get_optimization_task(task_id: str):
    """Get detailed optimization task progress and results."""
    if state.ai_optimizer is None:
        raise HTTPException(status_code=503, detail="AI optimizer not initialized")

    task = state.ai_optimizer.get_task(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")

    # Build round summaries
    rounds_summary: list[dict] = []
    for r in task.rounds:
        # Pre-group digests by config_index for O(1) lookup
        digests_by_cfg: dict[int, list[dict]] = {}
        for d in r.digests:
            idx = d.get("config_index", -1)
            digests_by_cfg.setdefault(idx, []).append(d)

        # Per-config metrics for this round
        configs_results: list[dict] = []
        for i, cfg in enumerate(r.configs):
            cfg_digests = digests_by_cfg.get(i, [])
            avg_metrics: dict = {}
            slug_metrics: list[dict] = []
            if cfg_digests:
                # Average metrics across slugs for this config
                metric_keys = [
                    "total_return_pct", "sharpe_ratio", "win_rate",
                    "max_drawdown", "profit_factor", "total_trades",
                ]
                for mk in metric_keys:
                    vals = [
                        d["metrics"].get(mk, 0)
                        for d in cfg_digests
                        if d.get("metrics")
                    ]
                    avg_metrics[mk] = round(sum(vals) / len(vals), 4) if vals else 0

                # Per-slug breakdown
                for d in cfg_digests:
                    m = d.get("metrics", {})
                    slug_metrics.append({
                        "slug": d.get("slug", ""),
                        "session_id": d.get("session_id", ""),
                        "total_return_pct": round(m.get("total_return_pct", 0), 4),
                        "sharpe_ratio": round(m.get("sharpe_ratio", 0), 4),
                        "win_rate": round(m.get("win_rate", 0), 4),
                        "max_drawdown": round(m.get("max_drawdown", 0), 4),
                        "total_trades": m.get("total_trades", 0),
                    })

            configs_results.append({
                "config_index": i,
                "config": cfg,
                "slug_count": len(cfg_digests),
                "avg_metrics": avg_metrics,
                "slug_metrics": slug_metrics,
            })

        rounds_summary.append({
            "round": r.round_number,
            "configs_count": len(r.configs),
            "runs_completed": len(r.digests),
            "best_metric_value": r.best_metric_value,
            "ai_reasoning": r.ai_reasoning,
            "duration_ms": round(r.duration_ms, 1),
            "configs_results": configs_results,
        })

    return {
        "task_id": task.task_id,
        "strategy": task.strategy,
        "slugs": task.slugs,
        "status": task.status,
        "optimize_target": task.optimize_target,
        "max_rounds": task.max_rounds,
        "current_round": task.current_round,
        "completed_runs": task.completed_runs,
        "total_runs": task.total_runs,
        "created_at": task.created_at,
        "error": task.error,
        "errors": task.errors,
        "persist_errors": task.persist_errors,
        "best_config": task.best_config,
        "best_metric": task.best_metric if task.best_metric != float("-inf") else None,
        "best_session_id": task.best_session_id,
        "market_profiles": task.market_profiles,
        "rounds": rounds_summary,
        "ai_messages": task.ai_messages,
    }


@router.post("/{task_id}/stop")
async def stop_optimization(task_id: str):
    """Stop a running optimization task early (keeps results so far)."""
    if state.ai_optimizer is None:
        raise HTTPException(status_code=503, detail="AI optimizer not initialized")

    ok = state.ai_optimizer.cancel(task_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Task not found")

    return {"task_id": task_id, "status": "cancelled"}
