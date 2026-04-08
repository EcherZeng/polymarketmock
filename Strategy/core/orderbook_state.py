"""Orderbook state management — init, delta application, snapshot derivation."""

from __future__ import annotations

from core.anchor_pricing import compute_anchor_price
from core.types import TokenSnapshot


# ── Delta-driven orderbook reconstruction ────────────────────────────────────


def init_working_ob(snapshot: dict) -> dict:
    """Initialise working orderbook from a full snapshot.

    Returns {"bids": {price_str: size_float}, "asks": {...}}
    """
    bids: dict[str, float] = {}
    asks: dict[str, float] = {}

    bid_prices = snapshot.get("bid_prices", [])
    bid_sizes = snapshot.get("bid_sizes", [])
    ask_prices = snapshot.get("ask_prices", [])
    ask_sizes = snapshot.get("ask_sizes", [])

    for p, s in zip(bid_prices, bid_sizes):
        price_str = str(round(float(p), 6))
        bids[price_str] = float(s)
    for p, s in zip(ask_prices, ask_sizes):
        price_str = str(round(float(p), 6))
        asks[price_str] = float(s)
    return {"bids": bids, "asks": asks}


def apply_delta(working_ob: dict, delta: dict) -> None:
    """Apply a single orderbook delta in-place."""
    side = delta.get("side", "")
    key = "bids" if side == "BUY" else "asks"
    levels: dict[str, float] = working_ob.setdefault(key, {})
    price = str(round(float(delta.get("price", 0)), 6))
    size = float(delta.get("size", 0))
    if size == 0:
        levels.pop(price, None)
    else:
        levels[price] = size


def derive_snapshot_from_ob(token_id: str, working_ob: dict) -> TokenSnapshot:
    """Derive TokenSnapshot from working orderbook."""
    bids = working_ob.get("bids", {})
    asks = working_ob.get("asks", {})
    best_bid = max((float(p) for p in bids if bids[p] > 0), default=0.0)
    best_ask = min((float(p) for p in asks if asks[p] > 0), default=0.0)
    mid = (best_bid + best_ask) / 2 if (best_bid and best_ask) else best_bid or best_ask
    spread = (best_ask - best_bid) if (best_bid and best_ask) else 0.0

    bid_levels = sorted(
        [(float(p), s) for p, s in bids.items() if s > 0],
        key=lambda x: x[0],
        reverse=True,
    )
    ask_levels = sorted(
        [(float(p), s) for p, s in asks.items() if s > 0],
        key=lambda x: x[0],
    )

    # Compute tiered anchor price
    anchor_price, anchor_source = compute_anchor_price(
        best_bid, best_ask, mid, spread, bid_levels, ask_levels,
    )

    return TokenSnapshot(
        token_id=token_id,
        mid_price=round(mid, 6),
        best_bid=round(best_bid, 6),
        best_ask=round(best_ask, 6),
        spread=round(spread, 6),
        anchor_price=round(anchor_price, 6),
        anchor_source=anchor_source,
        bid_levels=bid_levels,
        ask_levels=ask_levels,
    )
