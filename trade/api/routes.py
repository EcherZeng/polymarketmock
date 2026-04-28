"""Trade service API — FastAPI routes for monitoring and control."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter()

# These will be injected at app startup
_session_manager = None
_tracker = None
_store = None
_btc_streamer = None


def init_routes(session_manager, tracker, store, btc_streamer=None) -> None:
    global _session_manager, _tracker, _store, _btc_streamer
    _session_manager = session_manager
    _tracker = tracker
    _store = store
    _btc_streamer = btc_streamer


# ── Health ────────────────────────────────────────────────────────────────────


@router.get("/health")
async def health():
    return {"status": "ok", "service": "trade"}


# ── Status ────────────────────────────────────────────────────────────────────


@router.get("/status")
async def status():
    if not _session_manager:
        raise HTTPException(503, "Service not initialised")
    return _session_manager.get_status()


# ── Positions ─────────────────────────────────────────────────────────────────


@router.get("/positions")
async def positions():
    if not _tracker:
        raise HTTPException(503, "Service not initialised")
    return _tracker.to_dict()


# ── Balance ───────────────────────────────────────────────────────────────────


@router.get("/balance")
async def balance():
    if not _tracker:
        raise HTTPException(503, "Service not initialised")
    return {
        "balance": round(_tracker.balance, 6),
        "initial_balance": round(_tracker.initial_balance, 6),
    }


# ── PnL ───────────────────────────────────────────────────────────────────────


@router.get("/pnl")
async def pnl():
    if not _store:
        raise HTTPException(503, "Service not initialised")
    total = _store.get_total_pnl()
    recent = _store.get_recent_pnl(10)
    return {"total": total, "recent": recent}


# ── Sessions ──────────────────────────────────────────────────────────────────


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


# ── Trades ────────────────────────────────────────────────────────────────────


@router.get("/trades")
async def trades(session_slug: str | None = None, limit: int = 100):
    if not _store:
        raise HTTPException(503, "Service not initialised")
    return _store.get_trades(session_slug=session_slug, limit=limit)


# ── Config ────────────────────────────────────────────────────────────────────


# P0-4: Validated strategy config — only allowed keys with bounded values
_ALLOWED_CONFIG_KEYS: dict[str, tuple[float, float]] = {
    "min_price": (0.01, 1.0),
    "observation_s": (0, 900),
    "profit_margin": (0.0, 0.50),
    "position_min_pct": (0.01, 1.0),
    "position_max_pct": (0.01, 1.0),
    "take_profit_price": (0.5, 1.0),
    "stop_loss_price": (0.0, 1.0),
    "force_close_remaining_s": (0, 300),
    "min_close_profit": (0.0, 1.0),
}


class ConfigUpdate(BaseModel):
    config: dict


def _validate_config(config: dict) -> dict:
    """Validate config keys and value ranges. Raises HTTPException on invalid."""
    cleaned: dict = {}
    for key, value in config.items():
        if key not in _ALLOWED_CONFIG_KEYS:
            raise HTTPException(422, f"Unknown config key: {key}")
        lo, hi = _ALLOWED_CONFIG_KEYS[key]
        try:
            v = float(value)
        except (TypeError, ValueError):
            raise HTTPException(422, f"Config '{key}' must be numeric, got: {value}")
        if not (lo <= v <= hi):
            raise HTTPException(422, f"Config '{key}' must be in [{lo}, {hi}], got: {v}")
        cleaned[key] = v
    return cleaned


@router.get("/config")
async def get_config():
    if not _session_manager:
        raise HTTPException(503, "Service not initialised")
    from config import settings
    from core.strategy_engine import list_strategies
    return {
        "strategy": list_strategies(),
        "current_config": _session_manager._strategy_config,
        "allowed_keys": _ALLOWED_CONFIG_KEYS,
        "executor_mode": settings.executor_mode,
    }


@router.put("/config")
async def update_config(body: ConfigUpdate):
    if not _session_manager:
        raise HTTPException(503, "Service not initialised")
    validated = _validate_config(body.config)
    _session_manager.update_config(validated)
    return {"ok": True, "config": validated}


# ── Pause / Resume ────────────────────────────────────────────────────────────


@router.post("/pause")
async def pause():
    if not _session_manager:
        raise HTTPException(503, "Service not initialised")
    _session_manager.pause()
    return {"paused": True}


@router.post("/resume")
async def resume():
    if not _session_manager:
        raise HTTPException(503, "Service not initialised")
    _session_manager.resume()
    return {"paused": False}


# ── Executor mode ─────────────────────────────────────────────────────────────


class ModeUpdate(BaseModel):
    mode: str


@router.get("/executor-mode")
async def get_executor_mode():
    from config import settings
    return {"executor_mode": settings.executor_mode}


@router.put("/executor-mode")
async def set_executor_mode(body: ModeUpdate):
    if body.mode not in ("real", "mock"):
        raise HTTPException(422, "mode must be 'real' or 'mock'")
    if not _session_manager:
        raise HTTPException(503, "Service not initialised")
    from config import settings
    from core.executor_factory import create_executor

    old_mode = settings.executor_mode
    if body.mode == old_mode:
        return {"executor_mode": old_mode, "changed": False}

    # Stop old executor
    old_executor = _session_manager._executor
    await old_executor.stop()

    # Create and start new executor
    settings.executor_mode = body.mode
    new_executor = create_executor(body.mode)
    await new_executor.start()

    # If switching to real mode, sync balance
    if body.mode == "real" and new_executor.is_ready:
        real_balance = await new_executor.get_balance()
        if real_balance is not None:
            _session_manager._tracker.set_balance(real_balance)
        await new_executor.check_allowance()

    _session_manager._executor = new_executor
    return {"executor_mode": body.mode, "changed": True}


# ── Price snapshots ───────────────────────────────────────────────────────────


@router.get("/price-snapshots/{slug}")
async def price_snapshots(slug: str, limit: int = 300):
    if not _store:
        raise HTTPException(503, "Service not initialised")
    return _store.get_price_snapshots(slug, limit)


# ── BTC price ─────────────────────────────────────────────────────────────────


@router.get("/btc-price")
async def btc_price():
    if not _btc_streamer:
        raise HTTPException(503, "BTC streamer not initialised")
    return {
        "price": _btc_streamer.last_price,
        "history": _btc_streamer.history[-60:],  # last 60 seconds
    }
