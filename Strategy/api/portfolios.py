"""Portfolio CRUD routes — user-curated collections of backtest result data sources.

Supports a parent-child tree (max 3 levels).
* **Leaf portfolio**: holds ``items`` (backtest sessions), ``children`` is empty.
* **Container portfolio**: holds ``children`` (other portfolio IDs), ``items`` is always empty.

Strategy-group status is derived at query time:
  A portfolio is a strategy group only when it is a **leaf** (not a container)
  AND all its items share the same strategy + config.
"""

from __future__ import annotations

import re
import unicodedata
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

import api.state as state

router = APIRouter(prefix="/portfolios")

MAX_TREE_DEPTH = 3


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
    btc_momentum: float = 0.0
    config: dict = Field(default_factory=dict)


class CreatePortfolioBody(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    items: list[PortfolioItemBody] = []


class CreateContainerBody(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    children: list[str] = []


class AddItemsBody(BaseModel):
    items: list[PortfolioItemBody]


class RemoveItemsBody(BaseModel):
    session_ids: list[str]


class AddChildrenBody(BaseModel):
    children: list[str] = Field(..., min_length=1)


class RemoveChildrenBody(BaseModel):
    children: list[str] = Field(..., min_length=1)


class RenameBody(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)


# ── Helpers ──────────────────────────────────────────────────────────────────

_MULTI_WS = re.compile(r"\s+")


def _norm_strategy(name: str) -> str:
    """Normalize strategy name for comparison: NFC + strip + collapse whitespace."""
    return _MULTI_WS.sub(" ", unicodedata.normalize("NFC", name).strip())


def _store():
    if state.portfolio_store is None:
        raise HTTPException(503, "Portfolio store not initialised")
    return state.portfolio_store


def _enrich_portfolio(p: dict) -> dict:
    """Derive strategy-group / container flags at query time."""
    children = p.get("children", [])
    is_container = len(children) > 0

    p.setdefault("parent_id", None)
    p.setdefault("children", [])
    p["is_container"] = is_container

    # Containers are never strategy groups
    items = p.get("items", [])
    if is_container or not items:
        p["is_strategy_group"] = False
        p["group_strategy"] = None
        p["group_config"] = None
        return p

    first_strategy = items[0].get("strategy", "")
    first_config = items[0].get("config", {})
    norm_first = _norm_strategy(first_strategy)

    is_group = all(
        _norm_strategy(it.get("strategy", "")) == norm_first
        and it.get("config", {}) == first_config
        for it in items
    )
    p["is_strategy_group"] = is_group
    p["group_strategy"] = first_strategy if is_group else None
    p["group_config"] = first_config if is_group else None
    return p


def _validate_add_children(store, parent_id: str, child_ids: list[str]) -> None:
    """Raise HTTPException if adding *child_ids* to *parent_id* violates tree rules."""
    parent = store.get(parent_id)
    if parent is None:
        raise HTTPException(404, "Parent portfolio not found")

    # Parent must be a container (children list present, items empty)
    if parent.get("items"):
        raise HTTPException(
            400, "Leaf portfolio with items cannot have children. "
                 "Create a container portfolio instead.",
        )

    for cid in child_ids:
        if cid == parent_id:
            raise HTTPException(400, f"Cannot add portfolio as its own child")
        child = store.get(cid)
        if child is None:
            raise HTTPException(404, f"Child portfolio {cid} not found")
        # Already has a different parent?
        existing_parent = child.get("parent_id")
        if existing_parent and existing_parent != parent_id:
            raise HTTPException(
                400,
                f"Portfolio {cid} already belongs to another parent ({existing_parent}). "
                "Remove it from the current parent first.",
            )

    # Cycle detection: parent (or any ancestor) must not appear in any child's descendant tree
    ancestors = store.get_ancestors(parent_id) | {parent_id}
    for cid in child_ids:
        descendants = store.get_all_descendants(cid) | {cid}
        overlap = ancestors & descendants
        if overlap:
            raise HTTPException(
                400,
                f"Adding {cid} would create a cycle (overlap: {overlap})",
            )

    # Depth check: parent_depth + max_child_subtree_depth must not exceed MAX_TREE_DEPTH
    parent_depth = store.get_depth(parent_id)
    for cid in child_ids:
        child_subtree = _subtree_depth(store, cid)
        if parent_depth + child_subtree > MAX_TREE_DEPTH:
            raise HTTPException(
                400,
                f"Adding {cid} would exceed max tree depth ({MAX_TREE_DEPTH}). "
                f"Parent is at depth {parent_depth}, child subtree is {child_subtree} deep.",
            )


def _subtree_depth(store, portfolio_id: str) -> int:
    """Return the height of the subtree rooted at *portfolio_id* (self = 1)."""
    p = store.get(portfolio_id)
    if p is None:
        return 1
    children = p.get("children", [])
    if not children:
        return 1
    return 1 + max(_subtree_depth(store, cid) for cid in children)


# ── Routes ───────────────────────────────────────────────────────────────────

@router.get("")
async def list_portfolios():
    return [_enrich_portfolio(p) for p in _store().values()]


@router.get("/strategy-groups")
async def list_strategy_groups():
    """Flat list of all strategy groups regardless of nesting level."""
    all_portfolios = [_enrich_portfolio(p) for p in _store().values()]
    return [p for p in all_portfolios if p.get("is_strategy_group")]


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
        "parent_id": None,
        "children": [],
        "items": [it.model_dump(mode="json") for it in body.items],
    }
    store.put(portfolio_id, portfolio)
    return _enrich_portfolio(portfolio)


@router.post("/container", status_code=201)
async def create_container(body: CreateContainerBody):
    """Create a pure-container portfolio (no items, only children)."""
    store = _store()
    portfolio_id = uuid.uuid4().hex[:12]
    now = datetime.now(timezone.utc).isoformat()
    portfolio = {
        "portfolio_id": portfolio_id,
        "name": body.name,
        "created_at": now,
        "updated_at": now,
        "parent_id": None,
        "children": [],
        "items": [],
    }
    store.put(portfolio_id, portfolio)

    # Optionally attach initial children
    if body.children:
        _validate_add_children(store, portfolio_id, body.children)
        store.add_children(portfolio_id, body.children)
        portfolio = store.get(portfolio_id)

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
    p = store.get(portfolio_id)
    if p is None:
        raise HTTPException(404, "Portfolio not found")
    if p.get("children"):
        raise HTTPException(400, "Cannot add items to a container portfolio")
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


@router.put("/{portfolio_id}/children")
async def add_children(portfolio_id: str, body: AddChildrenBody):
    store = _store()
    _validate_add_children(store, portfolio_id, body.children)
    result = store.add_children(portfolio_id, body.children)
    if result is None:
        raise HTTPException(404, "Portfolio not found")
    return _enrich_portfolio(result)


@router.delete("/{portfolio_id}/children")
async def remove_children(portfolio_id: str, body: RemoveChildrenBody):
    store = _store()
    result = store.remove_children(portfolio_id, body.children)
    if result is None:
        raise HTTPException(404, "Portfolio not found")
    return _enrich_portfolio(result)


@router.delete("/{portfolio_id}")
async def delete_portfolio(portfolio_id: str):
    store = _store()
    p = store.get(portfolio_id)
    if p is None:
        raise HTTPException(404, "Portfolio not found")

    # Orphan children — promote to top-level
    children = p.get("children", [])
    if children:
        store.remove_children(portfolio_id, children)

    # Remove self from parent's children list
    parent_id = p.get("parent_id")
    if parent_id:
        parent = store.get(parent_id)
        if parent:
            store.remove_children(parent_id, [portfolio_id])

    if not store.delete(portfolio_id):
        raise HTTPException(404, "Portfolio not found")
    return {"deleted": portfolio_id}
