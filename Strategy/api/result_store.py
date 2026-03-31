"""Persistent stores — JSON files on disk for backtest results and batch summaries."""

from __future__ import annotations

import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


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

    def __contains__(self, batch_id: str) -> bool:
        return batch_id in self._data
