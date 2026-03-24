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


# ── Normalization ────────────────────────────────────────────────────────────

_JSON_STR_FIELDS = ("outcomes", "outcomePrices", "clobTokenIds")


def _parse_json_str(value: str) -> list:
    """Safely parse a JSON-encoded string field into a list."""
    if isinstance(value, list):
        return value
    if isinstance(value, str) and value.startswith("["):
        try:
            return json.loads(value)
        except (json.JSONDecodeError, ValueError):
            pass
    return []


def _normalize_market(m: dict) -> dict:
    """Parse JSON-encoded string fields in a Gamma market dict into real lists."""
    for field in _JSON_STR_FIELDS:
        if field in m:
            m[field] = _parse_json_str(m[field])
    return m


def _normalize_event(e: dict) -> dict:
    """Normalize all markets inside an event dict."""
    for m in e.get("markets", []):
        _normalize_market(m)
    return e


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
    data = [_normalize_market(m) for m in data] if isinstance(data, list) else data
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
    data = _normalize_market(resp.json())
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
    data = [_normalize_event(e) for e in resp.json()]
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
    data = _normalize_event(resp.json())
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


# ── Search / Resolve ─────────────────────────────────────────────────────────

async def search_events(
    query: str,
    active_only: bool = True,
    limit: int = 20,
    offset: int = 0,
) -> list[dict]:
    """Fetch events from Gamma API and filter by keyword in title/slug."""
    params: dict = {"limit": 100, "offset": offset, "order": "createdAt", "ascending": "false"}
    if active_only:
        params["active"] = "true"
        params["closed"] = "false"
    url = f"{settings.gamma_api_url}/events"
    resp = await _get_client().get(url, params=params)
    resp.raise_for_status()
    data = resp.json()
    q = query.lower()
    filtered = [
        _normalize_event(e) for e in data
        if q in e.get("title", "").lower() or q in e.get("slug", "").lower()
    ]
    return filtered[:limit]


async def resolve_event_slug(slug: str) -> dict | None:
    """Resolve a Polymarket event slug to its event data."""
    url = f"{settings.gamma_api_url}/events"
    resp = await _get_client().get(url, params={"limit": 1, "slug": slug})
    resp.raise_for_status()
    data = resp.json()
    return _normalize_event(data[0]) if data else None


async def discover_btc_markets() -> dict[str, list[dict]]:
    """Discover active BTC up/down markets grouped by duration (5m, 15m, 30m).

    Uses cache (30s TTL) to avoid excessive Gamma API requests.
    """
    cache_key = "btc:discovery"
    cached = await cache_get(cache_key)
    if cached:
        return json.loads(cached)

    url = f"{settings.gamma_api_url}/events"
    params = {
        "limit": 100,
        "active": "true",
        "closed": "false",
        "order": "createdAt",
        "ascending": "false",
    }
    resp = await _get_client().get(url, params=params)
    resp.raise_for_status()
    all_events = resp.json()

    groups: dict[str, list[dict]] = {"5m": [], "15m": [], "30m": []}
    for e in all_events:
        slug = e.get("slug", "")
        if "btc-updown-5m-" in slug:
            groups["5m"].append(_normalize_event(e))
        elif "btc-updown-15m-" in slug:
            groups["15m"].append(_normalize_event(e))
        elif "btc-updown-30m-" in slug:
            groups["30m"].append(_normalize_event(e))

    # Keep only the most recent per group
    for key in groups:
        groups[key] = groups[key][:10]

    await cache_set(cache_key, json.dumps(groups), 30)
    return groups
