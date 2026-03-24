"""Redis async client wrapper for mock trading data."""

from __future__ import annotations

import json
from typing import Any

import redis.asyncio as aioredis

from app.config import settings

_redis: aioredis.Redis | None = None


async def init_redis() -> None:
    global _redis
    _redis = aioredis.from_url(settings.redis_url, decode_responses=True)


async def close_redis() -> None:
    global _redis
    if _redis:
        await _redis.close()
        _redis = None


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


async def get_trades(start: float = 0, end: float = float("inf"), offset: int = 0, limit: int = 50) -> list[dict]:
    raw = await get_redis().zrangebyscore(TRADES_KEY, min=start, max=end, start=offset, num=limit)
    return [json.loads(r) for r in raw]


async def get_trades_count(start: float = 0, end: float = float("inf")) -> int:
    return await get_redis().zcount(TRADES_KEY, min=start, max=end)


# ── Watched markets ─────────────────────────────────────────────────────────

WATCHED_MARKETS_KEY = "watched:markets"


async def add_watched_market(token_id: str, market_id: str = "") -> None:
    await get_redis().hset(WATCHED_MARKETS_KEY, token_id, market_id)


async def get_watched_markets() -> dict[str, str]:
    return await get_redis().hgetall(WATCHED_MARKETS_KEY)


async def remove_watched_market(token_id: str) -> None:
    await get_redis().hdel(WATCHED_MARKETS_KEY, token_id)
