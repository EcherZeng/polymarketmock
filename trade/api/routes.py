"""Trade service API — FastAPI routes for monitoring and control."""

from __future__ import annotations

import logging

import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

logger = logging.getLogger(__name__)

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
    "profit_margin": (0.0, 0.50),
    "position_min_pct": (0.01, 1.0),
    "position_max_pct": (0.01, 1.0),
    "take_profit_price": (0.5, 1.0),
    "stop_loss_price": (0.0, 1.0),
    "force_close_remaining_s": (0, 300),
    "min_close_profit": (0.0, 1.0),
    # BTC trend parameters
    "btc_trend_window_1": (1, 14),
    "btc_trend_window_2": (2, 14),
    "btc_min_momentum": (0.0, 0.1),
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
    from core.strategy_engine import list_strategies as list_local_strategies

    # Fetch strategies from Strategy backtest service
    backtest_strategies: list[dict] = []
    composite_presets: list[dict] = []
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(f"{settings.strategy_service_url}/strategies")
            if resp.status_code == 200:
                backtest_strategies = resp.json()
            # Also fetch composite presets and resolve branch configs
            resp2 = await client.get(f"{settings.strategy_service_url}/composite-presets")
            if resp2.status_code == 200:
                raw_composites: list[dict] = resp2.json()
                for cp in raw_composites:
                    branches = cp.get("branches", [])
                    cp["branches"] = await _resolve_branch_configs(
                        client, settings.strategy_service_url, branches
                    )
                composite_presets = raw_composites
    except Exception as e:
        logger.debug("Failed to fetch strategies from Strategy service: %s", e)

    # Local live strategies
    local_strategies = list_local_strategies()

    # Composite config if active
    composite_info = None
    if _session_manager.composite_config:
        composite_info = _session_manager.composite_config.to_dict()

    return {
        "local_strategies": local_strategies,
        "backtest_strategies": backtest_strategies,
        "composite_presets": composite_presets,
        "current_config": _session_manager._strategy_config,
        "composite_config": composite_info,
        "allowed_keys": _ALLOWED_CONFIG_KEYS,
        "executor_mode": settings.executor_mode,
        "active_strategy": _session_manager._strategy_name,
    }


@router.put("/config")
async def update_config(body: ConfigUpdate):
    if not _session_manager:
        raise HTTPException(503, "Service not initialised")
    validated = _validate_config(body.config)
    _session_manager.update_config(validated)
    return {"ok": True, "config": validated}


class LoadPresetBody(BaseModel):
    preset_name: str


@router.post("/config/load-preset")
async def load_preset(body: LoadPresetBody):
    """Load a backtest preset's parameters into the live strategy config.

    Fetches the preset from the Strategy service, filters to keys that are
    compatible with the live strategy (i.e. present in _ALLOWED_CONFIG_KEYS),
    validates ranges, and applies them.
    """
    if not _session_manager:
        raise HTTPException(503, "Service not initialised")
    from config import settings

    # 1. Fetch the preset's default_config from the Strategy service
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(
                f"{settings.strategy_service_url}/strategies/{body.preset_name}"
            )
    except Exception as e:
        raise HTTPException(502, f"Cannot reach Strategy service: {e}")

    if resp.status_code == 404:
        raise HTTPException(404, f"Preset '{body.preset_name}' not found in Strategy service")
    if resp.status_code != 200:
        raise HTTPException(502, f"Strategy service returned {resp.status_code}")

    data = resp.json()
    preset_config = data.get("default_config", {})
    if not preset_config:
        raise HTTPException(422, f"Preset '{body.preset_name}' has no parameters")

    # 2. Filter to keys compatible with live strategy & validate ranges
    compatible: dict = {}
    skipped: list[str] = []
    for key, value in preset_config.items():
        if key not in _ALLOWED_CONFIG_KEYS:
            skipped.append(key)
            continue
        lo, hi = _ALLOWED_CONFIG_KEYS[key]
        try:
            v = float(value)
        except (TypeError, ValueError):
            skipped.append(key)
            continue
        # Clamp to allowed range instead of rejecting
        v = max(lo, min(hi, v))
        compatible[key] = v

    if not compatible:
        raise HTTPException(
            422,
            f"No compatible parameters found in preset '{body.preset_name}'. "
            f"Skipped keys: {skipped}",
        )

    # 3. Apply to live config
    _session_manager.update_config(compatible)
    logger.info(
        "Loaded preset '%s' → %d params applied, %d skipped",
        body.preset_name, len(compatible), len(skipped),
    )

    return {
        "ok": True,
        "preset_name": body.preset_name,
        "applied": compatible,
        "skipped": skipped,
        "current_config": _session_manager._strategy_config,
    }


