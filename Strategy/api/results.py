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
from core.btc_data import _iso_to_ms, analyze_btc_hd, compute_rolling_exit_factors, fetch_btc_klines, simulate_factor_exit_equity
from core.types import parse_slug_window

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


class _FirstTradeSummaryReq(BaseModel):
    session_ids: list[str] = Field(..., min_length=1, max_length=500)


def _compute_first_trade(result: dict) -> dict | None:
    """Extract PnL from the first BUY trade in *result*.

    Returns ``{pnl, return_pct, cost, token_id}`` or *None* when
    no BUY exists.
    """
    trades = result.get("trades", [])
    settlement = result.get("settlement_result") or {}
    initial_balance = result.get("initial_balance", 0.0)

    # Find the chronologically first BUY
    first_buy = None
    for t in trades:
        if t.get("side") == "BUY":
            first_buy = t
            break
    if first_buy is None:
        return None

    token_id = first_buy["token_id"]
    cost = first_buy.get("total_cost", 0.0)
    buy_price = first_buy.get("avg_price", 0.0)
    buy_qty = first_buy.get("filled_amount", 0.0)

    # Check if first-buy quantity was (partially) sold later
    sold_qty = 0.0
    sell_revenue = 0.0
    remaining = buy_qty
    for t in trades:
        if t is first_buy:
            continue
        if t.get("token_id") != token_id or t.get("side") != "SELL":
            continue
        can_sell = min(t.get("filled_amount", 0.0), remaining)
        if can_sell <= 0:
            continue
        sell_revenue += can_sell * t.get("avg_price", 0.0)
        sold_qty += can_sell
        remaining -= can_sell
        if remaining <= 0:
            break

    # Settlement PnL for the portion still held at end
    settle_pnl = 0.0
    if remaining > 0 and settlement:
        settle_price = settlement.get(token_id, 0.0)
        settle_pnl = (settle_price - buy_price) * remaining

    trade_pnl = sell_revenue - buy_price * sold_qty
    total_pnl = round(trade_pnl + settle_pnl, 6)
    # Use initial_balance as denominator to stay consistent with total_return_pct
    return_pct = round(total_pnl / initial_balance, 6) if initial_balance > 0 else 0.0

    return {
        "pnl": total_pnl,
        "return_pct": return_pct,
        "cost": round(cost, 6),
        "token_id": token_id,
    }


@router.post("/results/first-trade-summary")
async def first_trade_summary(req: _FirstTradeSummaryReq):
    """Batch-compute first-trade PnL for given session_ids.

    Returns ``{session_id: {pnl, return_pct, cost, token_id} | null}``.
    """
    store = _get_store()
    out: dict[str, dict | None] = {}
    for sid in req.session_ids:
        result = store.get(sid)
        if result is None:
            out[sid] = None
            continue
        out[sid] = _compute_first_trade(result)
    return sanitize_floats(out)


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

    # Build a reverse map: session_id -> batch_id
    # batch_store.values() returns lightweight summaries; need full data
    # for the results sub-dict, so load each batch individually.
    session_to_batch: dict[str, str] = {}
    if state.batch_store is not None:
        for b_summary in state.batch_store.values():
            bid = b_summary.get("batch_id", "")
            if not bid:
                continue
            full = state.batch_store.get(bid)
            if full is None:
                continue
            for _slug, summary in full.get("results", {}).items():
                sid = summary.get("session_id", "")
                if sid:
                    session_to_batch[sid] = bid

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
            "batch_id": session_to_batch.get(sid),
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
                "results_count": b.get("results_count", len(b.get("results", {}))),
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


