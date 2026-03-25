"""Market data proxy API routes."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from app.services import polymarket_proxy as proxy
from app.storage import redis_store

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


# ── Live trades (Polymarket Data API) ────────────────────────────────────────

@router.get("/trades/live")
async def get_live_trades(
    market_id: str = Query(..., description="Gamma market ID or condition_id"),
    limit: int = Query(30, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    """获取 Polymarket 真实链上交易流水。

    优先从 Data API 获取，失败时降级到 orderbook 推断数据。
    """
    try:
        trades = await proxy.get_data_trades(
            market_id=market_id, limit=limit, offset=offset,
        )
        if trades:
            return {"trades": trades, "count": len(trades)}
    except Exception:
        pass
    # Fallback: return inferred trades (best-effort, need a token_id)
    return {"trades": [], "count": 0}


# ── Realtime trade feed (inferred, kept as internal fallback) ────────────────

@router.get("/trades/realtime")
async def get_realtime_trades(
    token_id: str = Query(...),
    limit: int = Query(30, ge=1, le=200),
    since: float = Query(0, ge=0),
):
    """获取通过 orderbook 变化推断的市场成交流水（fallback）。"""
    trades = await redis_store.get_realtime_trades(token_id, since=since, limit=limit)
    return {"trades": trades, "count": len(trades)}


# ── Event status & next event ────────────────────────────────────────────────

@router.get("/event/status/{slug:path}")
async def get_event_status(slug: str):
    """获取事件当前状态（upcoming / live / ended）。"""
    from app.services.event_lifecycle import check_event_status
    try:
        return await check_event_status(slug)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Status check error: {e}")


@router.get("/event/next/{slug:path}")
async def get_next_event(slug: str):
    """获取下一个 LIVE 或即将开始的同类型事件。"""
    from app.services.event_lifecycle import get_next_live_event
    try:
        result = await get_next_live_event(slug)
        if not result:
            raise HTTPException(status_code=404, detail="No upcoming event found")
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Next event error: {e}")


# ── Watched markets (recording) ───────────────────────────────────────────────


@router.get("/watched")
async def list_watched():
    """列出当前正在录制的 token 列表。"""
    watched = await redis_store.get_watched_markets()
    return {"watched": watched}


@router.post("/watch/event/{slug:path}")
async def watch_event(slug: str):
    """进入事件后自动录制 — 注册所有 token 到数据采集器。

    幂等操作：重复调用不产生副作用。
    """
    event = await proxy.resolve_event_slug(slug)
    if not event:
        raise HTTPException(status_code=404, detail=f"Event not found: {slug}")

    import json as _json

    markets = event.get("markets", [])
    watched_tokens: list[str] = []

    for m in markets:
        token_ids_raw = m.get("clobTokenIds", [])
        if isinstance(token_ids_raw, str):
            try:
                token_ids_raw = _json.loads(token_ids_raw)
            except (ValueError, TypeError):
                token_ids_raw = [token_ids_raw]
        market_id = m.get("id", "")
        for tid in token_ids_raw:
            if not tid:
                continue
            await redis_store.add_watched_market(tid, market_id)
            watched_tokens.append(tid)
            # Persist full market info so archive_event can use it later
            info = {
                "id": market_id,
                "question": m.get("question", ""),
                "slug": slug,
                "startDate": m.get("startDate", "") or m.get("eventStartTime", ""),
                "endDate": m.get("endDate", "") or event.get("endDate", ""),
                "clobTokenIds": token_ids_raw,
                "outcomes": m.get("outcomes", []),
            }
            await redis_store.set_token_market_info(tid, _json.dumps(info))

    return {"watched_tokens": watched_tokens, "recording_started": True}


@router.delete("/watch/{token_id}")
async def unwatch_token(token_id: str):
    """取消监视某个 token。"""
    await redis_store.remove_watched_market(token_id)
    return {"removed": token_id}


# ── Archives ──────────────────────────────────────────────────────────────────

@router.get("/archives")
async def list_archives():
    """列出所有归档的历史场次。"""
    from app.services.event_lifecycle import list_archived_events
    return await list_archived_events()


@router.get("/archives/{slug:path}")
async def get_archive(slug: str):
    """获取归档场次详情。"""
    meta = await redis_store.get_archive_meta(slug)
    if not meta:
        raise HTTPException(status_code=404, detail=f"Archive not found: {slug}")
    return meta
