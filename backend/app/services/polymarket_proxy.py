"""Proxy service for Polymarket Gamma & CLOB APIs with Redis caching."""

from __future__ import annotations

import json
from datetime import datetime, timezone

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


async def get_prices_history(
    token_id: str,
    interval: str = "1m",
    fidelity: int = 60,
) -> list[dict]:
    """Fetch price history from CLOB API for a given token.

    The CLOB /prices-history endpoint returns OHLC-style data.
    """
    cache_key = f"clob:price_history:{token_id}:{interval}:{fidelity}"
    cached = await cache_get(cache_key)
    if cached:
        return json.loads(cached)

    url = f"{settings.clob_api_url}/prices-history"
    params = {"market": token_id, "interval": interval, "fidelity": fidelity}
    resp = await _get_client().get(url, params=params)
    resp.raise_for_status()
    data = resp.json()
    history = data.get("history", data) if isinstance(data, dict) else data
    if not isinstance(history, list):
        history = []
    await cache_set(cache_key, json.dumps(history), settings.cache_ttl_orderbook)
    return history


# ── Data API (real on-chain trades) ──────────────────────────────────────────

async def get_data_trades(
    market_id: str,
    limit: int = 50,
    offset: int = 0,
) -> list[dict]:
    """Fetch real trades from Polymarket Data API.

    ``market_id`` can be a numeric Gamma market ID or a condition_id hex.
    """
    cache_key = f"data:trades:{market_id}:{limit}:{offset}"
    cached = await cache_get(cache_key)
    if cached:
        return json.loads(cached)

    url = f"{settings.data_api_url}/trades"
    params: dict = {"market": market_id, "limit": limit, "offset": offset}
    resp = await _get_client().get(url, params=params)
    resp.raise_for_status()
    data = resp.json()
    if not isinstance(data, list):
        data = []
    await cache_set(cache_key, json.dumps(data), settings.cache_ttl_data_trades)
    return data


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
    """Discover BTC up/down markets around the current time, grouped by duration.

    Computes slug timestamps to query Gamma API precisely, avoiding the problem
    of current events being buried in large generic queries.  Uses cache (20s TTL)
    to stay well under the 10 req/s rate limit.
    """
    cache_key = "btc:discovery"
    cached = await cache_get(cache_key)
    if cached:
        return json.loads(cached)

    now_ts = int(datetime.now(timezone.utc).timestamp())

    # Duration configs: (slug_prefix, interval_seconds, slots_before, slots_after)
    durations = [
        ("btc-updown-5m", 300, 4, 6),     # 4 past + 6 upcoming = 10
        ("btc-updown-15m", 900, 2, 4),     # 2 past + 4 upcoming = 6
        ("btc-updown-30m", 1800, 1, 3),    # 1 past + 3 upcoming = 4
    ]

    groups: dict[str, list[dict]] = {}
    url = f"{settings.gamma_api_url}/events"
    now_utc = datetime.now(timezone.utc)

    for prefix, interval, before, after in durations:
        key = f"{interval // 60}m"
        window_start = now_ts - (now_ts % interval)
        events: list[dict] = []

        for offset in range(-before, after + 1):
            slug = f"{prefix}-{window_start + offset * interval}"
            resp = await _get_client().get(url, params={"limit": 1, "slug": slug})
            if resp.status_code != 200:
                continue
            data = resp.json()
            if not data:
                continue
            e = _normalize_event(data[0])
            # Compute real-time status from eventStartTime + endDate
            end_str = e.get("endDate", "")
            m0 = e["markets"][0] if e.get("markets") else {}
            start_str = m0.get("eventStartTime", e.get("startDate", ""))
            if end_str:
                end_dt = datetime.fromisoformat(end_str.replace("Z", "+00:00"))
                start_dt = (
                    datetime.fromisoformat(start_str.replace("Z", "+00:00"))
                    if start_str
                    else end_dt
                )
                if end_dt <= now_utc:
                    e["_status"] = "ended"
                elif start_dt <= now_utc:
                    e["_status"] = "live"
                else:
                    e["_status"] = "upcoming"
            else:
                e["_status"] = "unknown"
            events.append(e)

        groups[key] = events

    await cache_set(cache_key, json.dumps(groups), 20)
    return groups
