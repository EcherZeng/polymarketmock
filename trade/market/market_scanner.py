"""Market scanner — discovers upcoming BTC 15-minute sessions via Gamma API."""

from __future__ import annotations

import asyncio
import json
import logging
import re
from collections import deque
from datetime import datetime, timezone

import httpx

from config import settings
from models.types import SessionInfo, parse_slug_window

logger = logging.getLogger(__name__)

BTC_OUTCOMES: list[str] = ["Up", "Down"]

_BTC_SLUG_RE = re.compile(r"^(btc-updown-\d+m)-(\d{10})$")

_JSON_STR_FIELDS = ("outcomes", "outcomePrices", "clobTokenIds")

_client: httpx.AsyncClient | None = None


def _get_client() -> httpx.AsyncClient:
    global _client
    if _client is None or _client.is_closed:
        _client = httpx.AsyncClient(timeout=15.0)
    return _client


def _parse_json_str(value: str | list) -> list:
    if isinstance(value, list):
        return value
    if isinstance(value, str) and value.startswith("["):
        try:
            return json.loads(value)
        except (json.JSONDecodeError, ValueError):
            pass
    return []


def _normalize_event(e: dict) -> dict:
    for m in e.get("markets", []):
        for f in _JSON_STR_FIELDS:
            if f in m:
                m[f] = _parse_json_str(m[f])
    return e


def _extract_epoch(slug: str) -> int:
    m = _BTC_SLUG_RE.match(slug)
    if m:
        return int(m.group(2))
    try:
        return int(slug.rsplit("-", 1)[-1])
    except (ValueError, IndexError):
        return 0


def _compute_status(slug: str, now_utc: datetime) -> str:
    """Compute status from slug-derived timestamps (authoritative)."""
    parsed = parse_slug_window(slug)
    if not parsed:
        return "unknown"
    start_epoch, end_epoch, _ = parsed
    start_dt = datetime.fromtimestamp(start_epoch, tz=timezone.utc)
    end_dt = datetime.fromtimestamp(end_epoch, tz=timezone.utc)
    if end_dt <= now_utc:
        return "ended"
    if start_dt <= now_utc:
        return "live"
    return "upcoming"


def _event_to_session_info(slug: str, event: dict) -> SessionInfo | None:
    """Convert a Gamma API event to SessionInfo."""
    parsed = parse_slug_window(slug)
    if not parsed:
        return None
    start_epoch, end_epoch, interval_min = parsed

    markets = event.get("markets", [])
    if not markets:
        return None
    m0 = markets[0]

    token_ids = m0.get("clobTokenIds", [])
    if not token_ids or len(token_ids) < 2:
        return None

    outcomes = m0.get("outcomes", BTC_OUTCOMES)
    condition_id = m0.get("conditionId", "")
    question = m0.get("question", event.get("title", ""))

    return SessionInfo(
        slug=slug,
        token_ids=token_ids,
        outcomes=outcomes if isinstance(outcomes, list) else BTC_OUTCOMES,
        start_epoch=start_epoch,
        end_epoch=end_epoch,
        duration_s=interval_min * 60,
        condition_id=condition_id,
        question=question,
    )


