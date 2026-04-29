"""Order executor — places real orders on Polymarket via py-clob-client SDK."""

from __future__ import annotations

import asyncio
import logging
import time
from datetime import datetime, timezone

from py_clob_client.client import ClobClient
from py_clob_client.clob_types import ApiCreds, OrderArgs, OrderType

from config import settings
from execution.base_executor import BaseExecutor
from models.types import LiveFill, LiveSignal

logger = logging.getLogger(__name__)


class OrderExecutor(BaseExecutor):
    """Real order executor — places orders on Polymarket."""

    def __init__(self) -> None:
        self._client: ClobClient | None = None
        self._ready = False

    async def start(self) -> None:
        """Initialize the CLOB client with credentials."""
        if not settings.poly_private_key:
            logger.error("POLY_PRIVATE_KEY not set — order executor disabled")
            return

        loop = asyncio.get_running_loop()
        try:
            self._client = await loop.run_in_executor(None, self._init_client)
            self._ready = True
            logger.info("OrderExecutor ready (signature_type=%d)", settings.poly_signature_type)
        except Exception as e:
            logger.error("OrderExecutor init failed: %s", e)

    def _init_client(self) -> ClobClient:
        client = ClobClient(
            settings.clob_api_url,
            key=settings.poly_private_key,
            chain_id=settings.chain_id,
            signature_type=settings.poly_signature_type,
            funder=settings.poly_funder_address or None,
        )

        # Set API credentials
        if settings.poly_api_key:
            creds = ApiCreds(
                api_key=settings.poly_api_key,
                api_secret=settings.poly_api_secret,
                api_passphrase=settings.poly_api_passphrase,
            )
            client.set_api_creds(creds)
        else:
            # Derive from private key
            creds = client.create_or_derive_api_creds()
            client.set_api_creds(creds)

        # Verify connectivity
        client.get_ok()
        return client

    async def stop(self) -> None:
        self._ready = False
        self._client = None
        logger.info("OrderExecutor stopped")

    @property
    def is_ready(self) -> bool:
        return self._ready and self._client is not None

    # ── Order placement ───────────────────────────────────────

    async def place_order(self, signal: LiveSignal, session_slug: str = "") -> LiveFill | None:
        """Place a limit order based on signal. Returns LiveFill or None on failure."""
        if not self.is_ready:
            logger.error("OrderExecutor not ready — cannot place order")
            return None

        loop = asyncio.get_running_loop()

        try:
            fill = await loop.run_in_executor(
                None, self._place_order_sync, signal, session_slug,
            )
            return fill
        except Exception as e:
            logger.error("Order placement failed: %s", e)
            return None

    def _place_order_sync(self, signal: LiveSignal, session_slug: str) -> LiveFill | None:
        """Synchronous order placement (runs in thread pool)."""
        assert self._client is not None

        if signal.side == "BUY":
            return self._place_buy(signal, session_slug)
        else:
            return self._place_sell(signal, session_slug)

    def _place_buy(self, signal: LiveSignal, session_slug: str) -> LiveFill | None:
        assert self._client is not None
        price = signal.limit_price
        if price is None or price <= 0:
            logger.error("BUY signal has no valid limit_price")
            return None

        # Calculate shares from USDC amount
        shares = signal.amount_usdc / price

        order_args = OrderArgs(
            price=price,
            size=round(shares, 2),
            side="BUY",
            token_id=signal.token_id,
        )

        signed = self._client.create_order(order_args)
        resp = self._client.post_order(signed, order_type=OrderType.GTC)
        logger.info("BUY order posted: %s", resp)

        order_id = resp.get("orderID", resp.get("order_id", ""))
        if not order_id:
            logger.error("No order_id in response: %s", resp)
            return None

        # Wait for fill
        return self._wait_for_fill(order_id, signal, session_slug)

    def _place_sell(self, signal: LiveSignal, session_slug: str) -> LiveFill | None:
        assert self._client is not None
        price = signal.limit_price
        if price is None or price <= 0:
            logger.error("SELL signal has no valid limit_price")
            return None

        # Floor to 0.01 precision to avoid leaving dust positions
        import math
        shares = math.floor(signal.amount_usdc * 100) / 100

        order_args = OrderArgs(
            price=price,
            size=shares,
            side="SELL",
            token_id=signal.token_id,
        )

        signed = self._client.create_order(order_args)
        resp = self._client.post_order(signed, order_type=OrderType.GTC)
        logger.info("SELL order posted: %s", resp)

        order_id = resp.get("orderID", resp.get("order_id", ""))
        if not order_id:
            logger.error("No order_id in response: %s", resp)
            return None

        return self._wait_for_fill(order_id, signal, session_slug)

    def _wait_for_fill(
        self, order_id: str, signal: LiveSignal, session_slug: str,
    ) -> LiveFill | None:
        """Poll for order fill status. Cancel if timeout."""
        assert self._client is not None
        deadline = time.monotonic() + settings.order_timeout_s

        while time.monotonic() < deadline:
            try:
                order = self._client.get_order(order_id)
                status = order.get("status", "")

                if status == "MATCHED":
                    # Fully filled
                    return self._order_to_fill(order, signal, session_slug)
                elif status in ("CANCELLED", "REJECTED"):
                    logger.warning("Order %s %s", order_id, status)
                    return None

                # Partial fills — check size_matched
                size_matched = float(order.get("size_matched", 0))
                original_size = float(order.get("original_size", order.get("size", 0)))
                if size_matched > 0 and size_matched >= original_size:
                    return self._order_to_fill(order, signal, session_slug)

            except Exception as e:
                logger.warning("Order poll error: %s", e)

            time.sleep(2)

        # Timeout — cancel the order
        logger.warning("Order %s timed out — cancelling", order_id)
        try:
            self._client.cancel(order_id)
        except Exception as e:
            logger.error("Cancel failed for %s: %s", order_id, e)

        # Check if partially filled
        try:
            order = self._client.get_order(order_id)
            size_matched = float(order.get("size_matched", 0))
            if size_matched > 0:
                return self._order_to_fill(order, signal, session_slug)
        except Exception:
            pass

        return None

    def _order_to_fill(self, order: dict, signal: LiveSignal, session_slug: str) -> LiveFill:
        """Convert order response to LiveFill."""
        size_matched = float(order.get("size_matched", 0))
        avg_price = float(order.get("price", signal.limit_price or 0))
        total_cost = size_matched * avg_price

        return LiveFill(
            order_id=order.get("id", order.get("orderID", "")),
            token_id=signal.token_id,
            side=signal.side,
            filled_shares=size_matched,
            avg_price=avg_price,
            total_cost=total_cost,
            timestamp=datetime.now(timezone.utc).isoformat(),
            session_slug=session_slug,
        )

    # ── P0-2: Balance sync ────────────────────────────────────

    async def get_balance(self) -> float | None:
        """Fetch real USDC balance from Polymarket API."""
        if not self.is_ready:
            return None
        loop = asyncio.get_running_loop()
        try:
            bal = await loop.run_in_executor(None, self._get_balance_sync)
            return bal
        except Exception as e:
            logger.error("get_balance failed: %s", e)
            return None

    def _get_balance_sync(self) -> float:
        assert self._client is not None
        # py-clob-client exposes get_balance_allowance for collateral token
        resp = self._client.get_balance_allowance()
        # resp typically: {"balance": "123.45", "allowance": "..."}
        return float(resp.get("balance", 0))

    # ── P0-5: Allowance check ────────────────────────────────

    async def check_allowance(self) -> bool:
        """Verify conditional token approval for SELL operations."""
        if not self.is_ready:
            return False
        loop = asyncio.get_running_loop()
        try:
            return await loop.run_in_executor(None, self._check_allowance_sync)
        except Exception as e:
            logger.error("check_allowance failed: %s", e)
            return False

    def _check_allowance_sync(self) -> bool:
        assert self._client is not None
        resp = self._client.get_balance_allowance()
        allowance = float(resp.get("allowance", 0))
        if allowance <= 0:
            logger.warning(
                "Conditional token allowance is 0 — SELL operations may fail. "
                "Run: python -m scripts.set_allowances"
            )
            return False
        return True
