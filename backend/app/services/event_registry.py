"""BTC Event Registry — in-memory sliding window backed by Redis.

Maintains per-duration deques of BTC up/down events so that all callers
(discovery, status-check, auto-recorder, watch, next-event) read from a
shared cache instead of hitting the Gamma API individually.

Refresh strategy (threshold-driven, not timer):
  * Startup: full load — 前4后6 per duration.
  * When upcoming events ≤ 2: async-expand 6 new slugs to the right.
  * Background heartbeat every 30 s as safety-net.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
from collections import deque
from datetime import datetime, timezone

import httpx

from app.config import settings
from app.services.log_buffer import metrics
from app.storage import redis_store

logger = logging.getLogger(__name__)

# ── BTC constants ────────────────────────────────────────────────────────────

BTC_OUTCOMES: list[str] = ["Up", "Down"]

# duration_key → (slug_prefix, interval_seconds, slots_before, slots_after)
BTC_DURATIONS: dict[str, tuple[str, int, int, int]] = {
    "5m":  ("btc-updown-5m",  300,  4, 6),
    "15m": ("btc-updown-15m", 900,  2, 4),
    "30m": ("btc-updown-30m", 1800, 1, 3),
}

# Threshold: when upcoming count drops to this value, trigger refresh
_UPCOMING_THRESHOLD = 2

_BTC_SLUG_RE = re.compile(r"^(btc-updown-\d+m)-(\d{10})$")

# ── HTTP client (shared with polymarket_proxy) ───────────────────────────────

_client: httpx.AsyncClient | None = None


def _get_client() -> httpx.AsyncClient:
    global _client
    if _client is None or _client.is_closed:
        _client = httpx.AsyncClient(timeout=15.0)
    return _client


# ── Helpers ──────────────────────────────────────────────────────────────────

_JSON_STR_FIELDS = ("outcomes", "outcomePrices", "clobTokenIds")


def _parse_json_str(value: str) -> list:
    if isinstance(value, list):
        return value
    if isinstance(value, str) and value.startswith("["):
        try:
            return json.loads(value)
        except (json.JSONDecodeError, ValueError):
            pass
    return []


def _normalize_market(m: dict) -> dict:
    for field in _JSON_STR_FIELDS:
        if field in m:
            m[field] = _parse_json_str(m[field])
    return m


def _normalize_event(e: dict) -> dict:
    for m in e.get("markets", []):
        _normalize_market(m)
    return e


def _extract_epoch(slug: str) -> int:
    """Extract trailing 10-digit unix timestamp from a slug."""
    m = _BTC_SLUG_RE.match(slug)
    if m:
        return int(m.group(2))
    try:
        return int(slug.rsplit("-", 1)[-1])
    except (ValueError, IndexError):
        return 0


def _compute_status(event: dict, now_utc: datetime) -> str:
    """Return 'ended' | 'live' | 'upcoming' | 'unknown'."""
    end_str = event.get("endDate", "") or event.get("end_date", "")
    markets = event.get("markets", [])
    m0 = markets[0] if markets else {}
    start_str = m0.get("eventStartTime", m0.get("startDate", "")) or ""
    if not start_str:
        start_str = event.get("startDate", "") or event.get("start_date", "")

    if end_str:
        try:
            end_dt = datetime.fromisoformat(end_str.replace("Z", "+00:00"))
            start_dt = (
                datetime.fromisoformat(start_str.replace("Z", "+00:00"))
                if start_str
                else end_dt
            )
            if end_dt <= now_utc:
                return "ended"
            if start_dt <= now_utc:
                return "live"
            return "upcoming"
        except (ValueError, TypeError):
            pass
    if event.get("closed"):
        return "ended"
    if event.get("active"):
        return "live"
    return "unknown"


def _status_ttl(status: str) -> int:
    """Return Redis TTL for an event based on its status.

    ended  → 0 (no expiry, immutable)
    live   → 60 s
    upcoming / unknown → 120 s
    """
    if status == "ended":
        return 0
    if status == "live":
        return 60
    return 120


# ── Slim event builder ──────────────────────────────────────────────────────

def _slim_event(event: dict) -> dict:
    """Strip price-related transient fields; inject BTC_OUTCOMES constant."""
    slim = {
        k: v for k, v in event.items()
        if k not in ("outcomePrices",)
    }
    # Ensure outcomes constant on each market
    for m in slim.get("markets", []):
        m["outcomes"] = BTC_OUTCOMES
        m.pop("outcomePrices", None)
    return slim


# ── Entry type stored in deque ───────────────────────────────────────────────

class _Entry:
    __slots__ = ("slug", "event", "status")

    def __init__(self, slug: str, event: dict, status: str) -> None:
        self.slug = slug
        self.event = event
        self.status = status


# ── EventRegistry ────────────────────────────────────────────────────────────

class EventRegistry:
    """Singleton sliding-window registry for BTC series events."""

    def __init__(self) -> None:
        # duration_key → deque[_Entry] ordered by epoch ascending
        self._windows: dict[str, deque[_Entry]] = {}
        # slug → _Entry for O(1) lookup
        self._index: dict[str, _Entry] = {}
        self._refresh_locks: dict[str, asyncio.Lock] = {}
        self._heartbeat_task: asyncio.Task | None = None
        self._stop = asyncio.Event()

    # ── Lifecycle ────────────────────────────────────────────

    async def start(self) -> None:
        """Warm up all duration windows and start the heartbeat."""
        self._stop.clear()
        for dur_key in BTC_DURATIONS:
            self._windows[dur_key] = deque()
            self._refresh_locks[dur_key] = asyncio.Lock()

        # Try Redis recovery first, then full load
        for dur_key in BTC_DURATIONS:
            restored = await self._restore_from_redis(dur_key)
            if not restored:
                await self._full_load(dur_key)

        total = sum(len(d) for d in self._windows.values())
        logger.info("EventRegistry started — %d events across %d durations",
                     total, len(self._windows))

        self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())

    async def stop(self) -> None:
        self._stop.set()
        if self._heartbeat_task:
            self._heartbeat_task.cancel()
            try:
                await self._heartbeat_task
            except asyncio.CancelledError:
                pass
        logger.info("EventRegistry stopped")

    # ── Public query API ─────────────────────────────────────

    def get_event(self, slug: str) -> dict | None:
        """Look up event by slug from in-memory index (O(1))."""
        entry = self._index.get(slug)
        return entry.event if entry else None

    async def get_event_async(self, slug: str) -> dict | None:
        """Look up event — memory → Redis → Gamma API fallback."""
        entry = self._index.get(slug)
        if entry:
            return entry.event

        # Redis fallback
        cached = await redis_store.registry_get_event(slug)
        if cached:
            return cached

        # Gamma API fallback — fetch and backfill
        event = await self._fetch_slug(slug)
        if event:
            now_utc = datetime.now(timezone.utc)
            status = _compute_status(event, now_utc)
            slim = _slim_event(event)
            await redis_store.registry_set_event(
                slug, json.dumps(slim), _status_ttl(status),
            )
        return event

    def get_window(self, duration: str) -> list[dict]:
        """Return all events for a duration with fresh _status."""
        dq = self._windows.get(duration)
        if not dq:
            return []
        now_utc = datetime.now(timezone.utc)
        result: list[dict] = []
        for entry in dq:
            e = dict(entry.event)
            e["_status"] = _compute_status(entry.event, now_utc)
            result.append(e)
        return result

    def get_all_windows(self) -> dict[str, list[dict]]:
        """Return all duration windows — drop-in replacement for discover_btc_markets()."""
        self._maybe_trigger_refresh()
        return {dur: self.get_window(dur) for dur in BTC_DURATIONS}

    def get_current_or_next(self, prefix: str, interval: int) -> dict | None:
        """Find the current LIVE or first upcoming event matching prefix+interval."""
        dur_key = f"{interval // 60}m"
        dq = self._windows.get(dur_key)
        if not dq:
            return None
        now_utc = datetime.now(timezone.utc)
        for entry in dq:
            if not entry.slug.startswith(prefix):
                continue
            status = _compute_status(entry.event, now_utc)
            if status in ("live", "upcoming"):
                secs = self._seconds_remaining(entry.event, status, now_utc)
                return {
                    "slug": entry.slug,
                    "event": entry.event,
                    "status": status,
                    "seconds_remaining": secs,
                }
        return None

    def get_next_event(self, current_slug: str) -> dict | None:
        """Find the next live/upcoming event after current_slug in the same series."""
        m = _BTC_SLUG_RE.match(current_slug)
        if not m:
            return None
        prefix = m.group(1)
        curr_ts = int(m.group(2))
        interval = self._interval_from_prefix(prefix)
        dur_key = f"{interval // 60}m"
        dq = self._windows.get(dur_key)
        if not dq:
            return None
        now_utc = datetime.now(timezone.utc)
        for entry in dq:
            entry_ts = _extract_epoch(entry.slug)
            if entry_ts <= curr_ts:
                continue
            status = _compute_status(entry.event, now_utc)
            if status in ("live", "upcoming"):
                return {
                    "slug": entry.slug,
                    "event": entry.event,
                    "status": status,
                }
        return None

    # ── Refresh logic ────────────────────────────────────────

    def _maybe_trigger_refresh(self) -> None:
        """Check all durations and fire async refresh if upcoming ≤ threshold."""
        now_utc = datetime.now(timezone.utc)
        for dur_key, dq in self._windows.items():
            upcoming_count = sum(
                1 for e in dq if _compute_status(e.event, now_utc) == "upcoming"
            )
            if upcoming_count <= _UPCOMING_THRESHOLD:
                asyncio.create_task(self._safe_refresh(dur_key))

    async def _safe_refresh(self, dur_key: str) -> None:
        """Refresh with lock to prevent concurrent runs."""
        lock = self._refresh_locks.get(dur_key)
        if not lock:
            return
        if lock.locked():
            return  # another refresh in progress
        async with lock:
            await self._expand_right(dur_key)
            self._trim_left(dur_key)
            await self._persist_window(dur_key)

    async def _expand_right(self, dur_key: str) -> None:
        """Fetch up to 6 new slugs to the right of the window."""
        cfg = BTC_DURATIONS.get(dur_key)
        if not cfg:
            return
        prefix, interval, _, _ = cfg
        dq = self._windows[dur_key]

        if dq:
            rightmost_ts = _extract_epoch(dq[-1].slug)
        else:
            now_ts = int(datetime.now(timezone.utc).timestamp())
            rightmost_ts = now_ts - (now_ts % interval) - interval

        existing_slugs = {e.slug for e in dq}
        now_utc = datetime.now(timezone.utc)
        loaded = 0

        for i in range(1, 7):
            slug = f"{prefix}-{rightmost_ts + i * interval}"
            if slug in existing_slugs:
                continue
            event = await self._fetch_slug(slug)
            if not event:
                continue
            status = _compute_status(event, now_utc)
            slim = _slim_event(event)
            entry = _Entry(slug, slim, status)
            dq.append(entry)
            self._index[slug] = entry
            await redis_store.registry_set_event(
                slug, json.dumps(slim), _status_ttl(status),
            )
            loaded += 1

        if loaded:
            logger.info("Registry[%s]: expanded right +%d events", dur_key, loaded)

    def _trim_left(self, dur_key: str) -> None:
        """Remove ended events from the left, keeping at most `before` historical entries."""
        cfg = BTC_DURATIONS.get(dur_key)
        if not cfg:
            return
        _, _, before, _ = cfg
        dq = self._windows[dur_key]
        now_utc = datetime.now(timezone.utc)

        # Count ended events on the left
        ended_count = 0
        for entry in dq:
            if _compute_status(entry.event, now_utc) == "ended":
                ended_count += 1
            else:
                break  # sorted by time, so first non-ended means rest are live/upcoming

        while ended_count > before and dq:
            removed = dq.popleft()
            self._index.pop(removed.slug, None)
            ended_count -= 1

    async def _persist_window(self, dur_key: str) -> None:
        """Write ordered slug list to Redis for recovery on restart."""
        dq = self._windows.get(dur_key, deque())
        slugs = [e.slug for e in dq]
        await redis_store.registry_set_window(dur_key, slugs)

    # ── Initial load ─────────────────────────────────────────

    async def _restore_from_redis(self, dur_key: str) -> bool:
        """Try to rebuild window from Redis. Returns True if successful."""
        slugs = await redis_store.registry_get_window(dur_key)
        if not slugs:
            return False

        dq = self._windows[dur_key]
        now_utc = datetime.now(timezone.utc)
        restored = 0

        for slug in slugs:
            cached = await redis_store.registry_get_event(slug)
            if not cached:
                continue
            status = _compute_status(cached, now_utc)
            entry = _Entry(slug, cached, status)
            dq.append(entry)
            self._index[slug] = entry
            restored += 1

        if restored == 0:
            return False

        logger.info("Registry[%s]: restored %d events from Redis", dur_key, restored)

        # Check if window is still current (rightmost event shouldn't be too stale)
        rightmost_ts = _extract_epoch(dq[-1].slug)
        aligned_now = int(datetime.now(timezone.utc).timestamp())
        cfg = BTC_DURATIONS[dur_key]
        interval = cfg[1]
        # If the rightmost slug is more than 2 intervals behind "now", do a full reload
        if rightmost_ts < aligned_now - 2 * interval:
            logger.info("Registry[%s]: Redis window too stale, will full-reload", dur_key)
            dq.clear()
            for slug in slugs:
                self._index.pop(slug, None)
            return False

        return True

    async def _full_load(self, dur_key: str) -> None:
        """Load the initial window (前before后after) from Gamma API."""
        cfg = BTC_DURATIONS[dur_key]
        prefix, interval, before, after = cfg
        dq = self._windows[dur_key]
        now_ts = int(datetime.now(timezone.utc).timestamp())
        window_start = now_ts - (now_ts % interval)
        now_utc = datetime.now(timezone.utc)

        for offset in range(-before, after + 1):
            slug = f"{prefix}-{window_start + offset * interval}"
            event = await self._fetch_slug(slug)
            if not event:
                continue
            status = _compute_status(event, now_utc)
            slim = _slim_event(event)
            entry = _Entry(slug, slim, status)
            dq.append(entry)
            self._index[slug] = entry
            await redis_store.registry_set_event(
                slug, json.dumps(slim), _status_ttl(status),
            )

        await self._persist_window(dur_key)
        logger.info("Registry[%s]: full-loaded %d events", dur_key, len(dq))

    # ── Gamma API fetch ──────────────────────────────────────

    async def _fetch_slug(self, slug: str) -> dict | None:
        """Fetch a single event by slug from Gamma API."""
        url = f"{settings.gamma_api_url}/events"
        try:
            resp = await _get_client().get(url, params={"limit": 1, "slug": slug})
            if resp.status_code != 200:
                return None
            data = resp.json()
            if not data:
                return None
            metrics.inc("proxy.api_calls")
            return _normalize_event(data[0])
        except Exception as e:
            logger.warning("Registry: failed to fetch slug %s: %s", slug, e)
            return None

    # ── Heartbeat ────────────────────────────────────────────

    async def _heartbeat_loop(self) -> None:
        """Background safety-net: check & refresh every 30s."""
        while not self._stop.is_set():
            for _ in range(30):
                if self._stop.is_set():
                    return
                await asyncio.sleep(1)
            try:
                now_utc = datetime.now(timezone.utc)
                # Recompute statuses for all entries
                for dq in self._windows.values():
                    for entry in dq:
                        entry.status = _compute_status(entry.event, now_utc)
                # Check thresholds
                self._maybe_trigger_refresh()
            except Exception as e:
                logger.warning("Registry heartbeat error: %s", e)

    # ── Utilities ────────────────────────────────────────────

    @staticmethod
    def _interval_from_prefix(prefix: str) -> int:
        if "5m" in prefix:
            return 300
        if "15m" in prefix:
            return 900
        if "30m" in prefix:
            return 1800
        return 300

    @staticmethod
    def _seconds_remaining(event: dict, status: str, now_utc: datetime) -> float | None:
        end_str = event.get("endDate", "") or event.get("end_date", "")
        markets = event.get("markets", [])
        m0 = markets[0] if markets else {}
        start_str = m0.get("eventStartTime", m0.get("startDate", "")) or ""
        if not start_str:
            start_str = event.get("startDate", "") or event.get("start_date", "")
        try:
            if status == "live" and end_str:
                end_dt = datetime.fromisoformat(end_str.replace("Z", "+00:00"))
                return round((end_dt - now_utc).total_seconds(), 1)
            if status == "upcoming" and start_str:
                start_dt = datetime.fromisoformat(start_str.replace("Z", "+00:00"))
                return round((start_dt - now_utc).total_seconds(), 1)
        except (ValueError, TypeError):
            pass
        return None


# ── Module-level singleton ───────────────────────────────────────────────────

_instance: EventRegistry | None = None


def get_registry() -> EventRegistry:
    """Return the global EventRegistry instance."""
    assert _instance is not None, "EventRegistry not started — call start_event_registry() first"
    return _instance


async def start_event_registry() -> EventRegistry:
    global _instance
    _instance = EventRegistry()
    await _instance.start()
    return _instance


async def stop_event_registry() -> None:
    global _instance
    if _instance:
        await _instance.stop()
        _instance = None
