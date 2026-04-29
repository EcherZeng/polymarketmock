"""Control routes — pause, resume, executor mode."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter()

_session_manager = None


def init_control(session_manager) -> None:
    global _session_manager
    _session_manager = session_manager


@router.post("/pause")
async def pause():
    if not _session_manager:
        raise HTTPException(503, "Service not initialised")
    _session_manager.pause()
    return {"paused": True}


@router.post("/resume")
async def resume():
    if not _session_manager:
        raise HTTPException(503, "Service not initialised")
    _session_manager.resume()
    return {"paused": False}


class ModeUpdate(BaseModel):
    mode: str


@router.get("/executor-mode")
async def get_executor_mode():
    from config import settings
    return {"executor_mode": settings.executor_mode}


@router.put("/executor-mode")
async def set_executor_mode(body: ModeUpdate):
    if body.mode not in ("real", "mock"):
        raise HTTPException(422, "mode must be 'real' or 'mock'")
    if not _session_manager:
        raise HTTPException(503, "Service not initialised")
    from config import settings
    from execution.executor_factory import create_executor

    old_mode = settings.executor_mode
    if body.mode == old_mode:
        return {"executor_mode": old_mode, "changed": False}

    old_executor = _session_manager._executor
    await old_executor.stop()

    settings.executor_mode = body.mode
    new_executor = create_executor(body.mode)
    await new_executor.start()

    if body.mode == "real" and new_executor.is_ready:
        real_balance = await new_executor.get_balance()
        if real_balance is not None:
            _session_manager._tracker.set_balance(real_balance)
        await new_executor.check_allowance()

    _session_manager._executor = new_executor
    return {"executor_mode": body.mode, "changed": True}


class BalanceUpdate(BaseModel):
    balance: float


@router.put("/balance")
async def set_balance(body: BalanceUpdate):
    """Set balance (mock mode only)."""
    from config import settings
    if settings.executor_mode != "mock":
        raise HTTPException(403, "Balance setting only available in mock mode")
    if not _session_manager:
        raise HTTPException(503, "Service not initialised")
    if body.balance < 0:
        raise HTTPException(422, "Balance must be non-negative")
    
    _session_manager._tracker.set_balance(body.balance)
    # Also update mock executor's internal balance
    if hasattr(_session_manager._executor, "_mock_balance"):
        _session_manager._executor._mock_balance = body.balance
    
    return {"balance": body.balance, "mode": "mock"}


@router.get("/balance")
async def get_balance():
    """Get current balance."""
    if not _session_manager:
        raise HTTPException(503, "Service not initialised")
    return {
        "balance": _session_manager._tracker.balance,
        "initial_balance": _session_manager._tracker.initial_balance,
    }
