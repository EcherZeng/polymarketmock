"""Backtest execution API — single and batch runs."""

from __future__ import annotations

import asyncio
import logging

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from api.state import registry
import api.state as state
from config import config
from core.btc_data import fetch_btc_klines
from core.data_loader import load_archive
from core.evaluator import compute_drawdown_curve, compute_drawdown_events, evaluate
from core.runner import run_backtest
from core.types import BacktestSession, btc_trend_enabled

logger = logging.getLogger(__name__)

router = APIRouter()


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
    cumulative_capital: bool = False


# ── Result helpers ───────────────────────────────────────────────────────────


def store_session(session: BacktestSession) -> dict:
    """Serialize a BacktestSession and persist to the result store.

    Called by single-run endpoint AND by batch runner on_result callback.
    """
    result = _serialize_session(session)
    if state.result_store is not None:
        state.result_store.put(session.session_id, result)
    return result


# ── Single run ───────────────────────────────────────────────────────────────


@router.post("/run")
async def run_single(req: RunRequest):
    """Execute a single backtest (synchronous return)."""
    if not registry.has(req.strategy):
        raise HTTPException(status_code=404, detail=f"Strategy '{req.strategy}' not found")

    # Pre-fetch BTC klines if btc_min_momentum is active
    btc_klines: list[dict] | None = None
    if btc_trend_enabled(req.config):
        try:
            data = await asyncio.to_thread(load_archive, config.data_dir, req.slug)
            # Collect all timestamps to determine time range
            all_ts: set[str] = set()
            for row in (*data.prices, *data.orderbooks, *data.live_trades, *data.ob_deltas):
                ts = row.get("timestamp", "")
                if ts:
                    all_ts.add(ts)
            if all_ts:
                sorted_ts = sorted(all_ts)
                btc_klines = await fetch_btc_klines(sorted_ts[0], sorted_ts[-1])
        except Exception as e:
            logger.warning("BTC klines prefetch failed for %s: %s", req.slug, e)
            # Don't block backtest on BTC data failure

    # Run in thread pool (DuckDB is sync)
    try:
        session = await asyncio.to_thread(
            run_backtest,
            registry,
            req.strategy,
            req.slug,
            req.config,
            req.initial_balance,
            None,  # data
            req.settlement_result,
            btc_klines,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Backtest execution error: {e}")

    # Compute metrics and drawdown
    metrics = evaluate(session)
    session.metrics = metrics
    session.drawdown_curve = compute_drawdown_curve(session.equity_curve)
    session.drawdown_events = compute_drawdown_events(session.equity_curve)

    # Store and persist result
    result = store_session(session)
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
        req.strategy, req.slugs, req.config, req.initial_balance, req.settlement_result,
        cumulative_capital=req.cumulative_capital,
    )

    # Persist initial snapshot immediately so the task is always findable after a
    # server restart, even if the detail page was never opened during the run.
    if state.batch_store is not None:
        task = state.batch_runner.get_task(batch_id)
        if task is not None:
            state.batch_store.put(batch_id, {
                "batch_id": task.batch_id,
                "strategy": task.strategy,
                "slugs": task.slugs,
                "config": task.config,
                "status": task.status,
                "total": task.total,
                "completed": task.completed_count,
                "created_at": task.created_at,
                "cumulative_capital": task.cumulative_capital,
                "capital_chain": task.capital_chain,
                "results": {},
                "errors": {},
                "workflows": {s: _serialize_workflow(wf) for s, wf in task.workflows.items()},
            })

    return {"batch_id": batch_id, "total": len(req.slugs)}


