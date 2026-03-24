"""Account API routes — balance, positions, PnL."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.models.trading import AccountOverview, InitAccountRequest, Position
from app.services.position_manager import get_account_overview, get_position_detail
from app.storage import redis_store

router = APIRouter()


@router.post("/init")
async def init_account(req: InitAccountRequest):
    """Initialize or reset account with a custom USDC balance."""
    await redis_store.set_balance(req.balance)
    await redis_store.set_initial_balance(req.balance)
    # Reset realized PnL
    r = redis_store.get_redis()
    await r.set(redis_store.ACCOUNT_REALIZED_PNL_KEY, "0")
    return {"status": "ok", "balance": req.balance}


@router.get("", response_model=AccountOverview)
async def get_account():
    """Get account overview with positions and PnL."""
    return await get_account_overview()


@router.get("/positions")
async def list_positions():
    """List all open positions with real-time PnL."""
    overview = await get_account_overview()
    return overview.positions


@router.get("/positions/{token_id}", response_model=Position)
async def get_position(token_id: str):
    """Get details of a specific position."""
    pos = await get_position_detail(token_id)
    if not pos:
        raise HTTPException(status_code=404, detail="No position for this token")
    return pos
