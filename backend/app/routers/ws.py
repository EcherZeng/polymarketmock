"""WebSocket endpoint — frontend connects here for real-time market data."""

from __future__ import annotations

import asyncio
import json
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.services.ws_manager import get_ws_manager

logger = logging.getLogger(__name__)

router = APIRouter()


@router.websocket("/ws/market")
async def market_ws(ws: WebSocket) -> None:
    await ws.accept()
    manager = get_ws_manager()
    subscribed_ids: list[str] = []

    try:
        while True:
            raw = await ws.receive_text()

            # Heartbeat
            if raw.strip() == "PING":
                await ws.send_text("PONG")
                continue

            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                continue

            msg_type = data.get("type", "")

            if msg_type == "subscribe":
                asset_ids = data.get("asset_ids", [])
                if asset_ids:
                    await manager.register_client(ws, asset_ids)
                    subscribed_ids.extend(asset_ids)

            elif msg_type == "unsubscribe":
                asset_ids = data.get("asset_ids", [])
                if asset_ids:
                    await manager.update_client_subscription(ws, [], asset_ids)
                    subscribed_ids = [a for a in subscribed_ids if a not in asset_ids]

    except WebSocketDisconnect:
        pass
    except asyncio.CancelledError:
        pass
    except Exception as e:
        logger.warning("WS client error: %s", e)
    finally:
        await manager.unregister_client(ws)
