"""Background data collector — periodically snapshots real market data to Parquet.

Supports adaptive polling: LIVE event tokens are polled at higher frequency
and trade activity is inferred from orderbook diffs.
"""

from __future__ import annotations

import asyncio
import json
import logging

from app.config import settings
from app.services.matching_engine import check_and_fill_limit_orders
from app.services.polymarket_proxy import get_data_trades, get_midpoint, get_orderbook_raw
from app.services.trade_feed import detect_trades
from app.storage.duckdb_store import write_live_trade, write_orderbook_snapshot, write_price_snapshot, write_trade_snapshot
from app.storage import redis_store

logger = logging.getLogger(__name__)

# In-memory prev-snapshots for fast diff (avoids extra Redis round-trip per tick)
_prev_books: dict[str, dict] = {}


async def _collect_and_detect(token_id: str, market_id: str) -> None:
    """Fetch orderbook, detect trades via diff, and write Parquet snapshot."""
    try:
        book = await get_orderbook_raw(token_id)
    except Exception as e:
        logger.warning("Failed to fetch orderbook for %s: %s", token_id, e)
        return

    # Detect trades from diff
    prev = _prev_books.get(token_id)
    if prev:
        inferred = detect_trades(token_id, prev, book)
        for t in inferred:
            try:
                await redis_store.add_realtime_trade(
                    token_id, t["ts"], json.dumps(t),
                )
                await redis_store.trim_realtime_trades(
                    token_id, settings.realtime_trades_max,
                )
            except Exception as e:
                logger.warning("Failed to store realtime trade: %s", e)
            # Also persist to Parquet for archival
            try:
                write_trade_snapshot(
                    market_id=market_id or token_id,
                    token_id=token_id,
                    side=t.get("side", "UNKNOWN"),
                    price=t.get("price", 0),
                    size=t.get("size", 0),
                    timestamp=t.get("timestamp"),
                )
            except Exception as e:
                logger.warning("Failed to write trade snapshot: %s", e)

    _prev_books[token_id] = book

    # Write orderbook snapshot to Parquet
    bids = book.get("bids", [])
    asks = book.get("asks", [])
    try:
        write_orderbook_snapshot(
            market_id=market_id or token_id,
            token_id=token_id,
            bid_prices=json.dumps([b["price"] for b in bids]),
            bid_sizes=json.dumps([b["size"] for b in bids]),
            ask_prices=json.dumps([a["price"] for a in asks]),
            ask_sizes=json.dumps([a["size"] for a in asks]),
        )
    except Exception as e:
        logger.warning("Failed to write orderbook snapshot for %s: %s", token_id, e)

    # Write price snapshot from same orderbook data (1s resolution)
    try:
        best_bid = float(bids[0]["price"]) if bids else 0
        best_ask = float(asks[0]["price"]) if asks else 0
        mid_price = (best_bid + best_ask) / 2 if (best_bid and best_ask) else best_bid or best_ask
        spread = best_ask - best_bid if (best_bid and best_ask) else 0
        write_price_snapshot(
            market_id=market_id or token_id,
            token_id=token_id,
            mid_price=mid_price,
            best_bid=best_bid,
            best_ask=best_ask,
            spread=spread,
        )
    except Exception as e:
        logger.warning("Failed to write price snapshot for %s: %s", token_id, e)


async def _collect_orderbooks() -> None:
    watched = await redis_store.get_watched_markets()
    for token_id, market_id in watched.items():
        await _collect_and_detect(token_id, market_id)


async def _collect_prices() -> None:
    watched = await redis_store.get_watched_markets()
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
            logger.warning("Failed to collect price for %s: %s", token_id, e)


async def _live_tick() -> None:
    """High-frequency tick for LIVE tokens — orderbook diff + trade detection."""
    watched = await redis_store.get_watched_markets()
    for token_id, market_id in watched.items():
        await _collect_and_detect(token_id, market_id)


