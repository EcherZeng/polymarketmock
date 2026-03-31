"""Backtest execution API — single and batch runs."""

from __future__ import annotations

import asyncio

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from api.state import registry
import api.state as state
from config import config
from core.data_loader import load_archive
from core.evaluator import compute_drawdown_curve, compute_drawdown_events, evaluate
from core.runner import run_backtest

router = APIRouter()

# ── In-memory results store ──────────────────────────────────────────────────

_results: dict[str, dict] = {}  # session_id → serialised result


# ── Request models ───────────────────────────────────────────────────────────


class RunRequest(BaseModel):
    strategy: str
    slug: str
    initial_balance: float = Field(default=10000, gt=0)
    config: dict = Field(default_factory=dict)
    settlement_result: dict[str, float] | None = None


class BatchRequest(BaseModel):
    strategy: str
    slugs: list[str]
    initial_balance: float = Field(default=10000, gt=0)
    config: dict = Field(default_factory=dict)
    settlement_result: dict[str, float] | None = None


# ── Single run ───────────────────────────────────────────────────────────────


@router.post("/run")
async def run_single(req: RunRequest):
    """Execute a single backtest (synchronous return)."""
    if not registry.has(req.strategy):
        raise HTTPException(status_code=404, detail=f"Strategy '{req.strategy}' not found")

    # Run in thread pool (DuckDB is sync)
    session = await asyncio.to_thread(
        run_backtest,
        registry,
        req.strategy,
        req.slug,
        req.config,
        req.initial_balance,
        None,  # data
        req.settlement_result,
    )

    if session.status == "failed":
        raise HTTPException(status_code=400, detail="Backtest failed — check data or strategy")

    # Compute metrics and drawdown
    metrics = evaluate(session)
    session.metrics = metrics
    session.drawdown_curve = compute_drawdown_curve(session.equity_curve)
    session.drawdown_events = compute_drawdown_events(session.equity_curve)

    # Store result
    result = _serialize_session(session)
    _results[session.session_id] = result
    return result


# ── Batch ────────────────────────────────────────────────────────────────────


@router.post("/batch")
async def run_batch(req: BatchRequest):
    """Submit a batch of backtests (async, returns batch_id)."""
    if not registry.has(req.strategy):
        raise HTTPException(status_code=404, detail=f"Strategy '{req.strategy}' not found")
    if state.batch_runner is None:
        raise HTTPException(status_code=503, detail="Batch runner not initialized")

    batch_id = await state.batch_runner.submit(
        req.strategy, req.slugs, req.config, req.initial_balance,
    )
    return {"batch_id": batch_id, "total": len(req.slugs)}


@router.get("/tasks")
async def list_tasks():
    """List all batch tasks."""
    if state.batch_runner is None:
        return []
    return [
        {
            "batch_id": t.batch_id,
            "strategy": t.strategy,
            "slugs": t.slugs,
            "status": t.status,
            "total": t.total,
            "completed": t.completed_count,
            "created_at": t.created_at,
        }
        for t in state.batch_runner.list_tasks()
    ]


@router.get("/tasks/{batch_id}")
async def get_task(batch_id: str):
    """Get batch task progress and results."""
    if state.batch_runner is None:
        raise HTTPException(status_code=503, detail="Batch runner not initialized")
    task = state.batch_runner.get_task(batch_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Batch not found")

    # Evaluate and store completed results
    results_summary: dict[str, dict] = {}
    for slug, session in task.results.items():
        if session.session_id not in _results:
            metrics = evaluate(session)
            session.metrics = metrics
            session.drawdown_curve = compute_drawdown_curve(session.equity_curve)
            session.drawdown_events = compute_drawdown_events(session.equity_curve)
            _results[session.session_id] = _serialize_session(session)
        results_summary[slug] = {
            "session_id": session.session_id,
            "status": session.status,
            "total_return_pct": session.metrics.total_return_pct,
            "sharpe_ratio": session.metrics.sharpe_ratio,
            "total_trades": session.metrics.total_trades,
        }

    return {
        "batch_id": task.batch_id,
        "strategy": task.strategy,
        "slugs": task.slugs,
        "status": task.status,
        "total": task.total,
        "completed": task.completed_count,
        "created_at": task.created_at,
        "results": results_summary,
        "errors": task.errors,
    }


@router.post("/tasks/{batch_id}/cancel")
async def cancel_task(batch_id: str):
    """Cancel a running batch task."""
    if state.batch_runner is None:
        raise HTTPException(status_code=503, detail="Batch runner not initialized")
    ok = state.batch_runner.cancel(batch_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Batch not found")
    return {"batch_id": batch_id, "status": "cancelled"}


# ── Helpers ──────────────────────────────────────────────────────────────────


def get_results_store() -> dict[str, dict]:
    return _results


def _serialize_session(session) -> dict:
    """Serialize BacktestSession to JSON-safe dict."""
    from dataclasses import asdict
    from core.types import EvaluationMetrics

    metrics = session.metrics
    return {
        "session_id": session.session_id,
        "strategy": session.strategy,
        "slug": session.slug,
        "initial_balance": session.initial_balance,
        "status": session.status,
        "created_at": session.created_at,
        "duration_seconds": session.duration_seconds,
        "final_equity": session.final_equity,
        "config": session.config,
        "metrics": asdict(metrics) if isinstance(metrics, EvaluationMetrics) else metrics,
        "summary": {
            "total_ticks": len(session.equity_curve),
            "buy_count": metrics.buy_count if isinstance(metrics, EvaluationMetrics) else 0,
            "sell_count": metrics.sell_count if isinstance(metrics, EvaluationMetrics) else 0,
        },
        "trades": [
            {
                "timestamp": t.timestamp,
                "token_id": t.token_id,
                "side": t.side,
                "requested_amount": t.requested_amount,
                "filled_amount": t.filled_amount,
                "avg_price": t.avg_price,
                "total_cost": t.total_cost,
                "slippage_pct": t.slippage_pct,
                "balance_after": t.balance_after,
                "position_after": t.position_after,
            }
            for t in session.trades
        ],
        "equity_curve": session.equity_curve,
        "drawdown_curve": session.drawdown_curve,
        "drawdown_events": session.drawdown_events if session.drawdown_events else [],
        "position_curve": session.position_curve,
        "price_curve": session.price_curve,
        "strategy_summary": session.strategy_summary,
        "settlement_result": session.settlement_result,
    }
