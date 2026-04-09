"""Sensitivity analysis API — parameter sweep endpoints."""

from __future__ import annotations

from dataclasses import asdict

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

import api.state as state

router = APIRouter(prefix="/sensitivity", tags=["Sensitivity"])


# ── Request / Response models ────────────────────────────────────────────────


class SensitivityRequest(BaseModel):
    strategy: str
    slug: str
    base_config: dict
    param_key: str
    initial_balance: float = 100.0
    steps: int = 10
    param_min: float | None = None
    param_max: float | None = None


# ── Endpoints ────────────────────────────────────────────────────────────────


@router.post("")
async def submit_sensitivity(req: SensitivityRequest):
    """Submit a sensitivity analysis sweep for a single parameter."""
    if state.sensitivity_analyzer is None:
        raise HTTPException(500, "Sensitivity analyzer not initialized")
    try:
        result = await state.sensitivity_analyzer.submit(
            strategy=req.strategy,
            slug=req.slug,
            base_config=req.base_config,
            param_key=req.param_key,
            initial_balance=req.initial_balance,
            steps=req.steps,
            param_min=req.param_min,
            param_max=req.param_max,
        )
        return {"task_id": result.task_id, "status": result.status}
    except ValueError as exc:
        raise HTTPException(400, str(exc))


@router.get("")
async def list_sensitivity_tasks():
    """List all sensitivity analysis tasks."""
    if state.sensitivity_analyzer is None:
        return []
    tasks = state.sensitivity_analyzer.list_tasks()
    return [
        {
            "task_id": t.task_id,
            "param_key": t.param_key,
            "slug": t.slug,
            "strategy": t.strategy,
            "steps": t.steps,
            "status": t.status,
            "created_at": t.created_at,
            "elapsed_seconds": t.elapsed_seconds,
        }
        for t in tasks
    ]


@router.get("/{task_id}")
async def get_sensitivity_task(task_id: str):
    """Get full sensitivity analysis result."""
    if state.sensitivity_analyzer is None:
        raise HTTPException(500, "Sensitivity analyzer not initialized")
    result = state.sensitivity_analyzer.get_task(task_id)
    if not result:
        raise HTTPException(404, f"Task {task_id} not found")
    return asdict(result)
