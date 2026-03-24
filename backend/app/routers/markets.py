"""Market data proxy API routes."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from app.services import polymarket_proxy as proxy

router = APIRouter()


@router.get("/markets")
async def list_markets(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    order: str = Query("volume24hr"),
    ascending: bool = Query(False),
):
    try:
        return await proxy.get_markets(limit=limit, offset=offset, order=order, ascending=ascending)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Polymarket API error: {e}")


@router.get("/markets/{market_id}")
async def get_market(market_id: str):
    try:
        return await proxy.get_market(market_id)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Polymarket API error: {e}")


@router.get("/events")
async def list_events(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    try:
        return await proxy.get_events(limit=limit, offset=offset)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Polymarket API error: {e}")


@router.get("/events/{event_id}")
async def get_event(event_id: str):
    try:
        return await proxy.get_event(event_id)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Polymarket API error: {e}")


@router.get("/orderbook")
async def get_orderbook(token_id: str = Query(...)):
    try:
        return await proxy.get_orderbook(token_id)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Polymarket API error: {e}")


@router.get("/midpoint")
async def get_midpoint(token_id: str = Query(...)):
    try:
        mid = await proxy.get_midpoint(token_id)
        return {"token_id": token_id, "mid": mid}
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Polymarket API error: {e}")
