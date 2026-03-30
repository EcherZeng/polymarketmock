"""Polymarket WebSocket manager — connects to Market Channel, processes events,
updates Redis caches, persists to Parquet, and broadcasts to frontend clients.

Upstream WS connection is established when either a frontend client subscribes
or auto_recorder starts headless recording via ``start_recording()``.  When all
subscriptions are removed the upstream connection is gracefully closed.

Recording sessions are tracked in ``backend/data/sessions.jsonl`` so that
downstream consumers can distinguish complete vs. incomplete data."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import time
import uuid
from datetime import datetime, timezone

import websockets
from starlette.websockets import WebSocket

from app.config import settings
from app.services.log_buffer import metrics
from app.storage import redis_store
from app.storage.duckdb_store import (
    write_live_trade,
    write_ob_delta,
    write_orderbook_snapshot,
    write_price_snapshot,
)

logger = logging.getLogger(__name__)


def _ws_ts_to_iso(ts_ms: str) -> str | None:
    """Convert Polymarket WS unix-millisecond timestamp to ISO 8601."""
    try:
        return datetime.fromtimestamp(
            float(ts_ms) / 1000, tz=timezone.utc,
        ).isoformat()
    except (ValueError, TypeError, OverflowError):
        return None

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

        # Lazy-connect signal: set when _subscribed is non-empty
        self._has_subscriptions = asyncio.Event()

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

        # Recording sessions: slug → session dict
        self._sessions: dict[str, dict] = {}
        self._sessions_file = os.path.join(settings.data_dir, "sessions.jsonl")

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
            # Lazy: wait until at least one frontend client subscribes
            try:
                await asyncio.wait_for(
                    self._has_subscriptions.wait(),
                    timeout=1.0,
                )
            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                return

            if not self._subscribed:
                # Spurious wake or all clients left before we got here
                self._has_subscriptions.clear()
                continue

            try:
                await self._connect_and_listen()
            except asyncio.CancelledError:
                return
            except Exception as e:
                # Only log + backoff if we still have subscribers
                if self._subscribed:
                    logger.warning("WS upstream error: %s — reconnecting in %ss", e, backoff)
                else:
                    logger.info("WS upstream closed (no subscribers)")
            self.connected = False

            if not self._subscribed:
                # No subscribers left — go back to waiting
                self._has_subscriptions.clear()
                backoff = 1
                continue

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
            metrics.set("ws.upstream_connected", True)
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
                metrics.set("ws.upstream_connected", False)

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
        self._has_subscriptions.set()  # wake _run_loop if sleeping
        if self._ws and self.connected:
            await self._send_subscribe(new)

    async def unsubscribe(self, asset_ids: list[str]) -> None:
        removing = [a for a in asset_ids if a in self._subscribed]
        if not removing:
            return
        self._subscribed -= set(removing)
        if self._ws and self.connected:
            await self._send_unsubscribe(removing)

        # If no more subscriptions, gracefully close the upstream connection
        if not self._subscribed:
            self._has_subscriptions.clear()
            await self._close_upstream()

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
        metrics.set("ws.subscribed_assets", len(self._subscribed))

    async def _send_unsubscribe(self, asset_ids: list[str]) -> None:
        if not self._ws:
            return
        msg = {
            "operation": "unsubscribe",
            "assets_ids": asset_ids,
        }
        await self._ws.send(json.dumps(msg))
        logger.info("WS unsubscribed from %d assets", len(asset_ids))
        metrics.set("ws.subscribed_assets", len(self._subscribed))

    async def _close_upstream(self) -> None:
        """Gracefully close the upstream WS connection (sends close frame)."""
        if self._ping_task:
            self._ping_task.cancel()
            self._ping_task = None
        if self._ws:
            try:
                await self._ws.close()
            except Exception:
                pass
            self._ws = None
        self.connected = False
        logger.info("WS upstream closed — no active subscribers")

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
            metrics.inc("ws.messages_received")
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
        ts_iso = _ws_ts_to_iso(data.get("timestamp", ""))

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

        # Throttled Parquet write (max once per 2s per token)
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
                    timestamp=ts_iso,
                )
            except Exception as e:
                logger.warning("WS book parquet write failed: %s", e)

    async def _handle_price_change(self, data: dict) -> None:
        """Incremental orderbook update — update Redis cache with new levels
        and persist each delta to Parquet for replay fidelity."""
        ts_iso = _ws_ts_to_iso(data.get("timestamp", ""))
        for pc in data.get("price_changes", []):
            asset_id = pc.get("asset_id", "")
            if not asset_id:
                continue

            side = pc.get("side", "")
            price = pc.get("price", "0")
            size = pc.get("size", "0")

            # Persist delta to Parquet (no throttling — every event)
            market_id = await self._resolve_market_id(asset_id)
            try:
                write_ob_delta(
                    market_id=market_id,
                    token_id=asset_id,
                    side=side,
                    price=float(price),
                    size=float(size),
                    timestamp=ts_iso,
                )
            except Exception as e:
                logger.warning("WS ob_delta parquet write failed: %s", e)

            # Read current cached book, apply delta
            cached = await redis_store.cache_get(f"clob:book:{asset_id}")
            if not cached:
                continue
            try:
                book = json.loads(cached)
            except json.JSONDecodeError:
                continue

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
        ts_iso = _ws_ts_to_iso(data.get("timestamp", ""))

        await redis_store.cache_set(
            f"clob:mid:{asset_id}", str(mid), settings.cache_ttl_midpoint,
        )

        # Throttled Parquet write (max once per 5s per token)
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
                    timestamp=ts_iso,
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
        total = sum(len(s) for s in self._clients.values())
        metrics.set("ws.frontend_clients", total)
        # Ensure upstream is subscribed
        await self.subscribe(asset_ids)
        # Start recording session for these assets
        await self.start_recording(asset_ids)
        # Push cached data so client has initial state immediately
        await self._push_cached_state(ws, asset_ids)

    async def unregister_client(self, ws: WebSocket) -> None:
        orphaned: list[str] = []
        async with self._client_lock:
            for aid in list(self._clients):
                self._clients[aid].discard(ws)
                if not self._clients[aid]:
                    del self._clients[aid]
                    orphaned.append(aid)
        total = sum(len(s) for s in self._clients.values())
        metrics.set("ws.frontend_clients", total)
        # Cascade: unsubscribe upstream for assets with no remaining clients
        if orphaned:
            await self.unsubscribe(orphaned)
            await self.stop_recording(orphaned)

    async def update_client_subscription(
        self, ws: WebSocket, subscribe_ids: list[str], unsubscribe_ids: list[str],
    ) -> None:
        orphaned: list[str] = []
        async with self._client_lock:
            for aid in unsubscribe_ids:
                if aid in self._clients:
                    self._clients[aid].discard(ws)
                    if not self._clients[aid]:
                        del self._clients[aid]
                        orphaned.append(aid)
            for aid in subscribe_ids:
                if aid not in self._clients:
                    self._clients[aid] = set()
                self._clients[aid].add(ws)
        if subscribe_ids:
            await self.subscribe(subscribe_ids)
            await self.start_recording(subscribe_ids)
        if orphaned:
            await self.unsubscribe(orphaned)
            await self.stop_recording(orphaned)

    async def _push_cached_state(self, ws: WebSocket, asset_ids: list[str]) -> None:
        """Send cached orderbook + best_bid_ask from Redis to a newly subscribed client."""
        for aid in asset_ids:
            try:
                cached_book = await redis_store.cache_get(f"clob:book:{aid}")
                if cached_book:
                    book = json.loads(cached_book)
                    book["event_type"] = "book"
                    if "asset_id" not in book:
                        book["asset_id"] = aid
                    await ws.send_text(json.dumps(book))

                    # Derive best_bid_ask from the cached book
                    bids = book.get("bids", [])
                    asks = book.get("asks", [])
                    if bids and asks:
                        best_bid = max(bids, key=lambda lv: float(lv.get("price", 0)))
                        best_ask = min(asks, key=lambda lv: float(lv.get("price", 999)))
                        bba = {
                            "event_type": "best_bid_ask",
                            "asset_id": aid,
                            "market": book.get("market", ""),
                            "best_bid": best_bid["price"],
                            "best_ask": best_ask["price"],
                            "timestamp": book.get("timestamp", ""),
                        }
                        await ws.send_text(json.dumps(bba))
            except Exception as e:
                logger.warning("Failed to push cached state for %s: %s", aid, e)

    async def close_clients_for_assets(self, asset_ids: list[str], reason: str = "event_ended") -> None:
        """Send an event_ended message and close all frontend clients subscribed to given asset_ids."""
        # Collect unique clients across all asset_ids
        to_close: set[WebSocket] = set()
        async with self._client_lock:
            for aid in asset_ids:
                to_close.update(self._clients.get(aid, set()))

        if not to_close:
            return

        # Notify and close each client
        msg = json.dumps({"event_type": "event_ended", "reason": reason, "asset_ids": asset_ids})
        for ws in to_close:
            try:
                await ws.send_text(msg)
            except Exception:
                pass
            try:
                await ws.close(code=1000, reason=reason)
            except Exception:
                pass

        # Remove clients from tracking
        async with self._client_lock:
            for aid in asset_ids:
                self._clients.pop(aid, None)

        # Unsubscribe upstream if no other clients need these assets
        await self.unsubscribe(asset_ids)
        logger.info("Closed %d clients for ended assets: %s", len(to_close), asset_ids)

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

    # ── Recording session management ──────────────────────────

    async def start_recording(self, asset_ids: list[str]) -> None:
        """Begin or resume a recording session for asset_ids.

        Called by ``register_client`` (frontend) and ``auto_recorder`` (headless).
        """
        for aid in asset_ids:
            slug = await self._resolve_slug(aid)
            if not slug or slug in self._sessions:
                continue
            session = {
                "session_id": uuid.uuid4().hex[:12],
                "slug": slug,
                "market_id": await self._resolve_market_id(aid),
                "token_ids": [aid],
                "start_time": datetime.now(timezone.utc).isoformat(),
                "end_time": None,
                "status": "recording",
            }
            self._sessions[slug] = session
            await redis_store.set_recording_session(slug, json.dumps(session))
            self._append_session_log(session)
            logger.info("Recording session started: %s", slug)

    async def stop_recording(self, asset_ids: list[str]) -> None:
        """Mark sessions as incomplete when all frontend clients leave."""
        for aid in asset_ids:
            slug = await self._resolve_slug(aid)
            if not slug or slug not in self._sessions:
                continue
            # Check that no asset of this session still has clients
            session = self._sessions[slug]
            still_active = False
            async with self._client_lock:
                for tid in session.get("token_ids", []):
                    if tid in self._clients and self._clients[tid]:
                        still_active = True
                        break
            if still_active:
                continue
            session["status"] = "incomplete"
            session["end_time"] = datetime.now(timezone.utc).isoformat()
            await redis_store.set_recording_session(slug, json.dumps(session))
            self._append_session_log(session)
            del self._sessions[slug]
            logger.info("Recording session incomplete: %s", slug)

    async def complete_recording(self, slug: str, data_counts: dict | None = None) -> None:
        """Mark a recording session as complete (called by event_lifecycle on archive)."""
        session = self._sessions.pop(slug, None)
        if not session:
            raw = await redis_store.get_recording_session(slug)
            if raw:
                session = raw
        if not session:
            return
        session["status"] = "complete"
        session["end_time"] = datetime.now(timezone.utc).isoformat()
        if data_counts:
            session["data_counts"] = data_counts
        await redis_store.set_recording_session(slug, json.dumps(session))
        self._append_session_log(session)
        logger.info("Recording session complete: %s", slug)

    def _append_session_log(self, session: dict) -> None:
        """Append a session record to the sessions.jsonl index file."""
        try:
            os.makedirs(os.path.dirname(self._sessions_file), exist_ok=True)
            with open(self._sessions_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(session, ensure_ascii=False) + "\n")
        except Exception as e:
            logger.warning("Failed to write session log: %s", e)

    # ── Helpers ───────────────────────────────────────────────

    async def _resolve_market_id(self, token_id: str) -> str:
        """Get market_id for a token_id from watched:markets hash."""
        watched = await redis_store.get_watched_markets()
        return watched.get(token_id, token_id)

    async def _resolve_slug(self, token_id: str) -> str | None:
        """Get slug for a token_id from token:market_info."""
        info = await redis_store.get_token_market_info(token_id)
        if info:
            return info.get("slug")
        return None


# ── Module-level start/stop ──────────────────────────────────────────────────


async def start_ws_manager() -> PolymarketWSManager:
    global _manager
    _manager = PolymarketWSManager()
    await _manager.start()
    return _manager


async def stop_ws_manager() -> None:
    global _manager
    if _manager:
        await _manager.stop()
        _manager = None