class MarketScanner:
    """Scans Gamma API for BTC 15-minute sessions, maintains a sliding window."""

    def __init__(self) -> None:
        self._window: deque[tuple[str, dict]] = deque()  # (slug, event)
        self._index: dict[str, dict] = {}
        self._task: asyncio.Task | None = None
        self._stop = asyncio.Event()
        self._lock = asyncio.Lock()
        # Notify listeners when new sessions are discovered
        self._new_session_event = asyncio.Event()

    async def start(self) -> None:
        self._stop.clear()
        await self._full_load()
        self._task = asyncio.create_task(self._scan_loop())
        logger.info("MarketScanner started — %d sessions loaded", len(self._window))

    async def stop(self) -> None:
        self._stop.set()
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        global _client
        if _client and not _client.is_closed:
            await _client.aclose()
            _client = None
        logger.info("MarketScanner stopped")

    def get_current_or_next(self) -> SessionInfo | None:
        """Find the current LIVE or first upcoming session."""
        now_utc = datetime.now(timezone.utc)
        for slug, event in self._window:
            status = _compute_status(slug, now_utc)
            if status in ("live", "upcoming"):
                return _event_to_session_info(slug, event)
        return None

    def get_next_after(self, current_slug: str) -> SessionInfo | None:
        """Find the next session after the given slug."""
        curr_epoch = _extract_epoch(current_slug)
        now_utc = datetime.now(timezone.utc)
        for slug, event in self._window:
            epoch = _extract_epoch(slug)
            if epoch <= curr_epoch:
                continue
            status = _compute_status(slug, now_utc)
            if status in ("live", "upcoming"):
                return _event_to_session_info(slug, event)
        return None

    def get_session_info(self, slug: str) -> SessionInfo | None:
        """Look up a session by slug."""
        event = self._index.get(slug)
        if event:
            return _event_to_session_info(slug, event)
        return None

    # ── Internal ─────────────────────────────────────────────

    async def _full_load(self) -> None:
        """Initial load — batch fetch via tag search to minimize API calls."""
        prefix = settings.scan_slug_prefix
        interval = settings.scan_duration_s
        now_ts = int(datetime.now(timezone.utc).timestamp())
        window_start = now_ts - (now_ts % interval)

        # Try batch fetch first (single API call)
        slugs_needed = []
        for offset in range(-settings.scan_slots_before, settings.scan_slots_after + 1):
            slugs_needed.append(f"{prefix}-{window_start + offset * interval}")

        loaded = await self._batch_fetch(slugs_needed)
        if loaded:
            return

        # Fallback: individual fetches (only if batch fails)
        for slug in slugs_needed:
            event = await self._fetch_slug(slug)
            if event:
                self._window.append((slug, event))
                self._index[slug] = event

    async def _scan_loop(self) -> None:
        while not self._stop.is_set():
            for _ in range(settings.scan_interval_s):
                if self._stop.is_set():
                    return
                await asyncio.sleep(1)
            try:
                await self._refresh()
            except Exception as e:
                logger.warning("MarketScanner refresh error: %s", e)

    async def _refresh(self) -> None:
        async with self._lock:
            now_utc = datetime.now(timezone.utc)

            # Count upcoming
            upcoming = sum(
                1 for slug, _ in self._window
                if _compute_status(slug, now_utc) == "upcoming"
            )

            # Only call Gamma if we're running low on upcoming slots
            if upcoming <= 1:
                await self._expand_right()

            # Trim ended from left (keep scan_slots_before)
            self._trim_left()

    async def _expand_right(self) -> None:
        prefix = settings.scan_slug_prefix
        interval = settings.scan_duration_s
        existing = {slug for slug, _ in self._window}

        if self._window:
            rightmost_ts = _extract_epoch(self._window[-1][0])
        else:
            now_ts = int(datetime.now(timezone.utc).timestamp())
            rightmost_ts = now_ts - (now_ts % interval) - interval

        slugs_to_fetch = []
        for i in range(1, settings.scan_slots_after + 2):
            slug = f"{prefix}-{rightmost_ts + i * interval}"
            if slug not in existing:
                slugs_to_fetch.append(slug)

        if not slugs_to_fetch:
            return

        # Try batch first, fallback to individual
        added = 0
        if not await self._batch_fetch(slugs_to_fetch):
            for slug in slugs_to_fetch:
                if slug in self._index:
                    continue
                event = await self._fetch_slug(slug)
                if event:
                    self._window.append((slug, event))
                    self._index[slug] = event
                    added += 1
        else:
            added = sum(1 for s in slugs_to_fetch if s in self._index)

        if added:
            logger.info("MarketScanner: expanded +%d sessions", added)
            self._new_session_event.set()

    def _trim_left(self) -> None:
        now_utc = datetime.now(timezone.utc)
        ended = 0
        for slug, _ in self._window:
            if _compute_status(slug, now_utc) == "ended":
                ended += 1
            else:
                break
        while ended > settings.scan_slots_before and self._window:
            slug, _ = self._window.popleft()
            self._index.pop(slug, None)
            ended -= 1

    async def _fetch_slug(self, slug: str) -> dict | None:
        url = f"{settings.gamma_api_url}/events"
        try:
            resp = await _get_client().get(url, params={"limit": 1, "slug": slug})
            if resp.status_code != 200:
                return None
            data = resp.json()
            if not data:
                return None
            return _normalize_event(data[0])
        except Exception as e:
            logger.warning("MarketScanner: failed to fetch %s: %s", slug, e)
            return None

    async def _batch_fetch(self, slugs: list[str]) -> bool:
        """Fetch multiple sessions in a single Gamma API query.

        Uses tag-based search to get all BTC 15-min events in one call.
        Returns True if successful and at least one session was loaded.
        """
        url = f"{settings.gamma_api_url}/events"
        try:
            resp = await _get_client().get(url, params={
                "tag": "BTC",
                "limit": len(slugs) + 5,
                "closed": "false",
            })
            if resp.status_code != 200:
                return False
            data = resp.json()
            if not data:
                return False

            slug_set = set(slugs)
            loaded = 0
            for event in data:
                for m0 in event.get("markets", []):
                    market_slug = m0.get("groupItemTitle", "") or ""
                    # Also check the event-level slug
                    event_slug = event.get("slug", "")
                    for slug in (market_slug, event_slug):
                        if slug in slug_set and slug not in self._index:
                            norm = _normalize_event(event)
                            self._window.append((slug, norm))
                            self._index[slug] = norm
                            loaded += 1

            # Also try matching by extracting slugs from market questions
            for slug in slugs:
                if slug in self._index:
                    continue
                # Individual fallback for any missing
                event = await self._fetch_slug(slug)
                if event:
                    self._window.append((slug, event))
                    self._index[slug] = event
                    loaded += 1

            if loaded:
                # Sort window by epoch
                items = sorted(self._window, key=lambda x: _extract_epoch(x[0]))
                self._window.clear()
                self._window.extend(items)
                return True
            return False
        except Exception as e:
            logger.debug("MarketScanner: batch fetch failed: %s", e)
            return False
