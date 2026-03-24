"""Position manager — queries positions + calculates PnL."""

from __future__ import annotations

from app.models.trading import AccountOverview, OrderSide, Position
from app.services.polymarket_proxy import get_midpoint
from app.storage import redis_store


async def get_account_overview() -> AccountOverview:
    balance = await redis_store.get_balance()
    initial = await redis_store.get_initial_balance()
    realized = await redis_store.get_realized_pnl()
    positions = await get_all_positions_with_pnl()

    total_value = sum(p.market_value for p in positions)
    total_unrealized = sum(p.unrealized_pnl for p in positions)

    return AccountOverview(
        balance=round(balance, 6),
        initial_balance=round(initial, 6),
        total_positions_value=round(total_value, 6),
        total_unrealized_pnl=round(total_unrealized, 6),
        total_realized_pnl=round(realized, 6),
        total_pnl=round(total_unrealized + realized, 6),
        positions=positions,
    )


async def get_all_positions_with_pnl() -> list[Position]:
    raw = await redis_store.get_all_positions()
    positions: list[Position] = []

    for token_id, data in raw.items():
        shares = float(data.get("shares", 0))
        avg_cost = float(data.get("avg_cost", 0))
        side = data.get("side", "BUY")

        try:
            current_price = await get_midpoint(token_id)
        except Exception:
            current_price = 0.0

        market_value = shares * current_price
        unrealized = (current_price - avg_cost) * shares

        positions.append(Position(
            token_id=token_id,
            side=OrderSide(side),
            shares=round(shares, 6),
            avg_cost=round(avg_cost, 6),
            current_price=round(current_price, 6),
            unrealized_pnl=round(unrealized, 6),
            market_value=round(market_value, 6),
        ))

    return positions


async def get_position_detail(token_id: str) -> Position | None:
    data = await redis_store.get_position(token_id)
    if not data:
        return None

    shares = float(data.get("shares", 0))
    avg_cost = float(data.get("avg_cost", 0))
    side = data.get("side", "BUY")

    try:
        current_price = await get_midpoint(token_id)
    except Exception:
        current_price = 0.0

    market_value = shares * current_price
    unrealized = (current_price - avg_cost) * shares

    return Position(
        token_id=token_id,
        side=OrderSide(side),
        shares=round(shares, 6),
        avg_cost=round(avg_cost, 6),
        current_price=round(current_price, 6),
        unrealized_pnl=round(unrealized, 6),
        market_value=round(market_value, 6),
    )
