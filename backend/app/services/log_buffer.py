"""In-memory log ring buffer + lightweight metrics registry.

Provides:
- ``BufferHandler`` — a ``logging.Handler`` that captures log records into a
  fixed-size ring buffer for REST polling by the dashboard.
- ``metrics`` — a simple counter/gauge registry for key business metrics.
"""

from __future__ import annotations

import logging
import threading
import time
from collections import deque
from datetime import datetime, timezone
from typing import Any


# ── Log Ring Buffer ──────────────────────────────────────────────────────────

class BufferHandler(logging.Handler):
    """Captures log records into a thread-safe ring buffer (deque)."""

    def __init__(self, capacity: int = 2000) -> None:
        super().__init__()
        self._buffer: deque[dict] = deque(maxlen=capacity)
        self._lock = threading.Lock()

    def emit(self, record: logging.LogRecord) -> None:
        entry = self._format_record(record)
        with self._lock:
            self._buffer.append(entry)

    def get_logs(
        self,
        limit: int = 200,
        level: str | None = None,
        module: str | None = None,
    ) -> list[dict]:
        """Return recent logs, optionally filtered by level or module name."""
        with self._lock:
            items = list(self._buffer)
        if level:
            lv = level.upper()
            items = [i for i in items if i["level"] == lv]
        if module:
            items = [i for i in items if module in i["module"]]
        return items[-limit:]

    @staticmethod
    def _format_record(record: logging.LogRecord) -> dict:
        return {
            "ts": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "module": record.name,
            "message": record.getMessage(),
        }


# Module-level singleton
_handler: BufferHandler | None = None


def get_log_handler() -> BufferHandler:
    global _handler
    if _handler is None:
        _handler = BufferHandler()
    return _handler


# ── Metrics Registry ─────────────────────────────────────────────────────────

class _Metrics:
    """Dead-simple counter + gauge registry.  Thread-safe via dict atomicity.

    Usage:
        metrics.inc("ws.messages_received")
        metrics.set("ws.connected", True)
        metrics.snapshot()  →  {"counters": {...}, "gauges": {...}, "uptime": ...}
    """

    def __init__(self) -> None:
        self._counters: dict[str, int] = {}
        self._gauges: dict[str, Any] = {}
        self._start = time.monotonic()
        self._lock = threading.Lock()

    def inc(self, name: str, delta: int = 1) -> None:
        with self._lock:
            self._counters[name] = self._counters.get(name, 0) + delta

    def set(self, name: str, value: Any) -> None:
        with self._lock:
            self._gauges[name] = value

    def get(self, name: str, default: Any = 0) -> Any:
        with self._lock:
            if name in self._gauges:
                return self._gauges[name]
            return self._counters.get(name, default)

    def snapshot(self) -> dict:
        with self._lock:
            return {
                "counters": dict(self._counters),
                "gauges": dict(self._gauges),
                "uptime_seconds": round(time.monotonic() - self._start, 1),
            }


metrics = _Metrics()
