"""BTC trend computation for live trading — two-window sita/momentum filter.

Mirrors the Strategy (backtest) service logic: computes BTC momentum over
two time windows using Binance kline data to determine if a session is
tradeable and with what intensity.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

import httpx

logger = logging.getLogger(__name__)

BINANCE_KLINE_URL = "https://api.binance.com/api/v3/klines"

_shared_client: httpx.AsyncClient | None = None


def _get_client() -> httpx.AsyncClient:
    global _shared_client
    if _shared_client is None or _shared_client.is_closed:
        _shared_client = httpx.AsyncClient(
            timeout=10.0,
            limits=httpx.Limits(max_connections=10, max_keepalive_connections=5),
        )
    return _shared_client


async def close_client() -> None:
    global _shared_client
    if _shared_client is not None and not _shared_client.is_closed:
        await _shared_client.aclose()
        _shared_client = None


def _iso_to_ms(ts: str) -> int:
    dt = datetime.fromisoformat(ts)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return int(dt.timestamp() * 1000)


async def fetch_btc_klines(
    start_ts: str,
    end_ts: str,
    interval: str = "1m",
    limit: int = 60,
) -> list[dict]:
    """Fetch BTC/USDT klines from Binance for the given ISO time range."""
    start_ms = _iso_to_ms(start_ts)
    end_ms = _iso_to_ms(end_ts)

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
        })
    return klines


def compute_btc_trend(
    klines: list[dict],
    start_ts: str,
    window_1_min: int,
    window_2_min: int,
    min_momentum: float,
) -> dict:
    """Compute BTC trend filter — two-window sita mechanism.

    P0  = open price at session start
    Pw1 = open price at (start + window_1_min)
    Pw2 = open price at (start + window_2_min)

    a1 = (Pw1 - P0) / P0       — momentum over first window
    a2 = (Pw2 - Pw1) / Pw1     — momentum over second window

    Trend passes when:
        abs(a1 + a2) > min_momentum AND a1 * a2 > 0
        (same direction in both windows with sufficient magnitude)

    Returns dict: a1, a2, passed, amplitude, direction, error
    """
    if not klines:
        return _empty_result("no_klines")

    start_ms = _iso_to_ms(start_ts)
    target_w1_ms = start_ms + window_1_min * 60 * 1000
    target_w2_ms = start_ms + window_2_min * 60 * 1000

    def _closest_open(target_ms: int) -> float | None:
        best: dict | None = None
        best_dist = float("inf")
        for k in klines:
            dist = abs(k["open_time"] - target_ms)
            if dist < best_dist:
                best_dist = dist
                best = k
        return best["open"] if best else None

    p0 = _closest_open(start_ms)
    p_w1 = _closest_open(target_w1_ms)
    p_w2 = _closest_open(target_w2_ms)

    if p0 is None or p_w1 is None or p_w2 is None:
        return _empty_result("missing_prices")

    if p0 == 0 or p_w1 == 0:
        return _empty_result("zero_price")

    a1 = (p_w1 - p0) / p0
    a2 = (p_w2 - p_w1) / p_w1
    amplitude = abs(a1 + a2)
    passed = amplitude > min_momentum and a1 * a2 > 0

    # Determine direction: positive total momentum = UP, negative = DOWN
    direction = "UP" if (a1 + a2) > 0 else "DOWN"

    return {
        "a1": round(a1, 8),
        "a2": round(a2, 8),
        "passed": passed,
        "amplitude": round(amplitude, 8),
        "direction": direction,
        "p0": p0,
        "p_w1": p_w1,
        "p_w2": p_w2,
        "error": None,
    }


def _empty_result(error: str) -> dict:
    return {
        "a1": 0.0,
        "a2": 0.0,
        "passed": False,
        "amplitude": 0.0,
        "direction": "UNKNOWN",
        "p0": 0.0,
        "p_w1": 0.0,
        "p_w2": 0.0,
        "error": error,
    }


async def compute_session_btc_trend(
    session_start_iso: str,
    session_end_iso: str,
    window_1_min: int = 5,
    window_2_min: int = 10,
    min_momentum: float = 0.001,
) -> dict:
    """Convenience: fetch klines and compute trend for a session.

    Called when the session's window_2 time has elapsed, meaning we have
    enough BTC price data to compute both windows.
    """
    try:
        klines = await fetch_btc_klines(session_start_iso, session_end_iso)
        if not klines:
            return _empty_result("fetch_empty")
        return compute_btc_trend(klines, session_start_iso, window_1_min, window_2_min, min_momentum)
    except Exception as e:
        logger.warning("BTC trend computation failed: %s", e)
        return _empty_result(f"fetch_error: {e}")
