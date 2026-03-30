"""Settlement service — resolves markets and settles positions."""

from __future__ import annotations

import logging

from app.storage import redis_store

logger = logging.getLogger(__name__)


async def settle_market(market_id: str, winning_outcome: str, token_map: dict[str, str]) -> dict:
    """Settle a market.

    Args:
        market_id: The market condition ID
        winning_outcome: e.g. "Yes" or "No"
        token_map: mapping of outcome name -> token_id (e.g. {"Yes": "abc", "No": "def"})

    Returns:
        Settlement summary
    """
    settled_positions: list[dict] = []
    total_payout = 0.0
    logger.info("Settling market %s — winning: %s", market_id, winning_outcome)

    all_positions = await redis_store.get_all_positions()

    for token_id, data in all_positions.items():
        # Check if this token belongs to this market
        if token_id not in token_map.values():
            continue

        shares = float(data.get("shares", 0))
        avg_cost = float(data.get("avg_cost", 0))

        # Find which outcome this token represents
        outcome_name = ""
        for name, tid in token_map.items():
            if tid == token_id:
                outcome_name = name
                break

        if outcome_name == winning_outcome:
            # Winner: each share pays out $1
            payout = shares * 1.0
            pnl = payout - (shares * avg_cost)
            await redis_store.adjust_balance(payout)
            await redis_store.adjust_realized_pnl(pnl)
            total_payout += payout
        else:
            # Loser: shares are worth $0
            pnl = -(shares * avg_cost)
            await redis_store.adjust_realized_pnl(pnl)

        settled_positions.append({
            "token_id": token_id,
            "outcome": outcome_name,
            "shares": shares,
            "avg_cost": avg_cost,
            "is_winner": outcome_name == winning_outcome,
            "pnl": round(pnl, 6),
        })

        await redis_store.delete_position(token_id)

    logger.info(
        "Settlement complete: market=%s, positions=%d, payout=%.4f",
        market_id, len(settled_positions), total_payout,
    )

    return {
        "market_id": market_id,
        "winning_outcome": winning_outcome,
        "total_payout": round(total_payout, 6),
        "settled_positions": settled_positions,
    }
