"""Presets CRUD API — 策略预设参数的增删改查。"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from api.state import registry

router = APIRouter(prefix="/presets")


class PresetBody(BaseModel):
    description: str = ""
    params: dict = Field(default_factory=dict)


class UnifiedRulesBody(BaseModel):
    take_profit_price: float = Field(ge=0, le=1)
    stop_loss_price: float = Field(ge=0, le=1)
    force_close_remaining_seconds: int = Field(ge=0)


# ── List ─────────────────────────────────────────────────────────────────────


@router.get("")
async def list_presets():
    """List all strategy presets with param schema for frontend form rendering."""
    data = registry.get_presets_data()
    return {
        "unified_rules": data.get("unified_rules", {}),
        "strategies": data.get("strategies", {}),
        "param_schema": registry.get_param_schema(),
        "param_groups": registry.get_param_groups(),
    }


# ── Unified rules (must come BEFORE /{name} to avoid path conflict) ─────────


@router.get("/rules/unified")
async def get_unified_rules():
    """Get the current unified rules."""
    data = registry.get_presets_data()
    return {"unified_rules": data.get("unified_rules", {})}


@router.put("/rules/unified")
async def update_unified_rules(body: UnifiedRulesBody):
    """Update the shared unified rules (TP/SL/force close/loss reduction)."""
    rules = body.model_dump()
    registry.update_unified_rules(rules)
    return {"unified_rules": rules}


# ── Single preset CRUD ───────────────────────────────────────────────────────


@router.get("/{name}")
async def get_preset(name: str):
    """Get a single preset by name."""
    preset = registry.get_preset(name)
    if preset is None:
        raise HTTPException(status_code=404, detail=f"Preset '{name}' not found")
    return {"name": name, **preset}


@router.put("/{name}")
async def save_preset(name: str, body: PresetBody):
    """Create or update a custom preset. Builtin presets can be updated too."""
    preset_data = {**body.params}
    if body.description:
        preset_data["description"] = body.description
    # Preserve builtin flag if it already exists
    existing = registry.get_preset(name)
    if existing and existing.get("builtin"):
        preset_data["builtin"] = True
    registry.save_preset(name, preset_data)
    return {"name": name, "config": registry.get_default_config(name)}


@router.delete("/{name}")
async def delete_preset(name: str):
    """Delete a custom preset. Builtin presets cannot be deleted."""
    preset = registry.get_preset(name)
    if preset is None:
        raise HTTPException(status_code=404, detail=f"Preset '{name}' not found")
    if preset.get("builtin", False):
        raise HTTPException(status_code=400, detail=f"Cannot delete builtin preset '{name}'")
    registry.delete_preset(name)
    return {"deleted": name}