# ── Composite preset ─────────────────────────────────────────────────────────


class LoadCompositeBody(BaseModel):
    composite_name: str


async def _resolve_branch_configs(
    client: httpx.AsyncClient,
    strategy_service_url: str,
    branches: list[dict],
) -> list[dict]:
    """Resolve each branch's preset_name into actual config params.

    Fetches the referenced strategy preset from the Strategy service
    and embeds the default_config into the branch's 'config' field.
    """
    resolved = []
    for branch in branches:
        preset_name = branch.get("preset_name", "")
        config = branch.get("config")
        if not config and preset_name:
            try:
                resp = await client.get(
                    f"{strategy_service_url}/strategies/{preset_name}"
                )
                if resp.status_code == 200:
                    preset_data = resp.json()
                    config = preset_data.get("default_config", {})
            except Exception:
                logger.debug("Failed to resolve branch preset '%s'", preset_name)
        resolved.append({**branch, "config": config or {}})
    return resolved


@router.post("/config/load-composite")
async def load_composite(body: LoadCompositeBody):
    """Load a composite preset from the Strategy service.

    Composite presets define multiple branches with different configs,
    selected per-session based on BTC amplitude (two-window sita).
    """
    if not _session_manager:
        raise HTTPException(503, "Service not initialised")
    from config import settings
    from core.strategy_engine import CompositeConfig

    # Fetch composite preset from Strategy service
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(
                f"{settings.strategy_service_url}/composite-presets/{body.composite_name}"
            )
            if resp.status_code == 404:
                raise HTTPException(404, f"Composite preset '{body.composite_name}' not found")
            if resp.status_code != 200:
                raise HTTPException(502, f"Strategy service returned {resp.status_code}")

            data = resp.json()

            # Validate structure
            branches = data.get("branches", [])
            if not branches:
                raise HTTPException(422, f"Composite preset '{body.composite_name}' has no branches")

            # Resolve each branch's preset_name → actual config
            resolved_branches = await _resolve_branch_configs(
                client, settings.strategy_service_url, branches
            )
            data["branches"] = resolved_branches
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(502, f"Cannot reach Strategy service: {e}")

    # Build composite config
    composite = CompositeConfig(data)
    _session_manager.set_composite_config(composite)

    # Update base strategy config with BTC window params from composite
    btc_config = {
        "btc_trend_window_1": composite.window_1,
        "btc_trend_window_2": composite.window_2,
        "btc_min_momentum": composite.btc_min_momentum,
    }
    _session_manager.update_config(btc_config)

    return {
        "ok": True,
        "composite_name": composite.name,
        "branches": len(composite.branches),
        "btc_windows": {"window_1": composite.window_1, "window_2": composite.window_2},
        "branch_details": [
            {
                "label": b.get("label", "?"),
                "min_momentum": b.get("min_momentum", 0),
                "preset_name": b.get("preset_name", ""),
                "config": b.get("config", {}),
            }
            for b in composite.branches
        ],
    }


@router.delete("/config/composite")
async def clear_composite():
    """Clear composite strategy — revert to single strategy mode."""
    if not _session_manager:
        raise HTTPException(503, "Service not initialised")
    _session_manager.set_composite_config(None)
    return {"ok": True, "composite_config": None}


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
