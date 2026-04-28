"""Settlement tracker — monitors market resolution and computes final PnL."""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone

import httpx

from config import settings
from core.types import SessionInfo

logger = logging.getLogger(__name__)

_client: httpx.AsyncClient | None = None


def _get_client() -> httpx.AsyncClient:
    global _client
    if _client is None or _client.is_closed:
        _client = httpx.AsyncClient(timeout=15.0)
    return _client


class SettlementTracker:
    """Polls Gamma API to detect market resolution for completed sessions."""

    async def check_resolution(self, session: SessionInfo) -> dict | None:
        """Check if a market has been resolved.

        Returns dict with resolution info or None if not yet resolved.
        Result: {"resolved": True, "winning_outcome": "Up"|"Down", "winning_token_id": "..."}
        """
        url = f"{settings.gamma_api_url}/events"
        try:
            resp = await _get_client().get(url, params={"limit": 1, "slug": session.slug})
            if resp.status_code != 200:
                return None
            data = resp.json()
            if not data:
                return None

            event = data[0]
            markets = event.get("markets", [])
            if not markets:
                return None

            m0 = markets[0]

            # Check resolution flags
            if not m0.get("resolved", False):
                return None

            # Determine winning outcome
            outcome_prices = m0.get("outcomePrices", [])
            if isinstance(outcome_prices, str):
                try:
                    outcome_prices = json.loads(outcome_prices)
                except (json.JSONDecodeError, ValueError):
                    outcome_prices = []

            outcomes = m0.get("outcomes", [])
            if isinstance(outcomes, str):
                try:
                    outcomes = json.loads(outcomes)
                except (json.JSONDecodeError, ValueError):
                    outcomes = []

            token_ids = m0.get("clobTokenIds", [])
            if isinstance(token_ids, str):
                try:
                    token_ids = json.loads(token_ids)
                except (json.JSONDecodeError, ValueError):
                    token_ids = []

            # Find winning outcome (price = "1" or "1.0")
            winning_idx = -1
            for i, price in enumerate(outcome_prices):
                try:
                    if float(price) >= 0.99:
                        winning_idx = i
                        break
                except (ValueError, TypeError):
                    continue

            if winning_idx < 0:
                return None

            winning_outcome = outcomes[winning_idx] if winning_idx < len(outcomes) else ""
            winning_token = token_ids[winning_idx] if winning_idx < len(token_ids) else ""

            return {
                "resolved": True,
                "winning_outcome": winning_outcome,
                "winning_token_id": winning_token,
                "winning_index": winning_idx,
            }

        except Exception as e:
            logger.warning("Settlement check failed for %s: %s", session.slug, e)
            return None

    async def wait_for_resolution(self, session: SessionInfo) -> dict | None:
        """Poll until market is resolved or timeout."""
        deadline = asyncio.get_event_loop().time() + settings.settlement_poll_max_s
        while asyncio.get_event_loop().time() < deadline:
            result = await self.check_resolution(session)
            if result:
                logger.info(
                    "Settlement resolved for %s: %s wins",
                    session.slug, result.get("winning_outcome"),
                )
                return result
            await asyncio.sleep(settings.settlement_poll_interval_s)

        logger.warning("Settlement timeout for %s after %ds", session.slug, settings.settlement_poll_max_s)
        return None

    async def close(self) -> None:
        global _client
        if _client and not _client.is_closed:
            await _client.aclose()
            _client = None