async def _collect_live_trades() -> None:
    """Fetch real trades from Polymarket Data API for watched markets."""
    watched = await redis_store.get_watched_markets()
    if not watched:
        return

    # Group by market_id to avoid duplicate API calls
    market_ids: dict[str, str] = {}  # market_id -> any token_id
    for token_id, market_id in watched.items():
        if market_id and market_id not in market_ids:
            market_ids[market_id] = token_id

    for market_id, _ in market_ids.items():
        try:
            trades = await get_data_trades(market_id=market_id, limit=30)
        except Exception as e:
            logger.warning("Failed to fetch live trades for %s: %s", market_id, e)
            continue

        for t in trades:
            tx_hash = t.get("transactionHash", "")
            if not tx_hash:
                continue
            # Deduplicate by transactionHash
            try:
                already_seen = await redis_store.is_live_trade_seen(market_id, tx_hash)
                if already_seen:
                    continue
                await redis_store.mark_live_trade_seen(market_id, tx_hash)
            except Exception:
                continue

            ts = float(t.get("timestamp", 0))
            # Store in Redis for real-time queries
            try:
                await redis_store.add_live_trade(market_id, ts, json.dumps(t))
                await redis_store.trim_live_trades(market_id, settings.live_trades_max)
            except Exception as e:
                logger.warning("Failed to store live trade: %s", e)

            # Persist to Parquet
            try:
                from datetime import datetime, timezone
                ts_iso = datetime.fromtimestamp(ts, tz=timezone.utc).isoformat() if ts else None
                write_live_trade(
                    market_id=market_id,
                    token_id=t.get("asset", ""),
                    condition_id=t.get("conditionId", ""),
                    side=t.get("side", ""),
                    price=float(t.get("price", 0)),
                    size=float(t.get("size", 0)),
                    outcome=t.get("outcome", ""),
                    pseudonym=t.get("pseudonym", ""),
                    name=t.get("name", ""),
                    transaction_hash=tx_hash,
                    timestamp=ts_iso,
                )
            except Exception as e:
                logger.warning("Failed to write live trade to Parquet: %s", e)


async def _maybe_archive_ended() -> None:
    """Check if any watched tokens belong to ended events and trigger archival."""
    try:
        from app.services.event_lifecycle import auto_archive_if_ended
        await auto_archive_if_ended()
    except Exception as e:
        logger.warning("Auto-archive check failed: %s", e)


async def _collector_loop() -> None:
    ob_counter = 0
    price_counter = 0
    live_counter = 0
    archive_counter = 0
    live_trades_counter = 0

    while True:
        await asyncio.sleep(1)
        ob_counter += 1
        price_counter += 1
        live_counter += 1
        archive_counter += 1
        live_trades_counter += 1

        # Check limit orders every 5s
        if ob_counter % settings.limit_order_check_interval == 0:
            try:
                await check_and_fill_limit_orders()
            except Exception as e:
                logger.warning("Limit order check failed: %s", e)

        # High-frequency trade detection for watched tokens
        if live_counter >= settings.collector_live_interval:
            live_counter = 0
            try:
                await _live_tick()
            except Exception as e:
                logger.warning("Live tick failed: %s", e)

        # Orderbook snapshots (standard interval, also writes Parquet)
        if ob_counter >= settings.collector_orderbook_interval:
            ob_counter = 0
            # Parquet writes are already done in _live_tick via _collect_and_detect
            # This is a catch-all for the standard path
            pass

        # Price snapshots
        if price_counter >= settings.collector_price_interval:
            price_counter = 0
            try:
                await _collect_prices()
            except Exception as e:
                logger.warning("Price collection failed: %s", e)

        # Collect real trades from Data API
        if live_trades_counter >= settings.collector_live_trades_interval:
            live_trades_counter = 0
            try:
                await _collect_live_trades()
            except Exception as e:
                logger.warning("Live trades collection failed: %s", e)

        # Check for ended events every 30s
        if archive_counter >= 30:
            archive_counter = 0
            try:
                await _maybe_archive_ended()
            except Exception as e:
                logger.warning("Archive check failed: %s", e)


async def start_collector() -> asyncio.Task:
    return asyncio.create_task(_collector_loop())


async def stop_collector(task: asyncio.Task) -> None:
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass
