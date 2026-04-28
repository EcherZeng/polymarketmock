"""Monitoring routes — health, status, positions, balance, PnL, sessions, trades."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

router = APIRouter()

_session_manager = None
_tracker = None
_store = None
_btc_streamer = None


def init_monitor(session_manager, tracker, store, btc_streamer=None) -> None:
    global _session_manager, _tracker, _store, _btc_streamer
    _session_manager = session_manager
    _tracker = tracker
    _store = store
    _btc_streamer = btc_streamer


@router.get("/health")
async def health():
    return {"status": "ok", "service": "trade"}


@router.get("/status")
async def status():
    if not _session_manager:
        raise HTTPException(503, "Service not initialised")
    return _session_manager.get_status()


@router.get("/positions")
async def positions():
    if not _tracker:
        raise HTTPException(503, "Service not initialised")
    return _tracker.to_dict()


@router.get("/balance")
async def balance():
    if not _tracker:
        raise HTTPException(503, "Service not initialised")
    return {
        "balance": round(_tracker.balance, 6),
        "initial_balance": round(_tracker.initial_balance, 6),
    }


@router.get("/pnl")
async def pnl():
    if not _store:
        raise HTTPException(503, "Service not initialised")
    total = _store.get_total_pnl()
    recent = _store.get_recent_pnl(10)
    return {"total": total, "recent": recent}


@router.get("/sessions")
async def sessions(limit: int = 50):
    if not _store:
        raise HTTPException(503, "Service not initialised")
    return _store.get_sessions(limit)


@router.get("/sessions/{slug}")
async def session_detail(slug: str):
    if not _store:
        raise HTTPException(503, "Service not initialised")
    session = _store.get_session(slug)
    if not session:
        raise HTTPException(404, "Session not found")
    trades = _store.get_trades(session_slug=slug)
    return {"session": session, "trades": trades}


@router.get("/trades")
async def trades(session_slug: str | None = None, limit: int = 100):
    if not _store:
        raise HTTPException(503, "Service not initialised")
    return _store.get_trades(session_slug=session_slug, limit=limit)


@router.get("/price-snapshots/{slug}")
async def price_snapshots(slug: str):
    if not _store:
        raise HTTPException(503, "Service not initialised")
    return _store.get_snapshots(slug)


@router.get("/btc-price")
async def btc_price():
    if not _btc_streamer:
        raise HTTPException(503, "BTC streamer not initialised")
    return {
        "price": _btc_streamer.last_price,
        "history": _btc_streamer.history[-60:],
    }
