"""Redis async client wrapper for mock trading data."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any

import redis.asyncio as aioredis

from app.config import settings

logger = logging.getLogger(__name__)

_redis: aioredis.Redis | None = None


async def init_redis() -> None:
    global _redis
    _redis = aioredis.from_url(settings.redis_url, decode_responses=True)
    # Verify connectivity
    try:
        await _redis.ping()
        logger.info("Redis connected: %s", settings.redis_url)
    except Exception as e:
        logger.error("Redis connection failed: %s", e)
        raise


async def close_redis() -> None:
    global _redis
    if _redis:
        await _redis.close()
        _redis = None
        logger.info("Redis connection closed")


def get_redis() -> aioredis.Redis:
    if _redis is None:
        raise RuntimeError("Redis not initialised — call init_redis() first")
    return _redis


# ── Cache helpers (for market data) ──────────────────────────────────────────

async def cache_get(key: str) -> str | None:
    return await get_redis().get(key)


async def cache_set(key: str, value: str, ttl: int) -> None:
    await get_redis().set(key, value, ex=ttl)


# ── Account ──────────────────────────────────────────────────────────────────

ACCOUNT_BALANCE_KEY = "account:balance"
ACCOUNT_CONFIG_KEY = "account:config"
ACCOUNT_REALIZED_PNL_KEY = "account:realized_pnl"


async def get_balance() -> float:
    val = await get_redis().get(ACCOUNT_BALANCE_KEY)
    return float(val) if val else 0.0


async def set_balance(balance: float) -> None:
    await get_redis().set(ACCOUNT_BALANCE_KEY, str(balance))


async def adjust_balance(delta: float) -> float:
    """Atomically adjust balance by delta and return new balance."""
    r = get_redis()
    new_val = await r.incrbyfloat(ACCOUNT_BALANCE_KEY, delta)
    return float(new_val)


async def get_initial_balance() -> float:
    val = await get_redis().hget(ACCOUNT_CONFIG_KEY, "initial_balance")
    return float(val) if val else 0.0


async def set_initial_balance(balance: float) -> None:
    await get_redis().hset(ACCOUNT_CONFIG_KEY, "initial_balance", str(balance))


async def get_realized_pnl() -> float:
    val = await get_redis().get(ACCOUNT_REALIZED_PNL_KEY)
    return float(val) if val else 0.0


async def adjust_realized_pnl(delta: float) -> float:
    new_val = await get_redis().incrbyfloat(ACCOUNT_REALIZED_PNL_KEY, delta)
    return float(new_val)


# ── Positions ────────────────────────────────────────────────────────────────

POSITION_PREFIX = "account:positions:"


def _pos_key(token_id: str) -> str:
    return f"{POSITION_PREFIX}{token_id}"


async def get_position(token_id: str) -> dict[str, Any] | None:
    data = await get_redis().hgetall(_pos_key(token_id))
    return data if data else None


async def set_position(token_id: str, shares: float, avg_cost: float, side: str) -> None:
    await get_redis().hset(
        _pos_key(token_id),
        mapping={"shares": str(shares), "avg_cost": str(avg_cost), "side": side},
    )


async def delete_position(token_id: str) -> None:
    await get_redis().delete(_pos_key(token_id))


async def get_all_positions() -> dict[str, dict[str, Any]]:
    r = get_redis()
    positions: dict[str, dict[str, Any]] = {}
    async for key in r.scan_iter(match=f"{POSITION_PREFIX}*"):
        token_id = key.replace(POSITION_PREFIX, "")
        data = await r.hgetall(key)
        if data:
            positions[token_id] = data
    return positions


# ── Orders ───────────────────────────────────────────────────────────────────

ORDERS_ALL_PREFIX = "orders:all:"
ORDERS_PENDING_PREFIX = "orders:pending:"


async def save_order(order_id: str, order_data: dict) -> None:
    r = get_redis()
    await r.set(f"{ORDERS_ALL_PREFIX}{order_id}", json.dumps(order_data))


async def save_pending_order(order_id: str, order_data: dict) -> None:
    r = get_redis()
    await r.set(f"{ORDERS_PENDING_PREFIX}{order_id}", json.dumps(order_data))


async def remove_pending_order(order_id: str) -> None:
    await get_redis().delete(f"{ORDERS_PENDING_PREFIX}{order_id}")


async def get_order(order_id: str) -> dict | None:
    val = await get_redis().get(f"{ORDERS_ALL_PREFIX}{order_id}")
    return json.loads(val) if val else None


async def get_all_orders() -> list[dict]:
    r = get_redis()
    orders: list[dict] = []
    async for key in r.scan_iter(match=f"{ORDERS_ALL_PREFIX}*"):
        val = await r.get(key)
        if val:
            orders.append(json.loads(val))
    return orders


async def get_pending_orders() -> list[dict]:
    r = get_redis()
    orders: list[dict] = []
    async for key in r.scan_iter(match=f"{ORDERS_PENDING_PREFIX}*"):
        val = await r.get(key)
        if val:
            orders.append(json.loads(val))
    return orders


# ── Trade history (sorted set by timestamp) ─────────────────────────────────

TRADES_KEY = "trades:history"


async def add_trade(timestamp_score: float, trade_json: str) -> None:
    await get_redis().zadd(TRADES_KEY, {trade_json: timestamp_score})


async def get_trades(start: float = 0, end: float = float("inf"), offset: int = 0, limit: int = 50, token_id: str | None = None) -> list[dict]:
    if token_id is None:
        raw = await get_redis().zrangebyscore(TRADES_KEY, min=start, max=end, start=offset, num=limit)
        return [json.loads(r) for r in raw]
    # Client-side filter: fetch all in range, then filter + paginate
    raw = await get_redis().zrangebyscore(TRADES_KEY, min=start, max=end)
    filtered = [json.loads(r) for r in raw if json.loads(r).get("token_id") == token_id]
    return filtered[offset:offset + limit]


async def get_trades_count(start: float = 0, end: float = float("inf"), token_id: str | None = None) -> int:
    if token_id is None:
        return await get_redis().zcount(TRADES_KEY, min=start, max=end)
    raw = await get_redis().zrangebyscore(TRADES_KEY, min=start, max=end)
    return sum(1 for r in raw if json.loads(r).get("token_id") == token_id)


# ── Watched markets ─────────────────────────────────────────────────────────

WATCHED_MARKETS_KEY = "watched:markets"


async def add_watched_market(token_id: str, market_id: str = "") -> None:
    await get_redis().hset(WATCHED_MARKETS_KEY, token_id, market_id)


async def get_watched_markets() -> dict[str, str]:
    return await get_redis().hgetall(WATCHED_MARKETS_KEY)


async def remove_watched_market(token_id: str) -> None:
    await get_redis().hdel(WATCHED_MARKETS_KEY, token_id)


# ── Realtime trades (inferred from orderbook diffs) ─────────────────────────

REALTIME_TRADES_PREFIX = "realtime:trades:"


async def add_realtime_trade(token_id: str, timestamp_score: float, trade_json: str) -> None:
    await get_redis().zadd(f"{REALTIME_TRADES_PREFIX}{token_id}", {trade_json: timestamp_score})


async def get_realtime_trades(
    token_id: str,
    since: float = 0,
    limit: int = 30,
) -> list[dict]:
    raw = await get_redis().zrangebyscore(
        f"{REALTIME_TRADES_PREFIX}{token_id}",
        min=since,
        max=float("inf"),
        start=0,
        num=limit,
    )
    return [json.loads(r) for r in reversed(raw)]


async def trim_realtime_trades(token_id: str, max_count: int) -> None:
    key = f"{REALTIME_TRADES_PREFIX}{token_id}"
    count = await get_redis().zcard(key)
    if count > max_count:
        await get_redis().zremrangebyrank(key, 0, count - max_count - 1)


# ── Live trades (real on-chain trades from Data API) ────────────────────────

LIVE_TRADES_PREFIX = "live:trades:"
LIVE_SEEN_PREFIX = "live:seen:"


async def add_live_trade(market_id: str, timestamp_score: float, trade_json: str) -> None:
    await get_redis().zadd(f"{LIVE_TRADES_PREFIX}{market_id}", {trade_json: timestamp_score})


async def get_live_trades(
    market_id: str,
    since: float = 0,
    limit: int = 30,
    offset: int = 0,
) -> list[dict]:
    """Return latest live trades, newest first."""
    raw = await get_redis().zrevrangebyscore(
        f"{LIVE_TRADES_PREFIX}{market_id}",
        max=float("inf"),
        min=since,
        start=offset,
        num=limit,
    )
    return [json.loads(r) for r in raw]


async def get_live_trades_count(market_id: str) -> int:
    return await get_redis().zcard(f"{LIVE_TRADES_PREFIX}{market_id}")


async def trim_live_trades(market_id: str, max_count: int) -> None:
    key = f"{LIVE_TRADES_PREFIX}{market_id}"
    count = await get_redis().zcard(key)
    if count > max_count:
        await get_redis().zremrangebyrank(key, 0, count - max_count - 1)


async def is_live_trade_seen(market_id: str, tx_hash: str) -> bool:
    return await get_redis().sismember(f"{LIVE_SEEN_PREFIX}{market_id}", tx_hash)


async def mark_live_trade_seen(market_id: str, tx_hash: str) -> None:
    await get_redis().sadd(f"{LIVE_SEEN_PREFIX}{market_id}", tx_hash)


# ── Event status ─────────────────────────────────────────────────────────────

EVENT_STATUS_PREFIX = "event:status:"


async def set_event_status(event_slug: str, status: str) -> None:
    await get_redis().set(f"{EVENT_STATUS_PREFIX}{event_slug}", status, ex=5)


async def get_event_status(event_slug: str) -> str | None:
    return await get_redis().get(f"{EVENT_STATUS_PREFIX}{event_slug}")


# ── Token → Market mapping ──────────────────────────────────────────────────

TOKEN_MARKET_PREFIX = "token:market:"


async def set_token_market_info(token_id: str, market_json: str) -> None:
    await get_redis().set(f"{TOKEN_MARKET_PREFIX}{token_id}", market_json)


async def get_token_market_info(token_id: str) -> dict | None:
    val = await get_redis().get(f"{TOKEN_MARKET_PREFIX}{token_id}")
    return json.loads(val) if val else None


# ── Orderbook prev-snapshot (for trade feed diff) ───────────────────────────

PREV_BOOK_PREFIX = "prev:book:"


async def set_prev_orderbook(token_id: str, book_json: str) -> None:
    await get_redis().set(f"{PREV_BOOK_PREFIX}{token_id}", book_json, ex=60)


async def get_prev_orderbook(token_id: str) -> dict | None:
    val = await get_redis().get(f"{PREV_BOOK_PREFIX}{token_id}")
    return json.loads(val) if val else None


# ── Archived events ──────────────────────────────────────────────────────────

ARCHIVE_PREFIX = "archive:events:"


async def set_archive_meta(slug: str, meta_json: str) -> None:
    await get_redis().set(f"{ARCHIVE_PREFIX}{slug}", meta_json)


async def get_archive_meta(slug: str) -> dict | None:
    val = await get_redis().get(f"{ARCHIVE_PREFIX}{slug}")
    return json.loads(val) if val else None


async def list_archive_slugs() -> list[str]:
    r = get_redis()
    slugs: list[str] = []
    async for key in r.scan_iter(match=f"{ARCHIVE_PREFIX}*"):
        slugs.append(key.replace(ARCHIVE_PREFIX, ""))
    return slugs


async def delete_archive_meta(slug: str) -> bool:
    """Delete archive metadata from Redis. Returns True if the key existed."""
    return bool(await get_redis().delete(f"{ARCHIVE_PREFIX}{slug}"))


async def soft_delete_archive_meta(slug: str) -> bool:
    """Soft-delete: set deleted flag on archive meta. Returns True if key existed."""
    val = await get_redis().get(f"{ARCHIVE_PREFIX}{slug}")
    if not val:
        return False
    meta = json.loads(val)
    meta["deleted"] = True
    meta["deleted_at"] = datetime.now(timezone.utc).isoformat()
    await get_redis().set(f"{ARCHIVE_PREFIX}{slug}", json.dumps(meta))
    return True


# ── Recording sessions (WS data completeness tracking) ──────────────────────

RECORDING_SESSION_PREFIX = "recording:session:"


async def set_recording_session(slug: str, session_json: str) -> None:
    await get_redis().set(f"{RECORDING_SESSION_PREFIX}{slug}", session_json)


async def get_recording_session(slug: str) -> dict | None:
    val = await get_redis().get(f"{RECORDING_SESSION_PREFIX}{slug}")
    return json.loads(val) if val else None


async def delete_recording_session(slug: str) -> None:
    await get_redis().delete(f"{RECORDING_SESSION_PREFIX}{slug}")


# ── Replay sessions ─────────────────────────────────────────────────────────

REPLAY_SESSION_PREFIX = "replay:session:"


async def set_replay_session(session_id: str, session_json: str, ttl: int = 3600) -> None:
    await get_redis().set(f"{REPLAY_SESSION_PREFIX}{session_id}", session_json, ex=ttl)


async def get_replay_session(session_id: str) -> dict | None:
    val = await get_redis().get(f"{REPLAY_SESSION_PREFIX}{session_id}")
    return json.loads(val) if val else None


# ── Recording lock (per-tab ownership) ──────────────────────────────────────

RECORDING_LOCK_PREFIX = "recording:lock:"
RECORDING_LOCK_TTL = 15  # seconds — must be refreshed via heartbeat


async def acquire_recording_lock(slug: str, client_id: str) -> bool:
    """Try to claim recording ownership. Returns True if acquired (or already owned)."""
    key = f"{RECORDING_LOCK_PREFIX}{slug}"
    r = get_redis()
    # SET NX — only set if key doesn't exist
    acquired = await r.set(key, client_id, nx=True, ex=RECORDING_LOCK_TTL)
    if acquired:
        return True
    # Already exists — check if we already own it
    owner = await r.get(key)
    if owner == client_id:
        await r.expire(key, RECORDING_LOCK_TTL)
        return True
    return False


async def refresh_recording_lock(slug: str, client_id: str) -> bool:
    """Refresh lock TTL if caller is the owner. Returns True if still owned."""
    key = f"{RECORDING_LOCK_PREFIX}{slug}"
    r = get_redis()
    owner = await r.get(key)
    if owner == client_id:
        await r.expire(key, RECORDING_LOCK_TTL)
        return True
    return False


async def release_recording_lock(slug: str, client_id: str) -> bool:
    """Release lock if caller is the owner. Returns True if released."""
    key = f"{RECORDING_LOCK_PREFIX}{slug}"
    r = get_redis()
    owner = await r.get(key)
    if owner == client_id:
        await r.delete(key)
        return True
    return False


async def get_recording_lock_owner(slug: str) -> str | None:
    """Return the client_id that currently holds the recording lock, or None."""
    return await get_redis().get(f"{RECORDING_LOCK_PREFIX}{slug}")


# ── Auto-record config & state ──────────────────────────────────────────────

AUTO_RECORD_CONFIG_KEY = "auto-record:config"
AUTO_RECORD_STATE_PREFIX = "auto-record:state:"


async def get_auto_record_config() -> list[str]:
    """Return list of active durations, e.g. ["5m", "15m"]."""
    val = await get_redis().get(AUTO_RECORD_CONFIG_KEY)
    if not val:
        return []
    try:
        return json.loads(val)
    except (json.JSONDecodeError, TypeError):
        return []


async def set_auto_record_config(durations: list[str]) -> None:
    await get_redis().set(AUTO_RECORD_CONFIG_KEY, json.dumps(durations))


async def get_auto_record_state(duration: str) -> dict | None:
    val = await get_redis().get(f"{AUTO_RECORD_STATE_PREFIX}{duration}")
    if not val:
        return None
    try:
        return json.loads(val)
    except (json.JSONDecodeError, TypeError):
        return None


async def set_auto_record_state(duration: str, state_json: str) -> None:
    await get_redis().set(f"{AUTO_RECORD_STATE_PREFIX}{duration}", state_json)


async def delete_auto_record_state(duration: str) -> None:
    await get_redis().delete(f"{AUTO_RECORD_STATE_PREFIX}{duration}")


# ── Event Registry ───────────────────────────────────────────────────────────

REGISTRY_EVENT_PREFIX = "registry:event:"
REGISTRY_WINDOW_PREFIX = "registry:window:"


async def registry_get_event(slug: str) -> dict | None:
    """Read a cached event from the registry."""
    val = await get_redis().get(f"{REGISTRY_EVENT_PREFIX}{slug}")
    return json.loads(val) if val else None


async def registry_set_event(slug: str, event_json: str, ttl: int = 0) -> None:
    """Write event JSON to registry. ttl=0 means no expiry (ended events)."""
    key = f"{REGISTRY_EVENT_PREFIX}{slug}"
    if ttl > 0:
        await get_redis().set(key, event_json, ex=ttl)
    else:
        await get_redis().set(key, event_json)


async def registry_get_window(duration: str) -> list[str]:
    """Return ordered list of slugs for a duration window."""
    val = await get_redis().get(f"{REGISTRY_WINDOW_PREFIX}{duration}")
    if not val:
        return []
    try:
        return json.loads(val)
    except (json.JSONDecodeError, TypeError):
        return []


async def registry_set_window(duration: str, slugs: list[str]) -> None:
    """Persist the ordered slug list for a duration window."""
    await get_redis().set(f"{REGISTRY_WINDOW_PREFIX}{duration}", json.dumps(slugs))
