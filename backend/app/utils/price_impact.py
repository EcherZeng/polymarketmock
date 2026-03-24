"""Price impact and slippage calculation utilities."""

from __future__ import annotations

from decimal import Decimal


def calculate_vwap_from_levels(
    levels: list[dict],
    amount: float,
) -> tuple[float, float, float]:
    """Walk through orderbook levels to fill `amount` shares.

    Args:
        levels: list of {"price": str, "size": str} sorted best-first
        amount: number of shares to fill

    Returns:
        (filled_amount, avg_price, total_cost)
    """
    remaining = Decimal(str(amount))
    total_cost = Decimal("0")
    filled = Decimal("0")

    for level in levels:
        price = Decimal(level["price"])
        size = Decimal(level["size"])
        if size <= 0 or price <= 0:
            continue

        fill_qty = min(remaining, size)
        cost = fill_qty * price
        total_cost += cost
        filled += fill_qty
        remaining -= fill_qty

        if remaining <= 0:
            break

    if filled == 0:
        return 0.0, 0.0, 0.0

    avg_price = float(total_cost / filled)
    return float(filled), avg_price, float(total_cost)


def calculate_slippage(mid_price: float, avg_price: float, side: str) -> float:
    """Calculate slippage percentage relative to mid price."""
    if mid_price == 0:
        return 0.0
    if side == "BUY":
        return ((avg_price - mid_price) / mid_price) * 100
    else:
        return ((mid_price - avg_price) / mid_price) * 100
