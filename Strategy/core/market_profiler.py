"""Market profiler — extracts compact market characteristics from ArchiveData.

Used by AI optimizer to understand data source properties without exposing
raw time-series data (which would be too large for LLM context).
"""

from __future__ import annotations

import math
from collections import defaultdict

from core.types import ArchiveData


def profile_market(slug: str, data: ArchiveData) -> dict:
    """Build a compact market profile from archive data.

    Returns a dict with:
      slug, duration_seconds, token_count, tokens (per-token stats),
      total_trades, data_quality.
    """
    # ── Collect timestamps ───────────────────────────────────────────────
    all_ts: list[str] = []
    for row in (*data.prices, *data.orderbooks, *data.ob_deltas, *data.live_trades):
        ts = row.get("timestamp", "")
        if ts:
            all_ts.append(ts)

    all_ts.sort()
    duration_seconds = 0
    if len(all_ts) >= 2:
        from datetime import datetime
        try:
            dt_start = datetime.fromisoformat(all_ts[0])
            dt_end = datetime.fromisoformat(all_ts[-1])
            duration_seconds = (dt_end - dt_start).total_seconds()
        except (ValueError, TypeError):
            pass

    # ── Per-token price stats ────────────────────────────────────────────
    token_prices: dict[str, list[float]] = defaultdict(list)

    for row in data.prices:
        tid = row.get("token_id", "")
        mid = row.get("mid_price")
        if tid and mid is not None:
            token_prices[tid].append(float(mid))

    # Also collect from orderbook snapshots
    for row in data.orderbooks:
        tid = row.get("token_id", "")
        bid_prices = row.get("bid_prices", [])
        ask_prices = row.get("ask_prices", [])
        if tid and len(bid_prices) > 0 and len(ask_prices) > 0:
            best_bid = max(float(p) for p in bid_prices) if len(bid_prices) > 0 else 0
            best_ask = min(float(p) for p in ask_prices) if len(ask_prices) > 0 else 0
            if best_bid > 0 and best_ask > 0:
                token_prices[tid].append((best_bid + best_ask) / 2)

    # ── Per-token spread stats ───────────────────────────────────────
    token_spreads: dict[str, list[float]] = defaultdict(list)

    for row in data.orderbooks:
        tid = row.get("token_id", "")
        bid_prices = row.get("bid_prices", [])
        ask_prices = row.get("ask_prices", [])
        if tid and len(bid_prices) > 0 and len(ask_prices) > 0:
            best_bid = max(float(p) for p in bid_prices) if len(bid_prices) > 0 else 0
            best_ask = min(float(p) for p in ask_prices) if len(ask_prices) > 0 else 0
            if best_bid > 0 and best_ask > 0:
                token_spreads[tid].append(best_ask - best_bid)

    # ── Build per-token profile ──────────────────────────────────────────
    tokens: dict[str, dict] = {}

    for tid in sorted(token_prices.keys()):
        prices = token_prices[tid]
        spreads = token_spreads.get(tid, [])

        price_min = min(prices) if prices else 0.0
        price_max = max(prices) if prices else 0.0
        price_mean = sum(prices) / len(prices) if prices else 0.0

        # Volatility: standard deviation of prices
        volatility = 0.0
        if len(prices) > 1:
            mean = price_mean
            variance = sum((p - mean) ** 2 for p in prices) / (len(prices) - 1)
            volatility = math.sqrt(variance)

        avg_spread = sum(spreads) / len(spreads) if spreads else 0.0

        tokens[tid] = {
            "price_min": round(price_min, 6),
            "price_max": round(price_max, 6),
            "price_mean": round(price_mean, 6),
            "volatility": round(volatility, 6),
            "avg_spread": round(avg_spread, 6),
            "data_points": len(prices),
        }

    # ── Data quality ─────────────────────────────────────────────────────
    return {
        "slug": slug,
        "duration_seconds": round(duration_seconds, 1),
        "token_count": len(tokens),
        "tokens": tokens,
        "total_live_trades": len(data.live_trades),
        "data_quality": {
            "prices_count": len(data.prices),
            "orderbooks_count": len(data.orderbooks),
            "ob_deltas_count": len(data.ob_deltas),
            "live_trades_count": len(data.live_trades),
        },
    }