@router.get("/tasks")
async def list_tasks():
    """List all batch tasks (live + persisted)."""
    live: list[dict] = []
    live_ids: set[str] = set()

    # Live tasks from batch runner
    if state.batch_runner is not None:
        for t in state.batch_runner.list_tasks():
            live_ids.add(t.batch_id)
            live.append({
                "batch_id": t.batch_id,
                "strategy": t.strategy,
                "slugs": t.slugs,
                "config": t.config,
                "status": t.status,
                "total": t.total,
                "completed": t.completed_count,
                "created_at": t.created_at,
            })

    # Persisted completed batches (not in live)
    if state.batch_store is not None:
        for b in state.batch_store.values():
            if b.get("batch_id") not in live_ids:
                live.append({
                    "batch_id": b["batch_id"],
                    "strategy": b.get("strategy", ""),
                    "slugs": b.get("slugs", []),
                    "config": b.get("config", {}),
                    "status": b.get("status", "completed"),
                    "total": b.get("total", 0),
                    "completed": b.get("completed", b.get("total", 0)),
                    "created_at": b.get("created_at", ""),
                })

    return live


@router.get("/tasks/{batch_id}")
async def get_task(batch_id: str):
    """Get batch task progress and results with workflow step logs.

    Checks live in-memory task first, falls back to persisted snapshot.
    """
    # ── 1. Try live task from batch runner ────────────────────────────────
    task = None
    if state.batch_runner is not None:
        task = state.batch_runner.get_task(batch_id)

    if task is not None:
        # Ensure individual results are persisted
        results_summary: dict[str, dict] = {}
        for slug, session in task.results.items():
            if state.result_store is not None and session.session_id not in state.result_store:
                store_session(session)
            results_summary[slug] = _build_result_summary(session)

        # Also include summaries from already-released sessions (chunked batch)
        for slug, summary in task.results_summary.items():
            if slug not in results_summary:
                results_summary[slug] = {
                    "session_id": summary.session_id,
                    "status": summary.status,
                    "initial_balance": summary.initial_balance,
                    "final_equity": summary.final_equity,
                    "total_return_pct": summary.total_return_pct,
                    "sharpe_ratio": summary.sharpe_ratio,
                    "total_trades": summary.total_trades,
                    "win_rate": summary.win_rate,
                    "max_drawdown": summary.max_drawdown,
                    "avg_slippage": summary.avg_slippage,
                    "profit_factor": summary.profit_factor,
                }

        # Serialize workflow step logs
        workflows: dict[str, dict] = {}
        for slug, wf in task.workflows.items():
            workflows[slug] = _serialize_workflow(wf)

        response = {
            "batch_id": task.batch_id,
            "strategy": task.strategy,
            "slugs": task.slugs,
            "config": task.config,
            "status": task.status,
            "total": task.total,
            "completed": task.completed_count,
            "created_at": task.created_at,
            "cumulative_capital": task.cumulative_capital,
            "capital_chain": task.capital_chain,
            "results": results_summary,
            "errors": task.errors,
            "persist_errors": task.persist_errors,
            "workflows": workflows,
        }

        # Persist snapshot for future access
        if state.batch_store is not None:
            state.batch_store.put(batch_id, response)

        return response

    # ── 2. Fall back to persisted snapshot ────────────────────────────────
    if state.batch_store is not None:
        snapshot = state.batch_store.get(batch_id)
        if snapshot is not None:
            return snapshot

    raise HTTPException(status_code=404, detail="Batch not found")


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


def _build_result_summary(session: BacktestSession) -> dict:
    """Build a compact result summary for batch task responses."""
    return {
        "session_id": session.session_id,
        "status": session.status,
        "initial_balance": session.initial_balance,
        "final_equity": session.final_equity,
        "total_return_pct": session.metrics.total_return_pct,
        "sharpe_ratio": session.metrics.sharpe_ratio,
        "total_trades": session.metrics.total_trades,
        "win_rate": session.metrics.win_rate,
        "max_drawdown": session.metrics.max_drawdown,
        "avg_slippage": session.metrics.avg_slippage,
        "profit_factor": session.metrics.profit_factor,
    }


def _serialize_workflow(wf) -> dict:
    """Serialize a SlugWorkflow to JSON-safe dict."""
    return {
        "slug": wf.slug,
        "status": wf.status,
        "error": wf.error,
        "steps": [
            {
                "timestamp": s.timestamp,
                "step": s.step,
                "status": s.status,
                "message": s.message,
                "detail": s.detail,
                "duration_ms": s.duration_ms,
            }
            for s in wf.steps
        ],
    }


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
        "btc_trend_info": session.btc_trend_info,
    }
