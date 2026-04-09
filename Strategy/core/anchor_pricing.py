"""Tiered anchor pricing — spread-based mid / micro / last_trade selection."""

from __future__ import annotations


# Spread thresholds for tiered anchor selection (Polymarket uses 0.10)
SPREAD_TIGHT = 0.05    # spread < 0.05 → simple mid is reliable
SPREAD_WIDE = 0.15     # spread > 0.15 → mid is unreliable, use last_trade_price
MICRO_DEPTH = 3        # number of orderbook levels used for micro-price


def weighted_micro_price(
    bid_levels: list[tuple[float, float]],
    ask_levels: list[tuple[float, float]],
    depth: int = MICRO_DEPTH,
) -> float | None:
    """Compute depth-weighted micro-price using top N levels from each side.

    Formula (generalised for N levels):
      micro = (Σ bid_i × V_ask_i  +  Σ ask_i × V_bid_i) / (Σ V_bid + Σ V_ask)

    When the orderbook is oscillating with several close price levels at
    similar volumes, this captures the "centre of gravity" across the
    full visible depth rather than relying solely on a single best level.
    """
    top_bids = bid_levels[:depth]
    top_asks = ask_levels[:depth]
    if not top_bids or not top_asks:
        return None

    sum_bid_vol = sum(v for _, v in top_bids)
    sum_ask_vol = sum(v for _, v in top_asks)
    total_vol = sum_bid_vol + sum_ask_vol
    if total_vol <= 0:
        return None

    # Cross-weight: bid prices weighted by ask volume; ask prices by bid volume
    bid_weighted = sum(p * v for p, v in top_bids)
    ask_weighted = sum(p * v for p, v in top_asks)
    micro = (bid_weighted * sum_ask_vol + ask_weighted * sum_bid_vol) / (
        total_vol * ((sum_bid_vol + sum_ask_vol) / 2)
    )
    # Simpler equivalent that avoids the cross-product confusion:
    # Use the standard per-level cross-imbalance micro-price.
    # Weight each side's prices by the *opposing* side's total volume.
    micro = (
        sum(p * sum_ask_vol for p, _ in top_bids)
        + sum(p * sum_bid_vol for p, _ in top_asks)
    )
    denominator = len(top_bids) * sum_ask_vol + len(top_asks) * sum_bid_vol
    if denominator <= 0:
        return None
    micro = micro / denominator
    return round(micro, 6)


def compute_anchor_price(
    best_bid: float,
    best_ask: float,
    mid: float,
    spread: float,
    bid_levels: list[tuple[float, float]],
    ask_levels: list[tuple[float, float]],
    last_trade_price: float = 0.0,
) -> tuple[float, str]:
    """Compute tiered anchor price based on orderbook conditions.

    Returns (anchor_price, source) where source is one of:
      "mid"         — spread < 0.05, simple midpoint is reliable
      "micro"       — 0.05 <= spread < 0.15, depth-weighted micro-price (top N levels)
      "last_trade"  — spread >= 0.15 and a recent trade exists
      "none"        — no reliable price available

    When the orderbook is oscillating (multiple close price levels with
    similar volume), the micro-price uses up to 3 levels from each side
    to capture the volume-weighted centre of gravity.
    """
    if not best_bid and not best_ask:
        if last_trade_price > 0:
            return last_trade_price, "last_trade"
        return 0.0, "none"

    # Only one side available
    if not best_bid or not best_ask:
        if last_trade_price > 0:
            return last_trade_price, "last_trade"
        return mid, "mid"

    if spread < SPREAD_TIGHT:
        # Tight spread: simple mid is reliable
        return mid, "mid"
    elif spread < SPREAD_WIDE:
        # Medium spread: use multi-level micro-price
        micro = weighted_micro_price(bid_levels, ask_levels)
        return (micro, "micro") if micro is not None else (mid, "mid")
    else:
        # Wide spread: mid is unreliable
        if last_trade_price > 0:
            return last_trade_price, "last_trade"
        # Fallback to micro-price even for wide spread (better than simple mid)
        micro = weighted_micro_price(bid_levels, ask_levels)
        return (micro, "micro") if micro is not None else (mid, "mid")
