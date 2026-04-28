"""Config routes — strategy loading, config state, config updates."""

from __future__ import annotations

import logging

import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter()

_session_manager = None


def init_config(session_manager) -> None:
    global _session_manager
    _session_manager = session_manager


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


class LoadPresetBody(BaseModel):
    preset_name: str


class LoadCompositeBody(BaseModel):
    composite_name: str


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


def _build_state() -> dict:
    """Build current strategy state snapshot — no external calls."""
    from config import settings

    composite_info = None
    if _session_manager.composite_config:
        composite_info = _session_manager.composite_config.to_dict()
    return {
        "current_config": _session_manager._strategy_config,
        "composite_config": composite_info,
        "allowed_keys": _ALLOWED_CONFIG_KEYS,
        "executor_mode": settings.executor_mode,
        "active_preset_name": _session_manager.active_preset_name,
        "active_preset_type": _session_manager.active_preset_type,
    }


async def _resolve_branch_configs(
    client: httpx.AsyncClient,
    strategy_service_url: str,
    branches: list[dict],
) -> list[dict]:
    """Resolve each branch's preset_name into actual config params."""
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


# ── Catalog & State ───────────────────────────────────────────────────────────


@router.get("/config/catalog")
async def get_catalog():
    """Return available strategies and composite presets from Strategy service.

    Called once on page load — data rarely changes.
    """
    from config import settings

    backtest_strategies: list[dict] = []
    composite_presets: list[dict] = []
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(f"{settings.strategy_service_url}/strategies")
            if resp.status_code == 200:
                backtest_strategies = resp.json()
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

    return {
        "backtest_strategies": backtest_strategies,
        "composite_presets": composite_presets,
    }


@router.get("/config/state")
async def get_config_state():
    """Return current strategy state — instant, no external calls."""
    if not _session_manager:
        raise HTTPException(503, "Service not initialised")
    return _build_state()


# ── Config Update ─────────────────────────────────────────────────────────────


@router.put("/config")
async def update_config(body: ConfigUpdate):
    if not _session_manager:
        raise HTTPException(503, "Service not initialised")
    validated = _validate_config(body.config)
    _session_manager.update_config(validated)
    return {"ok": True, "state": _build_state()}


# ── Load Preset ───────────────────────────────────────────────────────────────


@router.post("/config/load-preset")
async def load_preset(body: LoadPresetBody):
    """Load a backtest preset's parameters into the live strategy config."""
    if not _session_manager:
        raise HTTPException(503, "Service not initialised")
    from config import settings

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
        v = max(lo, min(hi, v))
        compatible[key] = v

    if not compatible:
        raise HTTPException(
            422,
            f"No compatible parameters found in preset '{body.preset_name}'. "
            f"Skipped keys: {skipped}",
        )

    _session_manager.set_composite_config(None)
    _session_manager.update_config(compatible)
    _session_manager.set_active_preset(body.preset_name, "single")
    logger.info(
        "Loaded preset '%s' → %d params applied, %d skipped",
        body.preset_name, len(compatible), len(skipped),
    )

    return {
        "ok": True,
        "preset_name": body.preset_name,
        "applied": compatible,
        "skipped": skipped,
        "state": _build_state(),
    }


# ── Load Composite ────────────────────────────────────────────────────────────


@router.post("/config/load-composite")
async def load_composite(body: LoadCompositeBody):
    """Load a composite preset from the Strategy service."""
    if not _session_manager:
        raise HTTPException(503, "Service not initialised")
    from config import settings
    from engine.strategy_engine import CompositeConfig

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
            branches = data.get("branches", [])
            if not branches:
                raise HTTPException(422, f"Composite preset '{body.composite_name}' has no branches")

            resolved_branches = await _resolve_branch_configs(
                client, settings.strategy_service_url, branches
            )
            data["branches"] = resolved_branches
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(502, f"Cannot reach Strategy service: {e}")

    composite = CompositeConfig(data)
    _session_manager.set_composite_config(composite)
    _session_manager.set_active_preset(body.composite_name, "composite")

    btc_config = {
        "btc_trend_window_1": composite.window_1,
        "btc_trend_window_2": composite.window_2,
        "btc_min_momentum": composite.btc_min_momentum,
    }
    _session_manager.update_config(btc_config)

    return {
        "ok": True,
        "state": _build_state(),
    }


@router.delete("/config/composite")
async def clear_composite():
    """Clear active strategy — revert to no-preset mode."""
    if not _session_manager:
        raise HTTPException(503, "Service not initialised")
    _session_manager.set_composite_config(None)
    _session_manager.set_active_preset(None, "none")
    return {"ok": True, "state": _build_state()}
