"""Trading API routes — public RESTful endpoints for mock trading."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from app.models.trading import (
    EstimateRequest,
    EstimateResult,
    OrderRequest,
    OrderResult,
    OrderType,
    SettleRequest,
)
from app.services import matching_engine
from app.services.settlement import settle_market
from app.storage import redis_store

router = APIRouter()


@router.post("/order", response_model=OrderResult)
async def place_order(req: OrderRequest):
    """Place a market or limit order."""
    if req.type == OrderType.LIMIT:
        if req.price is None:
            raise HTTPException(status_code=400, detail="Limit order requires a price")
        return await matching_engine.place_limit_order(req)
    return await matching_engine.execute_market_order(req)


@router.post("/estimate", response_model=EstimateResult)
async def estimate_order(req: EstimateRequest):
    """Estimate execution without placing order."""
    return await matching_engine.estimate_order(req)


@router.get("/orders")
async def list_orders():
    """List all orders (including history)."""
    orders = await redis_store.get_all_orders()
    orders.sort(key=lambda o: o.get("created_at", ""), reverse=True)
    return orders


@router.get("/orders/pending")
async def list_pending_orders():
    """List pending limit orders."""
    return await redis_store.get_pending_orders()


@router.delete("/orders/{order_id}")
async def cancel_order(order_id: str):
    """Cancel a pending limit order."""
    result = await matching_engine.cancel_limit_order(order_id)
    if not result:
        raise HTTPException(status_code=404, detail="Order not found or not cancellable")
    return result


@router.get("/history")
async def trade_history(
    start: float = Query(0, description="Start timestamp"),
    end: float = Query(float("inf"), description="End timestamp"),
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    token_id: str | None = Query(None, description="Filter by token ID"),
):
    """Get trade execution history."""
    trades = await redis_store.get_trades(start=start, end=end, offset=offset, limit=limit, token_id=token_id)
    total = await redis_store.get_trades_count(start=start, end=end, token_id=token_id)
    return {"trades": trades, "total": total, "offset": offset, "limit": limit}


@router.post("/settle/{market_id}")
async def settle(market_id: str, req: SettleRequest):
    """Manually settle a market. Provide winning_outcome and token_map."""
    # We need to know which token_ids map to which outcomes.
    # The caller should provide this, or we look it up from market data.
    from app.services.polymarket_proxy import get_market

    try:
        market_data = await get_market(market_id)
    except Exception:
        raise HTTPException(status_code=404, detail="Market not found")

    outcomes = market_data.get("outcomes", [])
    clob_token_ids = market_data.get("clobTokenIds", "")

    if isinstance(outcomes, str):
        import json
        outcomes = json.loads(outcomes)
    if isinstance(clob_token_ids, str):
        token_ids = [t.strip() for t in clob_token_ids.split(",") if t.strip()]
    else:
        token_ids = clob_token_ids

    if len(outcomes) != len(token_ids):
        raise HTTPException(status_code=400, detail="Cannot map outcomes to token IDs")

    token_map = dict(zip(outcomes, token_ids))

    if req.winning_outcome not in token_map:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid outcome '{req.winning_outcome}'. Valid: {list(token_map.keys())}",
        )

    result = await settle_market(market_id, req.winning_outcome, token_map)
    return result
