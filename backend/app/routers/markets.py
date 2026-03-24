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


@router.get("/search/events")
async def search_events(
    q: str = Query(..., min_length=1, max_length=200, description="搜索关键词（匹配 title/slug）"),
    active_only: bool = Query(True),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    try:
        return await proxy.search_events(query=q, active_only=active_only, limit=limit, offset=offset)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Polymarket API error: {e}")


@router.get("/resolve/{slug:path}")
async def resolve_slug(slug: str):
    """通过 Polymarket URL slug 解析事件详情。

    例：slug = 'btc-updown-5m-1774420800'
    """
    try:
        event = await proxy.resolve_event_slug(slug)
        if not event:
            raise HTTPException(status_code=404, detail=f"Event not found: {slug}")
        return event
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Polymarket API error: {e}")


@router.get("/btc/markets")
async def btc_markets():
    """发现当前活跃的 BTC 涨跌预测市场（按 5m/15m/30m 分组）。"""
    try:
        return await proxy.discover_btc_markets()
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Polymarket API error: {e}")


@router.get("/prices/history")
async def get_prices_history(
    token_id: str = Query(..., description="Token ID (CLOB asset)"),
    interval: str = Query("1m", description="Interval: 1m, 5m, 1h, 1d"),
    fidelity: int = Query(60, ge=1, le=1440, description="Number of data points"),
):
    """获取 CLOB token 的历史价格（OHLC-style）。"""
    try:
        return await proxy.get_prices_history(
            token_id=token_id,
            interval=interval,
            fidelity=fidelity,
        )
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"CLOB API error: {e}")
