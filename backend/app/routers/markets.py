"""Market data proxy API routes."""

from __future__ import annotations

import json

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from app.config import settings
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

    每次请求都从 Data API 获取最新快照，同时将新交易去重写入 Redis sorted set 以
    实现跨轮询的累积。最终返回 API 最新数据 + Redis 历史的合并结果，按时间降序。
    """
    # 1. Fetch fresh snapshot from Data API (NO cache — must see latest trades)
    api_trades: list[dict] = []
    try:
        api_trades = await proxy.get_data_trades_raw(
            market_id=market_id, limit=50, offset=0,
        )
    except Exception:
        pass

    # 2. Seed new API trades into Redis for accumulation (dedup by txHash)
    for t in api_trades:
        tx_hash = t.get("transactionHash", "")
        if not tx_hash:
            continue
        try:
            if await redis_store.is_live_trade_seen(market_id, tx_hash):
                continue
            await redis_store.mark_live_trade_seen(market_id, tx_hash)
            ts = float(t.get("timestamp", 0))
            await redis_store.add_live_trade(market_id, ts, json.dumps(t))
        except Exception:
            continue
    try:
        await redis_store.trim_live_trades(market_id, settings.live_trades_max)
    except Exception:
        pass

    # 3. Read accumulated trades from Redis (includes freshly seeded + historical)
    trades = await redis_store.get_live_trades(
        market_id=market_id, limit=limit, offset=offset,
    )
    if trades:
        total = await redis_store.get_live_trades_count(market_id)
        return {"trades": trades, "count": total}

    # 4. Fallback: Redis unavailable — return raw API snapshot
    if api_trades:
        page = api_trades[offset:offset + limit]
        return {"trades": page, "count": len(api_trades)}
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
async def watch_event(slug: str, client_id: str | None = Query(None)):
    """进入事件后自动录制 — 注册所有 token 到数据采集器。

    幂等操作：重复调用不产生副作用。
    传入 client_id 时尝试获取录制所有权锁（同一事件仅一个标签页显示"录制中"）。
    """
    event = await proxy.resolve_event_slug(slug)
    if not event:
        raise HTTPException(status_code=404, detail=f"Event not found: {slug}")

    from app.services.event_lifecycle import watch_event_tokens
    watched_tokens = await watch_event_tokens(slug, event)

    # Try to acquire recording lock for this tab
    is_owner = False
    if client_id:
        is_owner = await redis_store.acquire_recording_lock(slug, client_id)

    return {
        "watched_tokens": watched_tokens,
        "recording_started": True,
        "is_owner": is_owner,
    }


@router.delete("/watch/{token_id}")
async def unwatch_token(token_id: str):
    """取消监视某个 token。"""
    await redis_store.remove_watched_market(token_id)
    return {"removed": token_id}


class HeartbeatRequest(BaseModel):
    slug: str
    client_id: str


@router.post("/recording/heartbeat")
async def recording_heartbeat(req: HeartbeatRequest):
    """刷新录制锁 TTL，保持当前标签页的录制所有权。"""
    is_owner = await redis_store.refresh_recording_lock(req.slug, req.client_id)
    if not is_owner:
        # Lock expired or stolen — try to re-acquire
        is_owner = await redis_store.acquire_recording_lock(req.slug, req.client_id)
    return {"is_owner": is_owner}


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
    if not meta or meta.get("deleted"):
        raise HTTPException(status_code=404, detail=f"Archive not found: {slug}")
    return meta


@router.delete("/archives/{slug:path}")
async def delete_archive(slug: str):
    """删除归档场次：硬删数据目录，软删索引元数据。"""
    from app.storage.duckdb_store import delete_session

    # 1. 获取元数据（删除前需要 market_id / token_ids 来清理 Redis）
    meta = await redis_store.get_archive_meta(slug)
    if not meta:
        raise HTTPException(status_code=404, detail=f"Archive not found: {slug}")
    market_id = meta.get("market_id", "")
    token_ids: list[str] = meta.get("token_ids", [])

    # 2. 硬删整个 session 目录（live + archive + meta.json）
    delete_session(slug)

    # 3. 硬删交易类 Redis 键
    r = redis_store.get_redis()
    if market_id:
        await r.delete(f"live:trades:{market_id}")
        await r.delete(f"live:seen:{market_id}")
    for tid in token_ids:
        await r.delete(f"realtime:trades:{tid}")
        await r.delete(f"prev:book:{tid}")

    # 4. 软删 Redis archive 元数据（保留 key，标记 deleted=true）
    await redis_store.soft_delete_archive_meta(slug)

    return {"deleted": slug}


# ── Auto-record config ────────────────────────────────────────────────────────


class AutoRecordConfigRequest(BaseModel):
    durations: list[str]


@router.get("/auto-record/config")
async def get_auto_record_config():
    """获取自动录制配置及各时长实时状态。"""
    config = await redis_store.get_auto_record_config()
    states: dict = {}
    from app.services.auto_recorder import VALID_DURATIONS
    for dur in VALID_DURATIONS:
        st = await redis_store.get_auto_record_state(dur)
        if st:
            states[dur] = st
    return {"durations": config, "states": states}


@router.put("/auto-record/config")
async def update_auto_record_config(req: AutoRecordConfigRequest):
    """更新自动录制配置 — 立即生效，不中断正在进行的录制。"""
    from app.services.auto_recorder import VALID_DURATIONS
    durations = [d for d in req.durations if d in VALID_DURATIONS]
    await redis_store.set_auto_record_config(durations)
    # Return updated state
    states: dict = {}
    for dur in VALID_DURATIONS:
        st = await redis_store.get_auto_record_state(dur)
        if st:
            states[dur] = st
    return {"durations": durations, "states": states}
