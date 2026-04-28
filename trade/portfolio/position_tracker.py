"""Position tracker — maintains real-time balance, positions, and PnL."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone

from models.types import LiveFill

logger = logging.getLogger(__name__)


@dataclass
class CostBasis:
    """Track cost basis for a position."""
    shares: float = 0.0
    total_cost: float = 0.0     # cumulative USDC spent

    @property
    def avg_price(self) -> float:
        return self.total_cost / self.shares if self.shares > 0 else 0.0


class PositionTracker:
    """Tracks USDC balance, token positions, and unrealised PnL."""

    def __init__(self, initial_balance: float = 0.0) -> None:
        self._balance: float = initial_balance
        self._initial_balance: float = initial_balance
        self._positions: dict[str, float] = {}              # token_id → shares
        self._cost_basis: dict[str, CostBasis] = {}         # token_id → CostBasis
        self._session_trades: list[LiveFill] = []
        self._realised_pnl: float = 0.0

    def reset_session(self) -> None:
        """Reset session-level tracking (keep balance & positions from prior sessions)."""
        self._session_trades.clear()
        self._realised_pnl = 0.0

    def set_balance(self, balance: float) -> None:
        """Override balance (e.g. from API sync)."""
        self._balance = balance
        if self._initial_balance <= 0:
            self._initial_balance = balance

    # ── Fill processing ───────────────────────────────────────

    def apply_fill(self, fill: LiveFill) -> None:
        """Update balance and positions based on a trade fill."""
        self._session_trades.append(fill)

        if fill.side == "BUY":
            self._balance -= fill.total_cost
            self._positions[fill.token_id] = self._positions.get(fill.token_id, 0) + fill.filled_shares
            basis = self._cost_basis.setdefault(fill.token_id, CostBasis())
            basis.shares += fill.filled_shares
            basis.total_cost += fill.total_cost
            logger.info(
                "BUY fill: %s %.2f shares @ %.4f (cost $%.2f) | balance: $%.2f",
                fill.token_id[:12], fill.filled_shares, fill.avg_price, fill.total_cost, self._balance,
            )

        elif fill.side == "SELL":
            self._balance += fill.total_cost
            old_qty = self._positions.get(fill.token_id, 0)
            new_qty = old_qty - fill.filled_shares
            self._positions[fill.token_id] = max(0, new_qty)

            # Calculate realised PnL
            basis = self._cost_basis.get(fill.token_id)
            if basis and basis.shares > 0:
                cost_per_share = basis.avg_price
                pnl = (fill.avg_price - cost_per_share) * fill.filled_shares
                self._realised_pnl += pnl
                # Reduce basis
                basis.shares -= fill.filled_shares
                basis.total_cost -= cost_per_share * fill.filled_shares
                if basis.shares <= 0:
                    basis.shares = 0
                    basis.total_cost = 0

            if new_qty <= 0:
                self._positions.pop(fill.token_id, None)

            logger.info(
                "SELL fill: %s %.2f shares @ %.4f (recv $%.2f) | balance: $%.2f",
                fill.token_id[:12], fill.filled_shares, fill.avg_price, fill.total_cost, self._balance,
            )

    # ── Settlement ────────────────────────────────────────────

    def apply_settlement(self, token_id: str, winning: bool) -> float:
        """Apply settlement: winning shares = $1 each, losing = $0.

        Returns the settlement PnL for this token.
        """
        shares = self._positions.get(token_id, 0)
        if shares <= 0:
            return 0.0

        basis = self._cost_basis.get(token_id)
        cost = basis.total_cost if basis else 0.0

        if winning:
            proceeds = shares * 1.0  # $1 per winning share
            pnl = proceeds - cost
            self._balance += proceeds
        else:
            pnl = -cost  # total loss

        self._realised_pnl += pnl
        self._positions.pop(token_id, None)
        self._cost_basis.pop(token_id, None)

        logger.info(
            "Settlement: %s %s — %.2f shares, PnL: $%.4f",
            token_id[:12], "WIN" if winning else "LOSS", shares, pnl,
        )
        return pnl

    # ── Queries ───────────────────────────────────────────────

    @property
    def balance(self) -> float:
        return self._balance

    @property
    def initial_balance(self) -> float:
        return self._initial_balance

    @property
    def positions(self) -> dict[str, float]:
        return dict(self._positions)

    @property
    def realised_pnl(self) -> float:
        return self._realised_pnl

    @property
    def session_trades(self) -> list[LiveFill]:
        return list(self._session_trades)

    def has_position(self, token_id: str | None = None) -> bool:
        if token_id:
            return self._positions.get(token_id, 0) > 0
        return any(v > 0 for v in self._positions.values())

    def get_cost_basis(self, token_id: str) -> float:
        basis = self._cost_basis.get(token_id)
        return basis.avg_price if basis else 0.0

    def equity(self, current_prices: dict[str, float] | None = None) -> float:
        """Total equity = balance + mark-to-market positions."""
        eq = self._balance
        if current_prices:
            for token_id, shares in self._positions.items():
                price = current_prices.get(token_id, 0)
                eq += shares * price
        return eq

    def unrealised_pnl(self, current_prices: dict[str, float]) -> float:
        """Unrealised PnL = position value - cost basis."""
        total = 0.0
        for token_id, shares in self._positions.items():
            price = current_prices.get(token_id, 0)
            basis = self._cost_basis.get(token_id)
            cost = basis.total_cost if basis else 0.0
            total += shares * price - cost
        return total

    def to_dict(self, current_prices: dict[str, float] | None = None) -> dict:
        """Snapshot for API responses."""
        prices = current_prices or {}
        return {
            "balance": round(self._balance, 6),
            "initial_balance": round(self._initial_balance, 6),
            "positions": {tid: round(s, 4) for tid, s in self._positions.items()},
            "equity": round(self.equity(prices), 6),
            "realised_pnl": round(self._realised_pnl, 6),
            "unrealised_pnl": round(self.unrealised_pnl(prices), 6),
            "session_trade_count": len(self._session_trades),
        }
