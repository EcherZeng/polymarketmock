"""WebSocket endpoint for live frontend streaming."""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from core.live_hub import LiveHub

logger = logging.getLogger(__name__)

ws_router = APIRouter()

_hub: LiveHub | None = None
_session_manager = None
_tracker = None
_store = None
_btc_streamer = None


def init_ws(hub: LiveHub, session_manager, tracker, store, btc_streamer) -> None:
    global _hub, _session_manager, _tracker, _store, _btc_streamer
    _hub = hub
    _session_manager = session_manager
    _tracker = tracker
    _store = store
    _btc_streamer = btc_streamer


def _json_default(obj):
    """Handle datetime serialisation for WebSocket JSON."""
    if isinstance(obj, datetime):
        return obj.isoformat()
    raise TypeError(f"Object of type {type(obj)} is not JSON serializable")


async def _ws_send(ws: WebSocket, msg_type: str, data) -> None:
    """Send JSON with datetime-safe serialisation."""
    payload = json.dumps({"type": msg_type, "data": data}, default=_json_default)
    await ws.send_text(payload)


@ws_router.websocket("/ws/live")
async def ws_live(ws: WebSocket):
    """Main WebSocket endpoint for real-time session data."""
    if not _hub:
        await ws.close(code=1011, reason="Hub not initialised")
        return

    await _hub.connect(ws)

    # Send initial snapshot on connect
    try:
        await _send_initial_snapshot(ws)
    except Exception as e:
        logger.warning("Failed to send initial snapshot: %s", e)

    # Keep alive + listen for client messages
    try:
        while True:
            # Wait for any client message (ping/pong or commands)
            try:
                msg = await asyncio.wait_for(ws.receive_text(), timeout=30)
            except asyncio.TimeoutError:
                # Send server ping
                try:
                    await _ws_send(ws, "ping", None)
                except Exception:
                    break
                continue
            # Could handle client commands here (e.g. subscribe to specific session)
    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.debug("WS connection error: %s", e)
    finally:
        await _hub.disconnect(ws)


async def _send_initial_snapshot(ws: WebSocket):
    """Send current state to newly connected client."""
    # Session status
    if _session_manager:
        status = _session_manager.get_status()
        await _ws_send(ws, "session", status)

    # Market data from active session
    if _session_manager and _session_manager.current_session:
        slot = _session_manager.current_session
        market = _build_market_snapshot(slot)
        if market:
            await _ws_send(ws, "market", market)

    # BTC price history — use session-scoped history from the active slot
    if _session_manager and _session_manager.current_session:
        slot = _session_manager.current_session
        if slot.btc_history:
            await _ws_send(ws, "btc_history", slot.btc_history)

    # Recent price snapshots for active session
    if _store and _session_manager and _session_manager.current_session:
        slug = _session_manager.current_session.session.slug
        snapshots = _store.get_price_snapshots(slug, limit=300)
        if snapshots:
            await _ws_send(ws, "price_history", snapshots)

    # Recent trades for active session
    if _store and _session_manager and _session_manager.current_session:
        slug = _session_manager.current_session.session.slug
        trades = _store.get_trades(session_slug=slug, limit=50)
        if trades:
            await _ws_send(ws, "trades", trades)


def _build_market_snapshot(slot) -> dict | None:
    """Build market data snapshot from active session slot."""
    if not slot or not slot.session:
        return None

    result = {"slug": slot.session.slug, "tokens": {}}
    for i, token_id in enumerate(slot.session.token_ids):
        mkt = slot.ob.get_market_data(token_id)
        outcome = slot.session.outcomes[i] if i < len(slot.session.outcomes) else "Unknown"
        result["tokens"][token_id] = {
            "outcome": outcome,
            "mid_price": mkt.mid_price,
            "best_bid": mkt.best_bid,
            "best_ask": mkt.best_ask,
            "spread": mkt.spread,
            "anchor_price": mkt.anchor_price,
            "bid_levels": [[p, s] for p, s in mkt.bid_levels[:5]],
            "ask_levels": [[p, s] for p, s in mkt.ask_levels[:5]],
        }
    return result
