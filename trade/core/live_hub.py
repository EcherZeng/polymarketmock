"""Live hub — manages WebSocket broadcast to frontend clients."""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone

from fastapi import WebSocket

logger = logging.getLogger(__name__)


def _json_default(obj):
    """Handle datetime serialisation for JSON."""
    if isinstance(obj, datetime):
        return obj.isoformat()
    raise TypeError(f"Object of type {type(obj)} is not JSON serializable")


class LiveHub:
    """Broadcast hub for WebSocket connections to frontend clients."""

    def __init__(self) -> None:
        self._clients: set[WebSocket] = set()
        self._lock = asyncio.Lock()

    async def connect(self, ws: WebSocket) -> None:
        await ws.accept()
        async with self._lock:
            self._clients.add(ws)
        logger.info("WS client connected (total=%d)", len(self._clients))

    async def disconnect(self, ws: WebSocket) -> None:
        async with self._lock:
            self._clients.discard(ws)
        logger.info("WS client disconnected (total=%d)", len(self._clients))

    async def broadcast(self, msg_type: str, data: dict) -> None:
        """Send a typed JSON message to all connected clients."""
        if not self._clients:
            return
        payload = json.dumps({"type": msg_type, "data": data, "ts": datetime.now(timezone.utc).isoformat()}, default=_json_default)
        dead: list[WebSocket] = []
        async with self._lock:
            for ws in self._clients:
                try:
                    await ws.send_text(payload)
                except Exception:
                    dead.append(ws)
            for ws in dead:
                self._clients.discard(ws)

    @property
    def client_count(self) -> int:
        return len(self._clients)
