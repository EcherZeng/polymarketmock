"""Polymarket WebSocket manager — connects to Market Channel, processes events,
updates Redis caches, persists to Parquet, and broadcasts to frontend clients."""

from __future__ import annotations

import asyncio
import json
import logging
import time
from datetime import datetime, timezone

import websockets
from starlette.websockets import WebSocket

from app.config import settings
from app.storage import redis_store
from app.storage.duckdb_store import (
    write_live_trade,
    write_orderbook_snapshot,
    write_price_snapshot,
)

logger = logging.getLogger(__name__)

# ── Singleton ────────────────────────────────────────────────────────────────

_manager: PolymarketWSManager | None = None


def get_ws_manager() -> PolymarketWSManager:
    assert _manager is not None, "WS manager not initialised"
    return _manager


# ── Manager ──────────────────────────────────────────────────────────────────


class PolymarketWSManager:
    """Manages upstream Polymarket WS + downstream frontend WS fanout."""

    def __init__(self) -> None:
        # Upstream connection state
        self._ws: websockets.WebSocketClientProtocol | None = None  # type: ignore[name-defined]
        self._task: asyncio.Task | None = None
        self._ping_task: asyncio.Task | None = None
        self._stop = asyncio.Event()

        # Subscribed asset_ids on the upstream connection
        self._subscribed: set[str] = set()

        # Frontend client connections: asset_id → set of FastAPI WebSocket
        self._clients: dict[str, set[WebSocket]] = {}
        self._client_lock = asyncio.Lock()

        # Connection status flag (used by data_collector for fallback)
        self.connected: bool = False

        # Parquet write throttling (last write timestamps)
        self._last_ob_write: dict[str, float] = {}
        self._last_price_write: dict[str, float] = {}

    # ── Lifecycle ─────────────────────────────────────────────

    async def start(self) -> None:
        self._stop.clear()
        self._task = asyncio.create_task(self._run_loop())

    async def stop(self) -> None:
        self._stop.set()
        if self._ping_task:
            self._ping_task.cancel()
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        if self._ws:
            await self._ws.close()
            self._ws = None
        self.connected = False

    # ── Upstream connect / reconnect ──────────────────────────

    async def _run_loop(self) -> None:
        backoff = 1
        while not self._stop.is_set():
            try:
                await self._connect_and_listen()
            except asyncio.CancelledError:
                return
            except Exception as e:
                logger.warning("WS upstream error: %s — reconnecting in %ss", e, backoff)
            self.connected = False
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, settings.ws_reconnect_max)

    async def _connect_and_listen(self) -> None:
        logger.info("Connecting to Polymarket WS: %s", settings.ws_url)
        async with websockets.connect(
            settings.ws_url,
            ping_interval=None,   # We handle app-level PING ourselves
            ping_timeout=None,
            close_timeout=10,
        ) as ws:
            self._ws = ws
            self.connected = True
            logger.info("Polymarket WS connected")

            # Re-subscribe to any previously tracked assets
            if self._subscribed:
                await self._send_subscribe(list(self._subscribed))

            # Start ping task
            self._ping_task = asyncio.create_task(self._ping_loop(ws))

            try:
                async for raw in ws:
                    if self._stop.is_set():
                        return
                    await self._on_message(raw)
            finally:
                if self._ping_task:
                    self._ping_task.cancel()
                self._ws = None
                self.connected = False

    async def _ping_loop(self, ws: websockets.WebSocketClientProtocol) -> None:  # type: ignore[name-defined]
        try:
            while True:
                await asyncio.sleep(settings.ws_ping_interval)
                await ws.send("PING")
        except asyncio.CancelledError:
            pass
        except Exception:
            pass

    # ── Subscribe / unsubscribe upstream ──────────────────────

    async def subscribe(self, asset_ids: list[str]) -> None:
        new = [a for a in asset_ids if a not in self._subscribed]
        if not new:
            return
        self._subscribed.update(new)
        if self._ws and self.connected:
            await self._send_subscribe(new)

    async def unsubscribe(self, asset_ids: list[str]) -> None:
        removing = [a for a in asset_ids if a in self._subscribed]
        if not removing:
            return
        self._subscribed -= set(removing)
        if self._ws and self.connected:
            await self._send_unsubscribe(removing)

    async def _send_subscribe(self, asset_ids: list[str]) -> None:
        if not self._ws:
            return
        msg = {
            "assets_ids": asset_ids,
            "type": "market",
            "initial_dump": True,
            "custom_feature_enabled": True,
        }
        await self._ws.send(json.dumps(msg))
        logger.info("WS subscribed to %d assets", len(asset_ids))

    async def _send_unsubscribe(self, asset_ids: list[str]) -> None:
        if not self._ws:
            return
        msg = {
            "operation": "unsubscribe",
            "assets_ids": asset_ids,
        }
        await self._ws.send(json.dumps(msg))
        logger.info("WS unsubscribed from %d assets", len(asset_ids))

    # ── Message dispatch ──────────────────────────────────────

    async def _on_message(self, raw: str | bytes) -> None:
        text = raw if isinstance(raw, str) else raw.decode()
        if text == "PONG":
            return

        try:
            parsed = json.loads(text)
        except json.JSONDecodeError:
            return

        # Polymarket may send a single object or a batch array
        items: list[dict] = parsed if isinstance(parsed, list) else [parsed]

        for data in items:
            if not isinstance(data, dict):
                continue
            await self._dispatch(data, text)

    async def _dispatch(self, data: dict, raw_text: str) -> None:
        event_type = data.get("event_type")
        if not event_type:
            return

        try:
            if event_type == "book":
                await self._handle_book(data)
            elif event_type == "price_change":
                await self._handle_price_change(data)
            elif event_type == "last_trade_price":
                await self._handle_last_trade_price(data)
            elif event_type == "best_bid_ask":
                await self._handle_best_bid_ask(data)
            elif event_type == "tick_size_change":
                await self._handle_tick_size_change(data)
            elif event_type == "market_resolved":
                await self._handle_market_resolved(data)
        except Exception as e:
            logger.warning("Error handling WS event %s: %s", event_type, e)

        # Broadcast individual event to frontend clients
        broadcast_text = json.dumps(data)
        asset_id = data.get("asset_id")
        if asset_id:
            await self._broadcast(asset_id, broadcast_text)
        # price_change may contain multiple asset_ids in price_changes
        if event_type == "price_change":
            seen: set[str] = set()
            for pc in data.get("price_changes", []):
                aid = pc.get("asset_id", "")
                if aid and aid not in seen and aid != asset_id:
                    seen.add(aid)
                    await self._broadcast(aid, broadcast_text)

    # ── Event handlers ────────────────────────────────────────

    async def _handle_book(self, data: dict) -> None:
        """Full orderbook snapshot — update Redis cache."""
        asset_id = data.get("asset_id", "")
        bids = data.get("bids", [])
        asks = data.get("asks", [])

        # Update Redis orderbook cache (same key as CLOB proxy)
        cache_data = json.dumps({
            "market": data.get("market", ""),
            "asset_id": asset_id,
            "timestamp": data.get("timestamp", ""),
            "hash": data.get("hash", ""),
            "bids": bids,
            "asks": asks,
        })
        await redis_store.cache_set(
            f"clob:book:{asset_id}", cache_data, settings.cache_ttl_orderbook,
        )

        # Throttled Parquet write (max once per 15s per token)
        now = time.monotonic()
        last = self._last_ob_write.get(asset_id, 0)
        if now - last >= settings.collector_orderbook_interval:
            self._last_ob_write[asset_id] = now
            market_id = await self._resolve_market_id(asset_id)
            try:
                write_orderbook_snapshot(
                    market_id=market_id,
                    token_id=asset_id,
                    bid_prices=[float(b["price"]) for b in bids],
                    bid_sizes=[float(b["size"]) for b in bids],
                    ask_prices=[float(a["price"]) for a in asks],
                    ask_sizes=[float(a["size"]) for a in asks],
                )
            except Exception as e:
                logger.warning("WS book parquet write failed: %s", e)

    async def _handle_price_change(self, data: dict) -> None:
        """Incremental orderbook update — update Redis cache with new levels."""
        for pc in data.get("price_changes", []):
            asset_id = pc.get("asset_id", "")
            if not asset_id:
                continue

            # Read current cached book, apply delta
            cached = await redis_store.cache_get(f"clob:book:{asset_id}")
            if not cached:
                continue
            try:
                book = json.loads(cached)
            except json.JSONDecodeError:
                continue

            side = pc.get("side", "")
            price = pc.get("price", "0")
            size = pc.get("size", "0")

            key = "bids" if side == "BUY" else "asks"
            levels: list[dict] = book.get(key, [])

            # Update or remove the level
            if float(size) == 0:
                levels = [lv for lv in levels if lv.get("price") != price]
            else:
                found = False
                for lv in levels:
                    if lv.get("price") == price:
                        lv["size"] = size
                        found = True
                        break
                if not found:
                    levels.append({"price": price, "size": size})

            # Re-sort: bids descending, asks ascending
            reverse = key == "bids"
            levels.sort(key=lambda lv: float(lv.get("price", 0)), reverse=reverse)
            book[key] = levels
            book["timestamp"] = data.get("timestamp", book.get("timestamp", ""))

            await redis_store.cache_set(
                f"clob:book:{asset_id}", json.dumps(book), settings.cache_ttl_orderbook,
            )

    async def _handle_last_trade_price(self, data: dict) -> None:
        """Real trade event — store in Redis + Parquet."""
        asset_id = data.get("asset_id", "")
        ts_ms = data.get("timestamp", "0")
        ts = float(ts_ms) / 1000 if ts_ms else time.time()

        trade = {
            "timestamp": datetime.fromtimestamp(ts, tz=timezone.utc).isoformat(),
            "ts": ts,
            "token_id": asset_id,
            "side": data.get("side", "UNKNOWN"),
            "price": round(float(data.get("price", "0")), 6),
            "size": round(float(data.get("size", "0")), 2),
            "inferred": False,
            "transaction_hash": data.get("transaction_hash", ""),
        }

        try:
            await redis_store.add_realtime_trade(asset_id, ts, json.dumps(trade))
            await redis_store.trim_realtime_trades(asset_id, settings.realtime_trades_max)
        except Exception as e:
            logger.warning("WS trade redis write failed: %s", e)

        # Persist to Parquet
        market_id = await self._resolve_market_id(asset_id)
        try:
            write_live_trade(
                market_id=market_id,
                token_id=asset_id,
                side=data.get("side", ""),
                price=float(data.get("price", "0")),
                size=float(data.get("size", "0")),
                transaction_hash=data.get("transaction_hash", ""),
                timestamp=trade["timestamp"],
            )
        except Exception as e:
            logger.warning("WS trade parquet write failed: %s", e)

    async def _handle_best_bid_ask(self, data: dict) -> None:
        """Best bid/ask event — update Redis midpoint cache."""
        asset_id = data.get("asset_id", "")
        best_bid = float(data.get("best_bid", "0"))
        best_ask = float(data.get("best_ask", "0"))
        mid = (best_bid + best_ask) / 2 if (best_bid and best_ask) else best_bid or best_ask

        await redis_store.cache_set(
            f"clob:mid:{asset_id}", str(mid), settings.cache_ttl_midpoint,
        )

        # Throttled Parquet write (max once per 60s per token)
        now = time.monotonic()
        last = self._last_price_write.get(asset_id, 0)
        if now - last >= settings.collector_price_interval:
            self._last_price_write[asset_id] = now
            market_id = await self._resolve_market_id(asset_id)
            spread = float(data.get("spread", "0"))
            try:
                write_price_snapshot(
                    market_id=market_id,
                    token_id=asset_id,
                    mid_price=mid,
                    best_bid=best_bid,
                    best_ask=best_ask,
                    spread=spread,
                )
            except Exception as e:
                logger.warning("WS BBA parquet write failed: %s", e)

    async def _handle_tick_size_change(self, data: dict) -> None:
        """Tick size change — broadcast only (no persistent storage needed)."""
        pass

    async def _handle_market_resolved(self, data: dict) -> None:
        """Market resolved — broadcast only (lifecycle handled by eventStatus polling)."""
        pass

    # ── Frontend client management ────────────────────────────

    async def register_client(self, ws: WebSocket, asset_ids: list[str]) -> None:
        async with self._client_lock:
            for aid in asset_ids:
                if aid not in self._clients:
                    self._clients[aid] = set()
                self._clients[aid].add(ws)
        # Ensure upstream is subscribed
        await self.subscribe(asset_ids)

    async def unregister_client(self, ws: WebSocket) -> None:
        async with self._client_lock:
            for aid in list(self._clients):
                self._clients[aid].discard(ws)
                if not self._clients[aid]:
                    del self._clients[aid]

    async def update_client_subscription(
        self, ws: WebSocket, subscribe_ids: list[str], unsubscribe_ids: list[str],
    ) -> None:
        async with self._client_lock:
            for aid in unsubscribe_ids:
                if aid in self._clients:
                    self._clients[aid].discard(ws)
                    if not self._clients[aid]:
                        del self._clients[aid]
            for aid in subscribe_ids:
                if aid not in self._clients:
                    self._clients[aid] = set()
                self._clients[aid].add(ws)
        if subscribe_ids:
            await self.subscribe(subscribe_ids)

    async def _broadcast(self, asset_id: str, message: str) -> None:
        """Send message to all frontend clients subscribed to asset_id."""
        async with self._client_lock:
            clients = list(self._clients.get(asset_id, set()))
        stale: list[WebSocket] = []
        for ws in clients:
            try:
                await ws.send_text(message)
            except Exception:
                stale.append(ws)
        if stale:
            async with self._client_lock:
                for ws in stale:
                    for aid in list(self._clients):
                        self._clients[aid].discard(ws)
                        if not self._clients[aid]:
                            del self._clients[aid]

    # ── Helpers ───────────────────────────────────────────────

    async def _resolve_market_id(self, token_id: str) -> str:
        """Get market_id for a token_id from watched:markets hash."""
        watched = await redis_store.get_watched_markets()
        return watched.get(token_id, token_id)


# ── Module-level start/stop ──────────────────────────────────────────────────


async def start_ws_manager() -> PolymarketWSManager:
    global _manager
    _manager = PolymarketWSManager()
    await _manager.start()

    # Auto-subscribe to all currently watched tokens
    try:
        watched = await redis_store.get_watched_markets()
        if watched:
            await _manager.subscribe(list(watched.keys()))
    except Exception as e:
        logger.warning("Failed to auto-subscribe watched tokens: %s", e)

    return _manager


async def stop_ws_manager() -> None:
    global _manager
    if _manager:
        await _manager.stop()
        _manager = None
