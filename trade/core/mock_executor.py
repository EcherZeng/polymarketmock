"""Mock order executor — simulates Polymarket order execution locally.

All parameters and return shapes match the real executor exactly,
but no actual API calls are made. Used for development and testing.
"""

from __future__ import annotations

import asyncio
import logging
import random
import string
import time
from datetime import datetime, timezone

from config import settings
from core.base_executor import BaseExecutor
from core.types import LiveFill, LiveSignal

logger = logging.getLogger(__name__)


def _gen_order_id() -> str:
    """Generate a fake order ID that looks like a Polymarket order ID."""
    return "mock-" + "".join(random.choices(string.hexdigits[:16], k=24))


class MockExecutor(BaseExecutor):
    """Mock executor — returns successful fills without calling Polymarket.

    Simulates:
    - Order acceptance (always succeeds)
    - Full fill (no partial fills)
    - Realistic timing (configurable latency)
    - Balance tracking

    Parameters mirror real Polymarket API responses.
    """

    def __init__(self, latency_ms: int = 200) -> None:
        self._ready = False
        self._latency_ms = latency_ms
        self._mock_balance: float = 100.0  # Default mock balance

    async def start(self) -> None:
        self._ready = True
        self._mock_balance = settings.initial_balance if settings.initial_balance > 0 else 100.0
        logger.info("MockExecutor ready (latency=%dms, balance=$%.2f)", self._latency_ms, self._mock_balance)

    async def stop(self) -> None:
        self._ready = False
        logger.info("MockExecutor stopped")

    @property
    def is_ready(self) -> bool:
        return self._ready

    # ── Order placement ───────────────────────────────────────

    async def place_order(self, signal: LiveSignal, session_slug: str = "") -> LiveFill | None:
        """Simulate order placement with full fill."""
        if not self.is_ready:
            logger.error("MockExecutor not ready")
            return None

        price = signal.limit_price
        if price is None or price <= 0:
            logger.error("Mock: %s signal has no valid limit_price", signal.side)
            return None

        # Simulate network latency
        await asyncio.sleep(self._latency_ms / 1000.0)

        if signal.side == "BUY":
            return self._mock_buy(signal, session_slug, price)
        else:
            return self._mock_sell(signal, session_slug, price)

    def _mock_buy(self, signal: LiveSignal, session_slug: str, price: float) -> LiveFill | None:
        # Check mock balance
        if signal.amount_usdc > self._mock_balance:
            logger.warning("Mock: insufficient balance $%.2f for buy $%.2f", self._mock_balance, signal.amount_usdc)
            return None

        shares = signal.amount_usdc / price
        total_cost = signal.amount_usdc
        self._mock_balance -= total_cost

        order_id = _gen_order_id()
        logger.info(
            "Mock BUY filled: %s %.2f shares @ %.4f ($%.2f) | balance: $%.2f",
            signal.token_id[:12], shares, price, total_cost, self._mock_balance,
        )

        return LiveFill(
            order_id=order_id,
            token_id=signal.token_id,
            side="BUY",
            filled_shares=round(shares, 4),
            avg_price=price,
            total_cost=round(total_cost, 6),
            timestamp=datetime.now(timezone.utc).isoformat(),
            session_slug=session_slug,
            fees=0.0,
        )

    def _mock_sell(self, signal: LiveSignal, session_slug: str, price: float) -> LiveFill | None:
        # signal.amount_usdc is shares for SELL
        shares = signal.amount_usdc
        proceeds = shares * price
        self._mock_balance += proceeds

        order_id = _gen_order_id()
        logger.info(
            "Mock SELL filled: %s %.2f shares @ %.4f ($%.2f) | balance: $%.2f",
            signal.token_id[:12], shares, price, proceeds, self._mock_balance,
        )

        return LiveFill(
            order_id=order_id,
            token_id=signal.token_id,
            side="SELL",
            filled_shares=round(shares, 4),
            avg_price=price,
            total_cost=round(proceeds, 6),
            timestamp=datetime.now(timezone.utc).isoformat(),
            session_slug=session_slug,
            fees=0.0,
        )

    # ── Cancel ────────────────────────────────────────────────

    async def cancel_all(self) -> None:
        logger.info("Mock: cancel_all (no-op)")

    async def cancel_order(self, order_id: str) -> None:
        logger.info("Mock: cancel %s (no-op)", order_id)

    # ── Balance / Allowance ───────────────────────────────────

    async def get_balance(self) -> float | None:
        """Return mock balance."""
        return self._mock_balance

    async def check_allowance(self) -> bool:
        """Always OK in mock mode."""
        return True
