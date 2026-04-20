"""Presets CRUD API — 策略预设参数的增删改查。"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from api.state import registry

router = APIRouter(prefix="/presets")


class PresetBody(BaseModel):
    description: str = ""
    params: dict = Field(default_factory=dict)


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


class RenameBody(BaseModel):
    new_name: str = Field(..., min_length=1, max_length=100)


@router.patch("/{name}/rename")
async def rename_preset(name: str, body: RenameBody):
    """Rename a custom preset. Builtin presets cannot be renamed."""
    preset = registry.get_preset(name)
    if preset is None:
        raise HTTPException(status_code=404, detail=f"Preset '{name}' not found")
    if preset.get("builtin", False):
        raise HTTPException(status_code=400, detail=f"Cannot rename builtin preset '{name}'")
    if registry.get_preset(body.new_name) is not None:
        raise HTTPException(status_code=409, detail=f"Preset '{body.new_name}' already exists")
    ok = registry.rename_preset(name, body.new_name)
    if not ok:
        raise HTTPException(status_code=400, detail="Rename failed")
    return {"old_name": name, "new_name": body.new_name}


# ── Composite Presets CRUD ───────────────────────────────────────────────────

composite_router = APIRouter(prefix="/composite-presets")


class CompositeBranchBody(BaseModel):
    label: str
    min_momentum: float = Field(ge=0)
    preset_name: str


class CompositePresetBody(BaseModel):
    description: str = ""
    btc_windows: dict = Field(default_factory=lambda: {"btc_trend_window_1": 5, "btc_trend_window_2": 10})
    branches: list[CompositeBranchBody] = Field(default_factory=list)


@composite_router.get("")
async def list_composite_presets():
    """List all composite presets."""
    return registry.list_composite_presets()


@composite_router.get("/{name}")
async def get_composite_preset(name: str):
    preset = registry.get_composite_preset(name)
    if preset is None:
        raise HTTPException(status_code=404, detail=f"Composite preset '{name}' not found")
    return {"name": name, **preset}


@composite_router.put("/{name}")
async def save_composite_preset(name: str, body: CompositePresetBody):
    """Create or update a composite preset."""
    data = {
        "description": body.description,
        "btc_windows": body.btc_windows,
        "branches": [b.model_dump() for b in body.branches],
    }
    try:
        registry.save_composite_preset(name, data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"name": name, **registry.get_composite_preset(name)}


@composite_router.delete("/{name}")
async def delete_composite_preset(name: str):
    if registry.get_composite_preset(name) is None:
        raise HTTPException(status_code=404, detail=f"Composite preset '{name}' not found")
    registry.delete_composite_preset(name)
    return {"deleted": name}


@composite_router.patch("/{name}/rename")
async def rename_composite_preset(name: str, body: RenameBody):
    if registry.get_composite_preset(name) is None:
        raise HTTPException(status_code=404, detail=f"Composite preset '{name}' not found")
    if registry.get_composite_preset(body.new_name) is not None:
        raise HTTPException(status_code=409, detail=f"Composite preset '{body.new_name}' already exists")
    ok = registry.rename_composite_preset(name, body.new_name)
    if not ok:
        raise HTTPException(status_code=400, detail="Rename failed")
    return {"old_name": name, "new_name": body.new_name}
