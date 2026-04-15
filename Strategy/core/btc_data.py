"""BTC kline data fetching from Binance — shared by results display and backtest engine."""

from __future__ import annotations

import logging
from datetime import datetime, timezone

import httpx

logger = logging.getLogger(__name__)

BINANCE_KLINE_URL = "https://api.binance.com/api/v3/klines"

# ── Module-level shared client and cache ─────────────────────────────────────

_shared_client: httpx.AsyncClient | None = None
_kline_cache: dict[tuple[int, int], list[dict]] = {}


def _get_client() -> httpx.AsyncClient:
    """Lazy-init a shared httpx client (connection pooling across requests)."""
    global _shared_client
    if _shared_client is None or _shared_client.is_closed:
        _shared_client = httpx.AsyncClient(
            timeout=15.0,
            limits=httpx.Limits(max_connections=20, max_keepalive_connections=10),
        )
    return _shared_client


def clear_kline_cache() -> None:
    """Clear the in-memory kline cache (call between batch runs if needed)."""
    _kline_cache.clear()


def _iso_to_ms(ts: str) -> int:
    """Convert ISO 8601 timestamp string to milliseconds since epoch.

    Treats naive (no tzinfo) strings as UTC to avoid system-timezone drift.
    """
    dt = datetime.fromisoformat(ts)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return int(dt.timestamp() * 1000)


def _transform_klines(raw: list) -> list[dict]:
    """Transform raw Binance kline arrays to structured dicts."""
    klines: list[dict] = []
    for k in raw:
        klines.append({
            "open_time": k[0],
            "open": float(k[1]),
            "high": float(k[2]),
            "low": float(k[3]),
            "close": float(k[4]),
            "volume": float(k[5]),
            "close_time": k[6],
            "quote_volume": float(k[7]),
            "trades": k[8],
        })
    return klines


async def fetch_btc_klines(
    start_ts: str,
    end_ts: str,
    interval: str = "1m",
    limit: int = 1000,
) -> list[dict]:
    """Fetch BTC/USDT klines from Binance for the given ISO time range.

    Returns a list of kline dicts with keys:
        open_time, open, high, low, close, volume, close_time, quote_volume, trades
    """
    start_ms = _iso_to_ms(start_ts)
    end_ms = _iso_to_ms(end_ts)

    # Cache hit — many slugs share overlapping time windows
    cache_key = (start_ms, end_ms)
    if cache_key in _kline_cache:
        return _kline_cache[cache_key]

    try:
        client = _get_client()
        resp = await client.get(
            BINANCE_KLINE_URL,
            params={
                "symbol": "BTCUSDT",
                "interval": interval,
                "startTime": start_ms,
                "endTime": end_ms,
                "limit": limit,
            },
        )
        resp.raise_for_status()
        raw = resp.json()
    except httpx.HTTPError as e:
        logger.warning("Binance kline request failed: %s", e)
        raise

    result = _transform_klines(raw)
    _kline_cache[cache_key] = result
    return result


def compute_btc_trend(
    klines: list[dict],
    start_ts: str,
    window_1_min: int,
    window_2_min: int,
    min_momentum: float,
) -> dict:
    """Compute BTC trend filter from kline data.

    Uses close prices at three time points:
      P0  = close at session start
      Pw1 = close at start + window_1_min
      Pw2 = close at start + window_1_min + window_2_min

    Computes:
      a1 = (Pw1 - P0) / P0
      a2 = (Pw2 - Pw1) / Pw1

    Trend passes when: abs(a1 + a2) > min_momentum AND a1 * a2 > 0
    (same direction in both windows with sufficient magnitude)

    Returns dict with keys: a1, a2, passed, p0, p_w1, p_w2, error
    """
    if not klines:
        return {"a1": 0.0, "a2": 0.0, "passed": True, "p0": 0.0, "p_w1": 0.0, "p_w2": 0.0, "error": "no_klines"}

    start_ms = _iso_to_ms(start_ts)
    target_w1_ms = start_ms + window_1_min * 60 * 1000
    target_w2_ms = start_ms + (window_1_min + window_2_min) * 60 * 1000

    def _closest_close(target_ms: int) -> float | None:
        """Find kline whose open_time is closest to target_ms and return its close price."""
        best: dict | None = None
        best_dist = float("inf")
        for k in klines:
            dist = abs(k["open_time"] - target_ms)
            if dist < best_dist:
                best_dist = dist
                best = k
        return best["close"] if best else None

    p0 = _closest_close(start_ms)
    p_w1 = _closest_close(target_w1_ms)
    p_w2 = _closest_close(target_w2_ms)

    if p0 is None or p_w1 is None or p_w2 is None:
        return {"a1": 0.0, "a2": 0.0, "passed": True, "p0": 0.0, "p_w1": 0.0, "p_w2": 0.0, "error": "missing_prices"}

    if p0 == 0 or p_w1 == 0:
        return {"a1": 0.0, "a2": 0.0, "passed": True, "p0": p0, "p_w1": p_w1, "p_w2": p_w2, "error": "zero_price"}

    a1 = (p_w1 - p0) / p0
    a2 = (p_w2 - p_w1) / p_w1

    passed = abs(a1 + a2) > min_momentum and a1 * a2 > 0

    return {
        "a1": round(a1, 8),
        "a2": round(a2, 8),
        "passed": passed,
        "p0": p0,
        "p_w1": p_w1,
        "p_w2": p_w2,
        "error": None,
    }
