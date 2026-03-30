"""Strategy query API."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from api.state import registry

router = APIRouter()


@router.get("/strategies")
async def list_strategies():
    """List all loaded strategies."""
    return registry.list_strategies()


@router.get("/strategies/{name}")
async def get_strategy(name: str):
    """Get strategy details by name."""
    cls = registry.get(name)
    if cls is None:
        raise HTTPException(status_code=404, detail=f"Strategy '{name}' not found")
    return {
        "name": cls.name,
        "description": cls.description,
        "version": cls.version,
        "default_config": cls.default_config,
    }
