"""Results query API."""

from __future__ import annotations

import logging
from datetime import datetime, timezone

import httpx
from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse

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
