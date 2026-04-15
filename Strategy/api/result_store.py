"""Persistent stores — JSON files on disk for backtest results and batch summaries.

All stores use **lazy loading**: on startup only file names are scanned to
build an index (O(1) memory per entry).  Full JSON is read from disk on
demand via ``get()``.  Recently-accessed items are kept in an LRU cache so
hot-path reads (e.g. detail page) stay fast.

``values()`` returns lightweight metadata extracted from file names or a
quick first-line peek, NOT the full payload.
"""

from __future__ import annotations

import json
import math
import logging
import os
import time
from collections import OrderedDict
from pathlib import Path

logger = logging.getLogger(__name__)

# Default LRU cache size — number of full objects kept in memory.
_DEFAULT_CACHE_SIZE = 64


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


def _read_json(path: Path) -> dict | None:
    """Read and parse a JSON file, returning None on any error."""
    try:
        raw = path.read_text("utf-8")
        return json.loads(raw)
    except Exception as e:
        logger.warning("Failed to read %s: %s", path.name, e)
        return None


# ── Result summary keys (extracted at scan time for list endpoints) ──────────
_RESULT_SUMMARY_KEYS = (
    "session_id", "strategy", "slug", "initial_balance", "final_equity",
    "status", "created_at", "duration_seconds", "metrics",
)


class ResultStore:
    """Lazy-loading on-disk store for individual backtest results.

    ``load()`` only scans file names and extracts lightweight summaries.
    ``get(id)`` reads the full JSON from disk (cached via LRU).
    ``values()`` returns pre-extracted summaries — NOT full payloads.
    """

    def __init__(self, results_dir: Path, cache_size: int = _DEFAULT_CACHE_SIZE) -> None:
        self._dir = results_dir
        self._dir.mkdir(parents=True, exist_ok=True)
        # id → lightweight summary (always in memory)
        self._index: dict[str, dict] = {}
        # id → full payload LRU cache
        self._cache: OrderedDict[str, dict] = OrderedDict()
        self._cache_size = cache_size

    # ── Lifecycle ────────────────────────────────────────────────────────────

    def load(self) -> int:
        """Scan persisted results and build lightweight index. Returns count."""
        t0 = time.monotonic()
        files = list(self._dir.glob("*.json"))
        total_bytes = 0
        count = 0
        errors = 0
        for f in files:
            try:
                fsize = f.stat().st_size
                total_bytes += fsize
                raw = f.read_text("utf-8")
                data = json.loads(raw)
                sid = data.get("session_id")
                if sid:
                    # Keep only summary fields in index
                    self._index[sid] = {
                        k: data[k] for k in _RESULT_SUMMARY_KEYS if k in data
                    }
                    count += 1
            except Exception as e:
                errors += 1
                logger.warning("Failed to index result %s: %s", f.name, e)
        dt_ms = (time.monotonic() - t0) * 1000
        logger.info(
            "ResultStore: scanned %d files (%.1f MB) in %.0f ms — "
            "indexed %d results, %d errors",
            len(files), total_bytes / (1024 * 1024), dt_ms, count, errors,
        )
        return count

    # ── LRU cache helpers ────────────────────────────────────────────────────

    def _cache_put(self, key: str, value: dict) -> None:
        if key in self._cache:
            self._cache.move_to_end(key)
        else:
            self._cache[key] = value
            while len(self._cache) > self._cache_size:
                self._cache.popitem(last=False)

    # ── CRUD ─────────────────────────────────────────────────────────────────

    def put(self, session_id: str, result: dict) -> None:
        """Store summary in index, full payload in cache, and persist to disk."""
        result = sanitize_floats(result)
        self._index[session_id] = {
            k: result[k] for k in _RESULT_SUMMARY_KEYS if k in result
        }
        self._cache_put(session_id, result)
        try:
            path = self._dir / f"{session_id}.json"
            path.write_text(
                json.dumps(result, ensure_ascii=False, default=str),
                encoding="utf-8",
            )
        except Exception as e:
            logger.error("Failed to persist result %s: %s", session_id, e)

    def get(self, session_id: str) -> dict | None:
        """Get full result — from cache or disk."""
        if session_id not in self._index:
            return None
        # Cache hit
        if session_id in self._cache:
            self._cache.move_to_end(session_id)
            return self._cache[session_id]
        # Disk read
        path = self._dir / f"{session_id}.json"
        data = _read_json(path)
        if data is not None:
            self._cache_put(session_id, data)
        return data

    def values(self) -> list[dict]:
        """Return lightweight summaries (NOT full payloads)."""
        return list(self._index.values())

    def __contains__(self, session_id: str) -> bool:
        return session_id in self._index

    def __len__(self) -> int:
        return len(self._index)

    def delete(self, session_id: str) -> bool:
        if session_id not in self._index:
            return False
        del self._index[session_id]
        self._cache.pop(session_id, None)
        path = self._dir / f"{session_id}.json"
        path.unlink(missing_ok=True)
        return True

    def clear(self) -> int:
        count = len(self._index)
        self._index.clear()
        self._cache.clear()
        for f in self._dir.glob("*.json"):
            f.unlink(missing_ok=True)
        return count


