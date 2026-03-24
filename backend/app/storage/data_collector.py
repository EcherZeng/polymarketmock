"""Background data collector — periodically snapshots real market data to Parquet."""

from __future__ import annotations

import asyncio
import json
import logging

from app.config import settings
from app.services.matching_engine import check_and_fill_limit_orders
from app.services.polymarket_proxy import get_midpoint, get_orderbook_raw
from app.storage.duckdb_store import write_orderbook_snapshot, write_price_snapshot
from app.storage.redis_store import get_watched_markets

logger = logging.getLogger(__name__)


async def _collect_orderbooks() -> None:
    watched = await get_watched_markets()
    for token_id, market_id in watched.items():
        try:
            book = await get_orderbook_raw(token_id)
            bids = book.get("bids", [])
            asks = book.get("asks", [])
            write_orderbook_snapshot(
                market_id=market_id or token_id,
                token_id=token_id,
                bid_prices=json.dumps([b["price"] for b in bids]),
                bid_sizes=json.dumps([b["size"] for b in bids]),
                ask_prices=json.dumps([a["price"] for a in asks]),
                ask_sizes=json.dumps([a["size"] for a in asks]),
            )
        except Exception as e:
            logger.warning(f"Failed to collect orderbook for {token_id}: {e}")


async def _collect_prices() -> None:
    watched = await get_watched_markets()
    for token_id, market_id in watched.items():
        try:
            book = await get_orderbook_raw(token_id)
            mid = await get_midpoint(token_id)
            bids = book.get("bids", [])
            asks = book.get("asks", [])
            best_bid = float(bids[0]["price"]) if bids else 0
            best_ask = float(asks[0]["price"]) if asks else 0
            spread = best_ask - best_bid

            write_price_snapshot(
                market_id=market_id or token_id,
                token_id=token_id,
                mid_price=mid,
                best_bid=best_bid,
                best_ask=best_ask,
                spread=spread,
            )
        except Exception as e:
            logger.warning(f"Failed to collect price for {token_id}: {e}")


async def _collector_loop() -> None:
    ob_counter = 0
    price_counter = 0

    while True:
        await asyncio.sleep(1)
        ob_counter += 1
        price_counter += 1

        # Check limit orders every 5s
        if ob_counter % settings.limit_order_check_interval == 0:
            try:
                await check_and_fill_limit_orders()
            except Exception as e:
                logger.warning(f"Limit order check failed: {e}")

        # Orderbook snapshots
        if ob_counter >= settings.collector_orderbook_interval:
            ob_counter = 0
            try:
                await _collect_orderbooks()
            except Exception as e:
                logger.warning(f"Orderbook collection failed: {e}")

        # Price snapshots
        if price_counter >= settings.collector_price_interval:
            price_counter = 0
            try:
                await _collect_prices()
            except Exception as e:
                logger.warning(f"Price collection failed: {e}")


async def start_collector() -> asyncio.Task:
    return asyncio.create_task(_collector_loop())


async def stop_collector(task: asyncio.Task) -> None:
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass
