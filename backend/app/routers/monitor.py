"""Monitor endpoints — log viewer + metrics dashboard."""

from __future__ import annotations

import asyncio
import json

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect

from app.services.log_buffer import get_log_handler, metrics

router = APIRouter()
ws_router = APIRouter()


# ── REST: recent logs ─────────────────────────────────────────────────────────

@router.get("/logs", response_model=list[dict])
async def get_logs(
    limit: int = Query(200, ge=1, le=2000),
    level: str | None = Query(None),
    module: str | None = Query(None),
):
    """Return recent log entries from the in-memory ring buffer."""
    return get_log_handler().get_logs(limit=limit, level=level, module=module)


# ── REST: metrics snapshot ────────────────────────────────────────────────────

@router.get("/metrics")
async def get_metrics():
    """Return current counters, gauges and uptime."""
    handler = get_log_handler()
    snap = metrics.snapshot()
    snap["log_buffer_size"] = len(handler._buffer)
    return snap


# ── WebSocket: live log stream ────────────────────────────────────────────────

@ws_router.websocket("/ws/logs")
async def ws_logs(ws: WebSocket):
    """Stream log entries in real time to connected dashboard clients."""
    await ws.accept()
    handler = get_log_handler()
    queue = handler.init_ws_queue()

    try:
        while True:
            entry = await queue.get()
            await ws.send_text(json.dumps(entry))
    except WebSocketDisconnect:
        pass
    except asyncio.CancelledError:
        pass
    except Exception:
        pass
