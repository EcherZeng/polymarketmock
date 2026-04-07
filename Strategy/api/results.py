"""Results query API."""

from __future__ import annotations

import logging
import os
from datetime import datetime, timezone

import httpx
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

import api.state as state
from api.result_store import sanitize_floats

logger = logging.getLogger(__name__)

router = APIRouter()


def _get_store():
    """Get the result store, raising 503 if not initialized."""
    if state.result_store is None:
        raise HTTPException(status_code=503, detail="Result store not initialized")
    return state.result_store


@router.get("/results")
async def list_results():
    """List all backtest results (summary only)."""
    store = _get_store()
    return sanitize_floats([
        {
            "session_id": r["session_id"],
            "strategy": r["strategy"],
            "slug": r["slug"],
            "initial_balance": r["initial_balance"],
            "final_equity": r["final_equity"],
            "status": r["status"],
            "created_at": r["created_at"],
            "duration_seconds": r["duration_seconds"],
            "metrics": r.get("metrics", {}),
        }
        for r in store.values()
    ])


@router.get("/results/{session_id}")
async def get_result(session_id: str):
    """Get full backtest result by session_id."""
    store = _get_store()
    result = store.get(session_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Result not found")
    return sanitize_floats(result)


@router.get("/results/{session_id}/metrics")
async def get_metrics(session_id: str):
    """Get only evaluation metrics."""
    store = _get_store()
    result = store.get(session_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Result not found")
    return result.get("metrics", {})


@router.get("/results/{session_id}/equity")
async def get_equity(session_id: str):
    """Get equity curve data."""
    store = _get_store()
    result = store.get(session_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Result not found")
    return result.get("equity_curve", [])


@router.get("/results/{session_id}/drawdown")
async def get_drawdown(session_id: str):
    """Get drawdown curve data."""
    store = _get_store()
    result = store.get(session_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Result not found")
    return result.get("drawdown_curve", [])


@router.get("/results/{session_id}/drawdown-events")
async def get_drawdown_events(session_id: str):
    """Get drawdown events (peak → trough → recovery episodes)."""
    store = _get_store()
    result = store.get(session_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Result not found")
    return result.get("drawdown_events", [])


@router.get("/results/{session_id}/trades")
async def get_trades(session_id: str):
    """Get trade details."""
    store = _get_store()
    result = store.get(session_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Result not found")
    return result.get("trades", [])


@router.get("/results/{session_id}/positions")
async def get_positions(session_id: str):
    """Get position curve data."""
    store = _get_store()
    result = store.get(session_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Result not found")
    return result.get("position_curve", [])


@router.delete("/results/{session_id}")
async def delete_result(session_id: str):
    """Delete a single result."""
    store = _get_store()
    if not store.delete(session_id):
        raise HTTPException(status_code=404, detail="Result not found")
    return {"deleted": session_id}


@router.delete("/results")
async def clear_results():
    """Clear all results."""
    store = _get_store()
    count = store.clear()
    return {"deleted": count}


# ── Results Cleanup ──────────────────────────────────────────────────────────


@router.get("/results-stats")
async def results_stats():
    """Get statistics about stored results and batch records for the cleanup page."""
    store = _get_store()
    from config import config

    all_results = store.values()

    # Per-result size on disk
    results_dir = config.results_dir
    result_items: list[dict] = []
    total_size_bytes = 0
    for r in all_results:
        sid = r.get("session_id", "")
        fpath = results_dir / f"{sid}.json"
        size_bytes = 0
        if fpath.exists():
            size_bytes = fpath.stat().st_size
        total_size_bytes += size_bytes
        result_items.append({
            "session_id": sid,
            "strategy": r.get("strategy", ""),
            "slug": r.get("slug", ""),
            "created_at": r.get("created_at", ""),
            "final_equity": r.get("final_equity", 0),
            "total_return_pct": r.get("metrics", {}).get("total_return_pct", 0),
            "total_trades": r.get("metrics", {}).get("total_trades", 0),
            "size_kb": round(size_bytes / 1024, 1),
        })

    # Batch records
    batch_items: list[dict] = []
    batch_total_size = 0
    if state.batch_store is not None:
        batches_dir = config.results_dir / "batches"
        for b in state.batch_store.values():
            bid = b.get("batch_id", "")
            fpath = batches_dir / f"{bid}.json"
            size_bytes = 0
            if fpath.exists():
                size_bytes = fpath.stat().st_size
            batch_total_size += size_bytes
            batch_items.append({
                "batch_id": bid,
                "strategy": b.get("strategy", ""),
                "status": b.get("status", ""),
                "total": b.get("total", 0),
                "completed": b.get("completed", 0),
                "created_at": b.get("created_at", ""),
                "slugs_count": len(b.get("slugs", [])),
                "results_count": len(b.get("results", {})),
                "size_kb": round(size_bytes / 1024, 1),
            })

    # In-memory batch runner tasks count
    runner_tasks_count = 0
    runner_running_count = 0
    if state.batch_runner is not None:
        for t in state.batch_runner.list_tasks():
            runner_tasks_count += 1
            if t.status == "running":
                runner_running_count += 1

    return {
        "results_count": len(result_items),
        "results_total_size_mb": round(total_size_bytes / (1024 * 1024), 2),
        "results": result_items,
        "batches_count": len(batch_items),
        "batches_total_size_mb": round(batch_total_size / (1024 * 1024), 2),
        "batches": batch_items,
        "runner_tasks_in_memory": runner_tasks_count,
        "runner_tasks_running": runner_running_count,
    }


class BulkDeleteRequest(BaseModel):
    session_ids: list[str] = Field(default_factory=list)


@router.post("/results-cleanup")
async def cleanup_results(req: BulkDeleteRequest):
    """Delete multiple results by session_ids."""
    store = _get_store()
    deleted: list[str] = []
    not_found: list[str] = []
    for sid in req.session_ids:
        if store.delete(sid):
            deleted.append(sid)
        else:
            not_found.append(sid)
    return {
        "deleted": deleted,
        "not_found": not_found,
        "deleted_count": len(deleted),
    }


@router.post("/results-cleanup/by-batch/{batch_id}")
async def cleanup_by_batch(batch_id: str):
    """Delete all results associated with a batch, plus the batch record itself."""
    store = _get_store()

    # Find session_ids from batch record
    batch_data = state.batch_store.get(batch_id) if state.batch_store else None
    if batch_data is None:
        raise HTTPException(status_code=404, detail="Batch not found")

    results_map: dict = batch_data.get("results", {})
    deleted: list[str] = []
    for slug, summary in results_map.items():
        sid = summary.get("session_id", "")
        if sid and store.delete(sid):
            deleted.append(sid)

    # Delete batch record
    batch_deleted = False
    if state.batch_store is not None:
        batch_deleted = state.batch_store.delete(batch_id)

    # Purge from batch runner memory
    if state.batch_runner is not None:
        state.batch_runner.purge_task(batch_id)

    return {
        "batch_id": batch_id,
        "batch_deleted": batch_deleted,
        "results_deleted": deleted,
        "results_deleted_count": len(deleted),
    }


class BatchBulkDeleteRequest(BaseModel):
    batch_ids: list[str] = Field(default_factory=list)


@router.post("/results-cleanup/batches")
async def cleanup_batches(req: BatchBulkDeleteRequest):
    """Delete multiple batch records and their associated results."""
    store = _get_store()
    deleted_batches: list[str] = []
    deleted_results: list[str] = []

    for batch_id in req.batch_ids:
        batch_data = state.batch_store.get(batch_id) if state.batch_store else None
        if batch_data is None:
            continue
        results_map: dict = batch_data.get("results", {})
        for slug, summary in results_map.items():
            sid = summary.get("session_id", "")
            if sid and store.delete(sid):
                deleted_results.append(sid)
        if state.batch_store is not None and state.batch_store.delete(batch_id):
            deleted_batches.append(batch_id)
        if state.batch_runner is not None:
            state.batch_runner.purge_task(batch_id)

    return {
        "deleted_batches": deleted_batches,
        "deleted_batches_count": len(deleted_batches),
        "deleted_results": deleted_results,
        "deleted_results_count": len(deleted_results),
    }


@router.post("/results-cleanup/purge-memory")
async def purge_runner_memory():
    """Purge completed/cancelled batch tasks from the in-memory runner registry."""
    if state.batch_runner is None:
        return {"purged": 0}
    count = state.batch_runner.purge_completed()
    return {"purged": count}


# ── BTC Kline (Binance) ─────────────────────────────────────────────────────

BINANCE_KLINE_URL = "https://api.binance.com/api/v3/klines"


def _iso_to_ms(ts: str) -> int:
    """Convert ISO 8601 timestamp string to milliseconds since epoch."""
    dt = datetime.fromisoformat(ts)
    return int(dt.timestamp() * 1000)


@router.get("/results/{session_id}/btc-klines")
async def get_btc_klines(session_id: str):
    """Fetch BTC/USDT 1m klines from Binance for the session's time range."""
    store = _get_store()
    result = store.get(session_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Result not found")

    # Determine time range from equity_curve or price_curve
    equity_curve = result.get("equity_curve", [])
    price_curve = result.get("price_curve", [])
    source = equity_curve if equity_curve else price_curve
    if not source:
        raise HTTPException(status_code=400, detail="No time series data in result")

    start_ts = source[0]["timestamp"]
    end_ts = source[-1]["timestamp"]
    start_ms = _iso_to_ms(start_ts)
    end_ms = _iso_to_ms(end_ts)

    # Fetch from Binance
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(
                BINANCE_KLINE_URL,
                params={
                    "symbol": "BTCUSDT",
                    "interval": "1m",
                    "startTime": start_ms,
                    "endTime": end_ms,
                    "limit": 1000,
                },
            )
            resp.raise_for_status()
            raw = resp.json()
    except httpx.HTTPError as e:
        logger.warning("Binance kline request failed: %s", e)
        raise HTTPException(status_code=502, detail=f"Binance API error: {e}")

    # Transform to structured response
    klines = []
    for k in raw:
        klines.append({
            "open_time": k[0],
            "open": float(k[1]),
            "high": float(k[2]),
            "low": float(k[3]),
            "close": float(k[4]),
            "volume": float(k[5]),
            "close_time": k[6],
            "quote_volume": float(k[7]),
            "trades": k[8],
        })

    return {
        "symbol": "BTCUSDT",
        "interval": "1m",
        "start_time": start_ts,
        "end_time": end_ts,
        "klines": klines,
    }
