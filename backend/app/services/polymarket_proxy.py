"""Proxy service for Polymarket Gamma & CLOB APIs with Redis caching."""

from __future__ import annotations

import json

import httpx

from app.config import settings
from app.storage.redis_store import cache_get, cache_set

_client: httpx.AsyncClient | None = None


def _get_client() -> httpx.AsyncClient:
    global _client
    if _client is None or _client.is_closed:
        _client = httpx.AsyncClient(timeout=15.0)
    return _client


# ── Gamma API ────────────────────────────────────────────────────────────────

async def get_markets(
    limit: int = 20,
    offset: int = 0,
    order: str = "volume24hr",
    ascending: bool = False,
) -> list[dict]:
    cache_key = f"gamma:markets:{limit}:{offset}:{order}:{ascending}"
    cached = await cache_get(cache_key)
    if cached:
        return json.loads(cached)

    url = f"{settings.gamma_api_url}/markets"
    params = {"limit": limit, "offset": offset, "order": order, "ascending": str(ascending).lower()}
    resp = await _get_client().get(url, params=params)
    resp.raise_for_status()
    data = resp.json()
    await cache_set(cache_key, json.dumps(data), settings.cache_ttl_markets)
    return data


async def get_market(market_id: str) -> dict:
    cache_key = f"gamma:market:{market_id}"
    cached = await cache_get(cache_key)
    if cached:
        return json.loads(cached)

    url = f"{settings.gamma_api_url}/markets/{market_id}"
    resp = await _get_client().get(url)
    resp.raise_for_status()
    data = resp.json()
    await cache_set(cache_key, json.dumps(data), settings.cache_ttl_markets)
    return data


async def get_events(
    limit: int = 20,
    offset: int = 0,
) -> list[dict]:
    cache_key = f"gamma:events:{limit}:{offset}"
    cached = await cache_get(cache_key)
    if cached:
        return json.loads(cached)

    url = f"{settings.gamma_api_url}/events"
    params = {"limit": limit, "offset": offset}
    resp = await _get_client().get(url, params=params)
    resp.raise_for_status()
    data = resp.json()
    await cache_set(cache_key, json.dumps(data), settings.cache_ttl_markets)
    return data


async def get_event(event_id: str) -> dict:
    cache_key = f"gamma:event:{event_id}"
    cached = await cache_get(cache_key)
    if cached:
        return json.loads(cached)

    url = f"{settings.gamma_api_url}/events/{event_id}"
    resp = await _get_client().get(url)
    resp.raise_for_status()
    data = resp.json()
    await cache_set(cache_key, json.dumps(data), settings.cache_ttl_markets)
    return data


# ── CLOB API ─────────────────────────────────────────────────────────────────

async def get_orderbook(token_id: str) -> dict:
    cache_key = f"clob:book:{token_id}"
    cached = await cache_get(cache_key)
    if cached:
        return json.loads(cached)

    url = f"{settings.clob_api_url}/book"
    resp = await _get_client().get(url, params={"token_id": token_id})
    resp.raise_for_status()
    data = resp.json()
    await cache_set(cache_key, json.dumps(data), settings.cache_ttl_orderbook)
    return data


async def get_midpoint(token_id: str) -> float:
    cache_key = f"clob:mid:{token_id}"
    cached = await cache_get(cache_key)
    if cached:
        return float(cached)

    url = f"{settings.clob_api_url}/midpoint"
    resp = await _get_client().get(url, params={"token_id": token_id})
    resp.raise_for_status()
    data = resp.json()
    mid = float(data.get("mid", 0))
    await cache_set(cache_key, str(mid), settings.cache_ttl_midpoint)
    return mid


async def get_orderbook_raw(token_id: str) -> dict:
    """Fetch orderbook without caching (for matching engine)."""
    url = f"{settings.clob_api_url}/book"
    resp = await _get_client().get(url, params={"token_id": token_id})
    resp.raise_for_status()
    return resp.json()
