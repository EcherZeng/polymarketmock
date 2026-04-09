"""Portfolio CRUD routes — user-curated collections of backtest result data sources."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

import api.state as state

router = APIRouter(prefix="/portfolios")


# ── Request / Response models ────────────────────────────────────────────────

class PortfolioItemBody(BaseModel):
    session_id: str
    strategy: str
    slug: str
    total_return_pct: float = 0.0
    sharpe_ratio: float = 0.0
    win_rate: float = 0.0
    max_drawdown: float = 0.0
    profit_factor: float = 0.0
    total_trades: int = 0
    avg_slippage: float = 0.0
    initial_balance: float = 0.0
    final_equity: float = 0.0
    config: dict = Field(default_factory=dict)


class CreatePortfolioBody(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    items: list[PortfolioItemBody] = []


class AddItemsBody(BaseModel):
    items: list[PortfolioItemBody]


class RemoveItemsBody(BaseModel):
    session_ids: list[str]


class RenameBody(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)


# ── Helpers ──────────────────────────────────────────────────────────────────

def _store():
    if state.portfolio_store is None:
        raise HTTPException(503, "Portfolio store not initialised")
    return state.portfolio_store


def _enrich_portfolio(p: dict) -> dict:
    """Derive strategy-group fields at query time (no extra storage)."""
    items = p.get("items", [])
    if not items:
        p["is_strategy_group"] = False
        p["group_strategy"] = None
        p["group_config"] = None
        return p

    first_strategy = items[0].get("strategy", "")
    first_config = items[0].get("config", {})

    is_group = all(
        it.get("strategy") == first_strategy and it.get("config", {}) == first_config
        for it in items
    )
    p["is_strategy_group"] = is_group
    p["group_strategy"] = first_strategy if is_group else None
    p["group_config"] = first_config if is_group else None
    return p


# ── Routes ───────────────────────────────────────────────────────────────────

@router.get("")
async def list_portfolios():
    return [_enrich_portfolio(p) for p in _store().values()]


@router.get("/{portfolio_id}")
async def get_portfolio(portfolio_id: str):
    p = _store().get(portfolio_id)
    if p is None:
        raise HTTPException(404, "Portfolio not found")
    return _enrich_portfolio(p)


@router.post("", status_code=201)
async def create_portfolio(body: CreatePortfolioBody):
    store = _store()
    portfolio_id = uuid.uuid4().hex[:12]
    now = datetime.now(timezone.utc).isoformat()
    portfolio = {
        "portfolio_id": portfolio_id,
        "name": body.name,
        "created_at": now,
        "updated_at": now,
        "items": [it.model_dump(mode="json") for it in body.items],
    }
    store.put(portfolio_id, portfolio)
    return _enrich_portfolio(portfolio)


@router.put("/{portfolio_id}")
async def rename_portfolio(portfolio_id: str, body: RenameBody):
    store = _store()
    p = store.get(portfolio_id)
    if p is None:
        raise HTTPException(404, "Portfolio not found")
    p["name"] = body.name
    p["updated_at"] = datetime.now(timezone.utc).isoformat()
    store.put(portfolio_id, p)
    return _enrich_portfolio(p)


@router.put("/{portfolio_id}/items")
async def add_items(portfolio_id: str, body: AddItemsBody):
    store = _store()
    items = [it.model_dump(mode="json") for it in body.items]
    result = store.add_items(portfolio_id, items)
    if result is None:
        raise HTTPException(404, "Portfolio not found")
    return _enrich_portfolio(result)


@router.delete("/{portfolio_id}/items")
async def remove_items(portfolio_id: str, body: RemoveItemsBody):
    store = _store()
    result = store.remove_items(portfolio_id, body.session_ids)
    if result is None:
        raise HTTPException(404, "Portfolio not found")
    return _enrich_portfolio(result)


@router.delete("/{portfolio_id}")
async def delete_portfolio(portfolio_id: str):
    if not _store().delete(portfolio_id):
        raise HTTPException(404, "Portfolio not found")
    return {"deleted": portfolio_id}
