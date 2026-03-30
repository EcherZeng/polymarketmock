"""Results query API."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from api.execution import get_results_store

router = APIRouter()


@router.get("/results")
async def list_results():
    """List all backtest results (summary only)."""
    store = get_results_store()
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
    store = get_results_store()
    result = store.get(session_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Result not found")
    return result


@router.get("/results/{session_id}/metrics")
async def get_metrics(session_id: str):
    """Get only evaluation metrics."""
    store = get_results_store()
    result = store.get(session_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Result not found")
    return result.get("metrics", {})


@router.get("/results/{session_id}/equity")
async def get_equity(session_id: str):
    """Get equity curve data."""
    store = get_results_store()
    result = store.get(session_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Result not found")
    return result.get("equity_curve", [])


@router.get("/results/{session_id}/drawdown")
async def get_drawdown(session_id: str):
    """Get drawdown curve data."""
    store = get_results_store()
    result = store.get(session_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Result not found")
    return result.get("drawdown_curve", [])


@router.get("/results/{session_id}/trades")
async def get_trades(session_id: str):
    """Get trade details."""
    store = get_results_store()
    result = store.get(session_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Result not found")
    return result.get("trades", [])


@router.get("/results/{session_id}/positions")
async def get_positions(session_id: str):
    """Get position curve data."""
    store = get_results_store()
    result = store.get(session_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Result not found")
    return result.get("position_curve", [])


@router.delete("/results/{session_id}")
async def delete_result(session_id: str):
    """Delete a single result."""
    store = get_results_store()
    if session_id not in store:
        raise HTTPException(status_code=404, detail="Result not found")
    del store[session_id]
    return {"deleted": session_id}


@router.delete("/results")
async def clear_results():
    """Clear all results."""
    store = get_results_store()
    count = len(store)
    store.clear()
    return {"deleted": count}
