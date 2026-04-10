"""Persistent stores — JSON files on disk for backtest results and batch summaries."""

from __future__ import annotations

import json
import math
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def sanitize_floats(obj):
    """Recursively replace inf/nan floats with JSON-safe values."""
    if isinstance(obj, float):
        if math.isnan(obj):
            return None
        if math.isinf(obj):
            return 9999.0 if obj > 0 else -9999.0
        return obj
    if isinstance(obj, dict):
        return {k: sanitize_floats(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [sanitize_floats(v) for v in obj]
    return obj


class ResultStore:
    """In-memory + on-disk store for individual backtest results.

    Each result is persisted as ``{session_id}.json`` inside *results_dir*.
    On startup, ``load()`` reads them back so data survives restarts.
    """

    def __init__(self, results_dir: Path) -> None:
        self._dir = results_dir
        self._dir.mkdir(parents=True, exist_ok=True)
        self._data: dict[str, dict] = {}

    # ── Lifecycle ────────────────────────────────────────────────────────────

    def load(self) -> int:
        """Load all persisted results from disk. Returns count loaded."""
        count = 0
        for f in self._dir.glob("*.json"):
            try:
                raw = f.read_text("utf-8")
                data = json.loads(raw)
                sid = data.get("session_id")
                if sid:
                    self._data[sid] = data
                    count += 1
            except Exception as e:
                logger.warning("Failed to load result %s: %s", f.name, e)
        if count:
            logger.info("Loaded %d persisted results from %s", count, self._dir)
        return count

    # ── CRUD ─────────────────────────────────────────────────────────────────

    def put(self, session_id: str, result: dict) -> None:
        """Store in memory and persist to disk."""
        result = sanitize_floats(result)
        self._data[session_id] = result
        try:
            path = self._dir / f"{session_id}.json"
            path.write_text(
                json.dumps(result, ensure_ascii=False, default=str),
                encoding="utf-8",
            )
        except Exception as e:
            logger.error("Failed to persist result %s: %s", session_id, e)

    def get(self, session_id: str) -> dict | None:
        return self._data.get(session_id)

    def values(self) -> list[dict]:
        return list(self._data.values())

    def __contains__(self, session_id: str) -> bool:
        return session_id in self._data

    def __len__(self) -> int:
        return len(self._data)

    def delete(self, session_id: str) -> bool:
        if session_id not in self._data:
            return False
        del self._data[session_id]
        path = self._dir / f"{session_id}.json"
        path.unlink(missing_ok=True)
        return True

    def clear(self) -> int:
        count = len(self._data)
        self._data.clear()
        for f in self._dir.glob("*.json"):
            f.unlink(missing_ok=True)
        return count


class BatchStore:
    """Persists batch task summaries to disk.

    Only the serialised API response is stored (results_summary + workflows),
    NOT the full BacktestSession objects (those live in ResultStore).
    """

    def __init__(self, batches_dir: Path) -> None:
        self._dir = batches_dir
        self._dir.mkdir(parents=True, exist_ok=True)
        self._data: dict[str, dict] = {}

    def load(self) -> int:
        count = 0
        for f in self._dir.glob("*.json"):
            try:
                raw = f.read_text("utf-8")
                data = json.loads(raw)
                bid = data.get("batch_id")
                if bid:
                    self._data[bid] = data
                    count += 1
            except Exception as e:
                logger.warning("Failed to load batch %s: %s", f.name, e)
        if count:
            logger.info("Loaded %d persisted batches from %s", count, self._dir)
        return count

    def put(self, batch_id: str, batch_data: dict) -> None:
        self._data[batch_id] = batch_data
        try:
            path = self._dir / f"{batch_id}.json"
            path.write_text(
                json.dumps(batch_data, ensure_ascii=False, default=str),
                encoding="utf-8",
            )
        except Exception as e:
            logger.error("Failed to persist batch %s: %s", batch_id, e)

    def get(self, batch_id: str) -> dict | None:
        return self._data.get(batch_id)

    def values(self) -> list[dict]:
        return list(self._data.values())

    def delete(self, batch_id: str) -> bool:
        if batch_id not in self._data:
            return False
        del self._data[batch_id]
        path = self._dir / f"{batch_id}.json"
        path.unlink(missing_ok=True)
        return True

    def clear(self) -> int:
        count = len(self._data)
        self._data.clear()
        for f in self._dir.glob("*.json"):
            f.unlink(missing_ok=True)
        return count

    def __contains__(self, batch_id: str) -> bool:
        return batch_id in self._data

    def __len__(self) -> int:
        return len(self._data)


class PortfolioStore:
    """Persists data-source portfolios (user-curated result collections) to disk.

    Each portfolio is ``{portfolio_id}.json`` inside *portfolios_dir*.
    """

    def __init__(self, portfolios_dir: Path) -> None:
        self._dir = portfolios_dir
        self._dir.mkdir(parents=True, exist_ok=True)
        self._data: dict[str, dict] = {}

    def load(self) -> int:
        count = 0
        for f in self._dir.glob("*.json"):
            try:
                raw = f.read_text("utf-8")
                data = json.loads(raw)
                pid = data.get("portfolio_id")
                if pid:
                    self._data[pid] = data
                    count += 1
            except Exception as e:
                logger.warning("Failed to load portfolio %s: %s", f.name, e)
        if count:
            logger.info("Loaded %d persisted portfolios from %s", count, self._dir)
        return count

    # ── CRUD ─────────────────────────────────────────────────────────────────

    def put(self, portfolio_id: str, portfolio: dict) -> None:
        portfolio = sanitize_floats(portfolio)
        self._data[portfolio_id] = portfolio
        self._persist(portfolio_id, portfolio)

    def get(self, portfolio_id: str) -> dict | None:
        return self._data.get(portfolio_id)

    def values(self) -> list[dict]:
        return list(self._data.values())

    def delete(self, portfolio_id: str) -> bool:
        if portfolio_id not in self._data:
            return False
        del self._data[portfolio_id]
        path = self._dir / f"{portfolio_id}.json"
        path.unlink(missing_ok=True)
        return True

    def __contains__(self, portfolio_id: str) -> bool:
        return portfolio_id in self._data

    def __len__(self) -> int:
        return len(self._data)

    # ── Children operations (container tree) ────────────────────────────────

    def get_depth(self, portfolio_id: str) -> int:
        """Return depth of *portfolio_id* in the tree (root = 1)."""
        depth = 1
        cur = portfolio_id
        while True:
            p = self._data.get(cur)
            if p is None:
                break
            parent = p.get("parent_id")
            if not parent:
                break
            depth += 1
            cur = parent
        return depth

    def get_all_descendants(self, portfolio_id: str) -> set[str]:
        """Return IDs of all descendants (children, grandchildren, …)."""
        result: set[str] = set()
        stack = list(self._data.get(portfolio_id, {}).get("children", []))
        while stack:
            cid = stack.pop()
            if cid in result:
                continue
            result.add(cid)
            child = self._data.get(cid)
            if child:
                stack.extend(child.get("children", []))
        return result

    def get_ancestors(self, portfolio_id: str) -> set[str]:
        """Return IDs of all ancestors (parent, grandparent, …)."""
        result: set[str] = set()
        cur = portfolio_id
        while True:
            p = self._data.get(cur)
            if p is None:
                break
            parent = p.get("parent_id")
            if not parent or parent in result:
                break
            result.add(parent)
            cur = parent
        return result

    def add_children(self, parent_id: str, child_ids: list[str]) -> dict | None:
        parent = self._data.get(parent_id)
        if parent is None:
            return None
        existing = set(parent.get("children", []))
        for cid in child_ids:
            if cid not in existing and cid in self._data:
                existing.add(cid)
                child = self._data[cid]
                child["parent_id"] = parent_id
                self._persist(cid, child)
        parent["children"] = list(existing)
        from datetime import datetime, timezone
        parent["updated_at"] = datetime.now(timezone.utc).isoformat()
        self._persist(parent_id, parent)
        return parent

    def remove_children(self, parent_id: str, child_ids: list[str]) -> dict | None:
        parent = self._data.get(parent_id)
        if parent is None:
            return None
        remove_set = set(child_ids)
        parent["children"] = [
            cid for cid in parent.get("children", []) if cid not in remove_set
        ]
        for cid in child_ids:
            child = self._data.get(cid)
            if child and child.get("parent_id") == parent_id:
                child["parent_id"] = None
                self._persist(cid, child)
        from datetime import datetime, timezone
        parent["updated_at"] = datetime.now(timezone.utc).isoformat()
        self._persist(parent_id, parent)
        return parent

    # ── Item-level operations ────────────────────────────────────────────────

    def add_items(self, portfolio_id: str, items: list[dict]) -> dict | None:
        portfolio = self._data.get(portfolio_id)
        if portfolio is None:
            return None
        existing_ids = {it["session_id"] for it in portfolio["items"]}
        for item in items:
            if item["session_id"] not in existing_ids:
                portfolio["items"].append(sanitize_floats(item))
                existing_ids.add(item["session_id"])
        from datetime import datetime, timezone
        portfolio["updated_at"] = datetime.now(timezone.utc).isoformat()
        self._persist(portfolio_id, portfolio)
        return portfolio

    def remove_items(self, portfolio_id: str, session_ids: list[str]) -> dict | None:
        portfolio = self._data.get(portfolio_id)
        if portfolio is None:
            return None
        remove_set = set(session_ids)
        portfolio["items"] = [
            it for it in portfolio["items"] if it["session_id"] not in remove_set
        ]
        from datetime import datetime, timezone
        portfolio["updated_at"] = datetime.now(timezone.utc).isoformat()
        self._persist(portfolio_id, portfolio)
        return portfolio

    # ── Internal ─────────────────────────────────────────────────────────────

    def _persist(self, portfolio_id: str, data: dict) -> None:
        try:
            path = self._dir / f"{portfolio_id}.json"
            path.write_text(
                json.dumps(data, ensure_ascii=False, default=str),
                encoding="utf-8",
            )
        except Exception as e:
            logger.error("Failed to persist portfolio %s: %s", portfolio_id, e)