# ── Batch summary keys (extracted at scan time for list endpoints) ───────────
_BATCH_SUMMARY_KEYS = (
    "batch_id", "strategy", "status", "total", "completed",
    "created_at", "started_at", "finished_at", "slugs", "config",
)


class BatchStore:
    """Lazy-loading on-disk store for batch task summaries.

    ``load()`` scans and extracts only listing-level fields.
    ``get(id)`` reads the full JSON from disk (cached via LRU).
    ``values()`` returns pre-extracted summaries.
    """

    def __init__(self, batches_dir: Path, cache_size: int = _DEFAULT_CACHE_SIZE) -> None:
        self._dir = batches_dir
        self._dir.mkdir(parents=True, exist_ok=True)
        self._index: dict[str, dict] = {}
        self._cache: OrderedDict[str, dict] = OrderedDict()
        self._cache_size = cache_size

    def load(self) -> int:
        t0 = time.monotonic()
        files = list(self._dir.glob("*.json"))
        total_bytes = 0
        count = 0
        errors = 0
        for f in files:
            try:
                fsize = f.stat().st_size
                total_bytes += fsize
                raw = f.read_text("utf-8")
                data = json.loads(raw)
                bid = data.get("batch_id")
                if bid:
                    summary = {k: data[k] for k in _BATCH_SUMMARY_KEYS if k in data}
                    # Keep lightweight counts instead of full results/workflows
                    summary["results_count"] = len(data.get("results", {}))
                    summary["errors_count"] = len(data.get("errors", {}))
                    self._index[bid] = summary
                    count += 1
            except Exception as e:
                errors += 1
                logger.warning("Failed to index batch %s: %s", f.name, e)
        dt_ms = (time.monotonic() - t0) * 1000
        logger.info(
            "BatchStore: scanned %d files (%.1f MB) in %.0f ms — "
            "indexed %d batches, %d errors",
            len(files), total_bytes / (1024 * 1024), dt_ms, count, errors,
        )
        return count

    def _cache_put(self, key: str, value: dict) -> None:
        if key in self._cache:
            self._cache.move_to_end(key)
        else:
            self._cache[key] = value
            while len(self._cache) > self._cache_size:
                self._cache.popitem(last=False)

    def put(self, batch_id: str, batch_data: dict) -> None:
        summary = {k: batch_data[k] for k in _BATCH_SUMMARY_KEYS if k in batch_data}
        summary["results_count"] = len(batch_data.get("results", {}))
        summary["errors_count"] = len(batch_data.get("errors", {}))
        self._index[batch_id] = summary
        self._cache_put(batch_id, batch_data)
        try:
            path = self._dir / f"{batch_id}.json"
            path.write_text(
                json.dumps(batch_data, ensure_ascii=False, default=str),
                encoding="utf-8",
            )
        except Exception as e:
            logger.error("Failed to persist batch %s: %s", batch_id, e)

    def get(self, batch_id: str) -> dict | None:
        """Get full batch data — from cache or disk."""
        if batch_id not in self._index:
            return None
        if batch_id in self._cache:
            self._cache.move_to_end(batch_id)
            return self._cache[batch_id]
        path = self._dir / f"{batch_id}.json"
        data = _read_json(path)
        if data is not None:
            self._cache_put(batch_id, data)
        return data

    def values(self) -> list[dict]:
        """Return lightweight summaries (NOT full payloads)."""
        return list(self._index.values())

    def delete(self, batch_id: str) -> bool:
        if batch_id not in self._index:
            return False
        del self._index[batch_id]
        self._cache.pop(batch_id, None)
        path = self._dir / f"{batch_id}.json"
        path.unlink(missing_ok=True)
        return True

    def clear(self) -> int:
        count = len(self._index)
        self._index.clear()
        self._cache.clear()
        for f in self._dir.glob("*.json"):
            f.unlink(missing_ok=True)
        return count

    def __contains__(self, batch_id: str) -> bool:
        return batch_id in self._index

    def __len__(self) -> int:
        return len(self._index)


class PortfolioStore:
    """Persists data-source portfolios (user-curated result collections) to disk.

    Each portfolio is ``{portfolio_id}.json`` inside *portfolios_dir*.
    """

    def __init__(self, portfolios_dir: Path) -> None:
        self._dir = portfolios_dir
        self._dir.mkdir(parents=True, exist_ok=True)
        self._data: dict[str, dict] = {}

    def load(self) -> int:
        t0 = time.monotonic()
        files = list(self._dir.glob("*.json"))
        total_bytes = 0
        count = 0
        for f in files:
            try:
                total_bytes += f.stat().st_size
                raw = f.read_text("utf-8")
                data = json.loads(raw)
                pid = data.get("portfolio_id")
                if pid:
                    self._data[pid] = data
                    count += 1
            except Exception as e:
                logger.warning("Failed to load portfolio %s: %s", f.name, e)
        if count:
            dt_ms = (time.monotonic() - t0) * 1000
            logger.info(
                "PortfolioStore: loaded %d portfolios (%.1f KB) in %.0f ms",
                count, total_bytes / 1024, dt_ms,
            )
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
