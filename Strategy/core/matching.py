"""VWAP matching engine — independent implementation (no backend imports)."""

from __future__ import annotations

from decimal import Decimal

from core.types import FillInfo, Signal


def calculate_vwap_from_levels(
    levels: list[tuple[float, float]],
    amount: float,
    max_cost: float | None = None,
) -> tuple[float, float, float]:
    """Walk through orderbook levels to fill `amount` shares.

    Args:
        levels: list of (price, size) sorted best-first
        amount: number of shares to fill
        max_cost: optional hard cap on total spend (USDC). Fills stop when
                  cumulative cost would exceed this limit.

    Returns:
        (filled_amount, avg_price, total_cost)
    """
    remaining = Decimal(str(amount))
    total_cost = Decimal("0")
    filled = Decimal("0")
    budget = Decimal(str(max_cost)) if max_cost is not None else None

    for price_f, size_f in levels:
        price = Decimal(str(price_f))
        size = Decimal(str(size_f))
        if size <= 0 or price <= 0:
            continue

        fill_qty = min(remaining, size)
        cost = fill_qty * price

        # Budget guard: only take as much as the remaining budget allows
        if budget is not None:
            remaining_budget = budget - total_cost
            if remaining_budget <= 0:
                break
            if cost > remaining_budget:
                fill_qty = remaining_budget / price
                cost = fill_qty * price

        total_cost += cost
        filled += fill_qty
        remaining -= fill_qty

        if remaining <= 0:
            break

    if filled == 0:
        return 0.0, 0.0, 0.0

    avg_price = float(total_cost / filled)
    return float(filled), round(avg_price, 6), float(total_cost)


def calculate_slippage(mid_price: float, avg_price: float, side: str) -> float:
    """Calculate slippage percentage relative to mid price."""
    if mid_price == 0:
        return 0.0
    if side == "BUY":
        return round(((avg_price - mid_price) / mid_price) * 100, 4)
    else:
        return round(((mid_price - avg_price) / mid_price) * 100, 4)


def execute_signal(
    signal: Signal,
    token_snapshot_bid_levels: list[tuple[float, float]],
    token_snapshot_ask_levels: list[tuple[float, float]],
    mid_price: float,
    balance: float,
    positions: dict[str, float],
    timestamp: str,
) -> FillInfo | None:
    """Execute a single signal against the current orderbook state.

    Returns FillInfo on success, None if signal cannot be filled.
    """
    if signal.amount <= 0:
        return None

    current_pos = positions.get(signal.token_id, 0.0)

    if signal.side == "BUY":
        levels = token_snapshot_ask_levels
    elif signal.side == "SELL":
        levels = token_snapshot_bid_levels
        if current_pos <= 0:
            return None
    else:
        return None

    if not levels:
        return None

    request_amount = signal.amount
    if signal.side == "SELL":
        request_amount = min(request_amount, current_pos)

    # For BUY, pass max_cost so the VWAP walk stops at budget
    buy_max_cost = signal.max_cost if signal.side == "BUY" else None
    filled, avg_price, total_cost = calculate_vwap_from_levels(levels, request_amount, max_cost=buy_max_cost)
    if filled <= 0:
        return None

    # Check balance for buys
    if signal.side == "BUY":
        max_affordable = balance / avg_price if avg_price > 0 else 0
        if filled > max_affordable:
            filled = max_affordable
            total_cost = filled * avg_price
        if filled <= 0:
            return None

    slippage = calculate_slippage(mid_price, avg_price, signal.side)

    # Update balance and positions
    if signal.side == "BUY":
        balance -= total_cost
        positions[signal.token_id] = current_pos + filled
    else:
        balance += total_cost
        positions[signal.token_id] = current_pos - filled

    return FillInfo(
        timestamp=timestamp,
        token_id=signal.token_id,
        side=signal.side,
        requested_amount=signal.amount,
        filled_amount=round(filled, 6),
        avg_price=round(avg_price, 6),
        total_cost=round(total_cost, 6),
        slippage_pct=round(slippage, 4),
        balance_after=round(balance, 6),
        position_after=round(positions.get(signal.token_id, 0.0), 6),
    )
