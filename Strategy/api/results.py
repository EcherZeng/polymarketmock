"""Results query API."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

import api.state as state

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
    return [
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
    ]


@router.get("/results/{session_id}")
async def get_result(session_id: str):
    """Get full backtest result by session_id."""
    store = _get_store()
    result = store.get(session_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Result not found")
    return result


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
