"""BTC price streamer — connects to Binance WebSocket for real-time BTCUSDT trades."""

from __future__ import annotations

import asyncio
import json
import logging
import time
from datetime import datetime, timezone

import websockets

from infra.live_hub import LiveHub

logger = logging.getLogger(__name__)

# Binance WebSocket stream — aggregated trade (1 msg per trade, ~100ms avg)
BINANCE_WS_URL = "wss://stream.binance.com:9443/ws/btcusdt@aggTrade"

# Throttle: broadcast to frontend at most once per second
BROADCAST_INTERVAL = 1.0


class BtcPriceStreamer:
    """Connects to Binance WS for real-time BTC price.
    
    Runs independently of frontend connections — always keeps the Binance WS
    alive. Broadcasts throttled updates to LiveHub only when clients exist.
    """

    def __init__(self, hub: LiveHub) -> None:
        self._hub = hub
        self._task: asyncio.Task | None = None
        self._stop = asyncio.Event()
        self._last_price: float = 0.0
        self._last_broadcast: float = 0.0
        # Global circular history (for fallback / debug only)
        self._history: list[dict] = []
        self._max_history = 900  # 15 minutes at 1s

    @property
    def last_price(self) -> float:
        return self._last_price

    @property
    def history(self) -> list[dict]:
        return list(self._history)

    async def start(self) -> None:
        self._stop.clear()
        self._task = asyncio.create_task(self._run())
        logger.info("BtcPriceStreamer started (Binance WS)")

    async def stop(self) -> None:
        self._stop.set()
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("BtcPriceStreamer stopped")

    async def _run(self) -> None:
        backoff = 1
        while not self._stop.is_set():
            try:
                await self._connect()
                backoff = 1  # reset on clean disconnect
            except asyncio.CancelledError:
                return
            except Exception as e:
                logger.warning("BTC WS error: %s — reconnecting in %ds", e, backoff)
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, 30)

    async def _connect(self) -> None:
        """Connect to Binance WS and process aggTrade messages."""
        async with websockets.connect(BINANCE_WS_URL, ping_interval=20) as ws:
            logger.info("Binance BTC WS connected")
            while not self._stop.is_set():
                try:
                    raw = await asyncio.wait_for(ws.recv(), timeout=30)
                except asyncio.TimeoutError:
                    # No data in 30s — connection might be stale
                    await ws.ping()
                    continue

                data = json.loads(raw)
                price = float(data.get("p", 0))
                if price <= 0:
                    continue

                self._last_price = price

                # Throttle broadcasts to 1/second
                now = time.monotonic()
                if now - self._last_broadcast >= BROADCAST_INTERVAL:
                    self._last_broadcast = now
                    ts_ms = data.get("T", 0)
                    if ts_ms:
                        ts_iso = datetime.fromtimestamp(ts_ms / 1000, tz=timezone.utc).isoformat()
                    else:
                        ts_iso = datetime.now(timezone.utc).isoformat()

                    point = {"price": price, "timestamp": ts_iso}
                    self._history.append(point)
                    if len(self._history) > self._max_history:
                        self._history = self._history[-self._max_history:]

                    # Broadcast to frontend only when clients are watching
                    if self._hub.client_count > 0:
                        await self._hub.broadcast("btc_price", point)