@router.get("/results/{session_id}/btc-klines")
async def get_btc_klines(session_id: str):
    """Fetch BTC/USDT 1m klines from Binance for the session's time range."""
    store = _get_store()
    result = store.get(session_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Result not found")

    # Determine time range: prefer slug-derived window, fall back to data timestamps
    slug_start = result.get("slug_start", "")
    slug_end = result.get("slug_end", "")
    if not slug_start or not slug_end:
        slug_window = parse_slug_window(result.get("slug", ""))
        if slug_window:
            slug_start, slug_end = slug_window

    if slug_start and slug_end:
        start_ts = slug_start
        end_ts = slug_end
    else:
        # Fallback: use actual data timestamps
        equity_curve = result.get("equity_curve", [])
        price_curve = result.get("price_curve", [])
        source = equity_curve if equity_curve else price_curve
        if not source:
            raise HTTPException(status_code=400, detail="No time series data in result")
        start_ts = source[0]["timestamp"]
        end_ts = source[-1]["timestamp"]

    # Fetch from Binance via shared module
    try:
        klines = await fetch_btc_klines(start_ts, end_ts)
    except Exception as e:
        logger.warning("Binance kline request failed: %s", e)
        raise HTTPException(status_code=502, detail=f"Binance API error: {e}")

    return {
        "symbol": "BTCUSDT",
        "interval": "1m",
        "start_time": start_ts,
        "end_time": end_ts,
        "klines": klines,
    }


@router.post("/results/{session_id}/btc-analyze")
async def btc_hd_analyze(session_id: str):
    """On-demand high-density BTC factor analysis using 1s klines."""
    store = _get_store()
    result = store.get(session_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Result not found")

    slug_start = result.get("slug_start", "")
    slug_end = result.get("slug_end", "")
    if not slug_start or not slug_end:
        slug_window = parse_slug_window(result.get("slug", ""))
        if slug_window:
            slug_start, slug_end = slug_window

    if not slug_start or not slug_end:
        raise HTTPException(status_code=400, detail="Cannot determine session time range")

    config = result.get("config", {})
    w1 = config.get("btc_trend_window_1", 5)
    w2 = config.get("btc_trend_window_2", 10)
    min_mom = config.get("btc_min_momentum", 0.001)

    try:
        analysis = await analyze_btc_hd(slug_start, slug_end, w1, w2, min_mom)
    except Exception as e:
        logger.warning("HD BTC analysis failed: %s", e)
        raise HTTPException(status_code=502, detail=f"Binance API error: {e}")

    return sanitize_floats({
        "session_id": session_id,
        **analysis,
    })


@router.post("/results/{session_id}/exit-analysis")
async def exit_factor_analysis(session_id: str):
    """On-demand rolling BTC factor exit analysis for a single backtest result.

    Computes top-3 factors (direction streak, momentum acceleration, volume
    coupling) on a rolling window over the holding period using 1s BTC klines.
    Simulates factor-based partial exits and compares to actual equity.
    """
    store = _get_store()
    result = store.get(session_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Result not found")

    # ── Determine holding period ─────────────────────────────────────────
    trades = result.get("trades", [])
    buy_fills = [t for t in trades if t.get("side") == "BUY"]
    if not buy_fills:
        return sanitize_floats({
            "session_id": session_id,
            "error": "no_buy_trades",
            "kline_count": 0,
            "factor_timeline": [],
            "summary": {},
        })

    first_buy = buy_fills[0]
    hold_start_ts = first_buy.get("timestamp", "")
    entry_price = float(first_buy.get("avg_price", 0))
    entry_qty = float(first_buy.get("filled_amount", 0))
    token_id = first_buy.get("token_id", "")

    # slug_end as holding end
    slug_end = result.get("slug_end", "")
    if not slug_end:
        slug_window = parse_slug_window(result.get("slug", ""))
        if slug_window:
            slug_end = slug_window[1]
    if not hold_start_ts or not slug_end:
        raise HTTPException(status_code=400, detail="Cannot determine holding period")

    # ── Determine entry direction (BTC-relative) ─────────────────────────
    # If entry price >= 0.5, user is betting UP (bullish BTC) → direction = +1
    # If entry price < 0.5, user is betting DOWN (bearish BTC) → direction = -1
    entry_direction = 1.0 if entry_price >= 0.5 else -1.0

    # ── Fetch 1s BTC klines ──────────────────────────────────────────────
    try:
        klines = await fetch_btc_klines(hold_start_ts, slug_end, interval="1s")
    except Exception as e:
        logger.warning("Exit analysis kline fetch failed: %s", e)
        raise HTTPException(status_code=502, detail=f"Binance API error: {e}")

    if not klines:
        return sanitize_floats({
            "session_id": session_id,
            "error": "no_klines",
            "kline_count": 0,
            "factor_timeline": [],
            "summary": {},
        })

    # ── Compute rolling factors ──────────────────────────────────────────
    hold_start_ms = _iso_to_ms(hold_start_ts)
    hold_end_ms = _iso_to_ms(slug_end)

    factor_timeline = compute_rolling_exit_factors(
        klines, hold_start_ms, hold_end_ms, entry_direction,
    )

    # ── Simulate factor-based equity ─────────────────────────────────────
    price_curve = result.get("price_curve", [])
    initial_balance = float(result.get("initial_balance", 100.0))

    sim = simulate_factor_exit_equity(
        timeline=factor_timeline,
        entry_price=entry_price,
        entry_qty=entry_qty,
        initial_balance=initial_balance,
        price_curve=price_curve,
        token_id=token_id,
    )

    # ── Actual exit info ─────────────────────────────────────────────────
    sell_fills = [t for t in trades if t.get("side") == "SELL"]
    actual_exit_ts: str | None = sell_fills[0].get("timestamp") if sell_fills else None
    actual_exit_equity = float(result.get("final_equity", initial_balance))

    summary = {
        "first_reduce_ts": sim["first_reduce_ts"],
        "first_exit_ts": sim["first_exit_ts"],
        "actual_exit_ts": actual_exit_ts,
        "factor_final_equity": sim["final_equity"],
        "actual_final_equity": actual_exit_equity,
        "equity_diff": round(sim["final_equity"] - actual_exit_equity, 6),
    }

    return sanitize_floats({
        "session_id": session_id,
        "interval": "1s",
        "kline_count": len(klines),
        "hold_start_ts": hold_start_ts,
        "hold_end_ts": slug_end,
        "entry_direction": entry_direction,
        "factor_timeline": factor_timeline,
        "simulated_equity_curve": sim["simulated_equity_curve"],
        "summary": summary,
    })
