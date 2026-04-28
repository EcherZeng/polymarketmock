"""WebSocket client — connects to Polymarket Market Channel for live data."""

from __future__ import annotations

import asyncio
import json
import logging
import time
from datetime import datetime, timezone
from typing import Callable, Awaitable

import websockets

from config import settings

logger = logging.getLogger(__name__)

# Type for event callbacks: async fn(event_type, asset_id, data)
EventCallback = Callable[[str, str, dict], Awaitable[None]]


def _ws_ts_to_iso(ts_ms: str | int | float) -> str | None:
    """Convert Polymarket WS unix-millisecond timestamp to ISO 8601."""
    try:
        return datetime.fromtimestamp(
            float(ts_ms) / 1000, tz=timezone.utc,
        ).isoformat()
    except (ValueError, TypeError, OverflowError):
        return None


class PolymarketWSClient:
    """Manages a single upstream WebSocket connection to Polymarket.

    Handles subscription, reconnection, and event dispatch.
    """

    def __init__(self, on_event: EventCallback) -> None:
        self._on_event = on_event
        self._ws: websockets.WebSocketClientProtocol | None = None  # type: ignore[name-defined]
        self._task: asyncio.Task | None = None
        self._ping_task: asyncio.Task | None = None
        self._stop = asyncio.Event()

        self._subscribed: set[str] = set()
        self._pending_subscribe: set[str] = set()
        self._initial_sub_sent: bool = False
        self.connected: bool = False

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

    # ── Subscription ──────────────────────────────────────────

    async def subscribe(self, asset_ids: list[str]) -> None:
        """Add asset_ids to subscription. Sends immediately if connected."""
        new_ids = set(asset_ids) - self._subscribed
        if not new_ids:
            return
        self._subscribed.update(new_ids)

        if self._ws and self.connected and self._initial_sub_sent:
            await self._send_incremental_subscribe(list(new_ids))
        else:
            self._pending_subscribe.update(new_ids)

    async def unsubscribe(self, asset_ids: list[str]) -> None:
        """Remove asset_ids from subscription."""
        for aid in asset_ids:
            self._subscribed.discard(aid)
            self._pending_subscribe.discard(aid)

    # ── Connection loop ───────────────────────────────────────

    async def _run_loop(self) -> None:
        backoff = 1
        while not self._stop.is_set():
            # Wait until we have something to subscribe to
            if not self._subscribed:
                await asyncio.sleep(0.5)
                continue

            try:
                await self._connect_and_listen()
                backoff = 1  # reset on clean disconnect
            except asyncio.CancelledError:
                return
            except Exception as e:
                if self._subscribed:
                    logger.warning("WS error: %s — reconnecting in %ss", e, backoff)

            self.connected = False

            if not self._subscribed:
                backoff = 1
                continue

            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, settings.ws_reconnect_max)

    async def _connect_and_listen(self) -> None:
        logger.info("Connecting to Polymarket WS: %s", settings.ws_url)
        async with websockets.connect(
            settings.ws_url,
            ping_interval=None,     # app-level PING, not library-level
            ping_timeout=None,
            close_timeout=10,
        ) as ws:
            self._ws = ws
            self.connected = True
            self._initial_sub_sent = False
            logger.info("Polymarket WS connected")

            # Send initial subscription
            if self._subscribed:
                await self._send_initial_subscribe(list(self._subscribed))

            # Flush any pending
            if self._pending_subscribe:
                pending = list(self._pending_subscribe)
                self._pending_subscribe.clear()
                if self._initial_sub_sent:
                    await self._send_incremental_subscribe(pending)

            # Start ping
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

    # ── Subscription messages ─────────────────────────────────

    async def _send_initial_subscribe(self, asset_ids: list[str]) -> None:
        if not self._ws:
            return
        msg = {
            "assets_ids": asset_ids,
            "type": "market",
            "initial_dump": True,
            "custom_feature_enabled": True,
        }
        await self._ws.send(json.dumps(msg))
        self._initial_sub_sent = True
        logger.info("WS subscribed to %d assets (initial)", len(asset_ids))

    async def _send_incremental_subscribe(self, asset_ids: list[str]) -> None:
        if not self._ws:
            return
        msg = {
            "operation": "subscribe",
            "assets_ids": asset_ids,
            "custom_feature_enabled": True,
        }
        await self._ws.send(json.dumps(msg))
        logger.info("WS subscribed to %d assets (incremental)", len(asset_ids))

    # ── Message dispatch ──────────────────────────────────────

    async def _on_message(self, raw: str | bytes) -> None:
        if isinstance(raw, bytes):
            raw = raw.decode("utf-8", errors="replace")

        text = raw.strip()

        # Handle PONG
        if text == "PONG":
            return

        # Parse array of events
        try:
            messages = json.loads(text)
        except json.JSONDecodeError:
            return

        if not isinstance(messages, list):
            messages = [messages]

        for msg in messages:
            if not isinstance(msg, dict):
                continue
            event_type = msg.get("event_type", "")
            asset_id = msg.get("asset_id", "")
            if event_type and asset_id:
                try:
                    await self._on_event(event_type, asset_id, msg)
                except Exception as e:
                    logger.error("WS event handler error (%s/%s): %s", event_type, asset_id[:12], e)
