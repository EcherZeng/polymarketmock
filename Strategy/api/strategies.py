"""Strategy query API."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from api.state import registry

router = APIRouter()


@router.get("/strategies")
async def list_strategies():
    """List all loaded strategies with preset configs."""
    return registry.list_strategies()


@router.get("/strategies/{name}")
async def get_strategy(name: str):
    """Get strategy preset details by name."""
    if not registry.has(name):
        raise HTTPException(status_code=404, detail=f"Strategy '{name}' not found")
    strategies = registry.list_strategies()
    for s in strategies:
        if s["name"] == name:
            return s
    raise HTTPException(status_code=404, detail=f"Strategy '{name}' not found")
