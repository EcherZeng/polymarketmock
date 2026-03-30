"""Event lifecycle management — status detection, next-event lookup, and archival."""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone

from app.services.polymarket_proxy import resolve_event_slug, get_event
from app.storage import redis_store
from app.storage.duckdb_store import (
    archive_event_data,
    get_archive_data_range,
    list_available_markets,
    query_orderbooks,
    query_prices,
)

# Lazy import to avoid circular dependency at module level
def _get_ws_manager():
    from app.services.ws_manager import get_ws_manager
    try:
        return get_ws_manager()
    except AssertionError:
        return None

logger = logging.getLogger(__name__)


# ── Status check ─────────────────────────────────────────────────────────────

async def check_event_status(slug: str) -> dict:
    """Return current status of an event: upcoming / live / ended."""
    # Try cache first
    cached = await redis_store.get_event_status(slug)
    if cached:
        try:
            result = json.loads(cached)
            # Always add fresh archive_ready for ended events
            if result.get("status") == "ended":
                existing = await redis_store.get_archive_meta(slug)
                result["archive_ready"] = existing is not None
            # Add live recording lock info (not cached — changes per-tab)
            owner = await redis_store.get_recording_lock_owner(slug)
            result["recording_active"] = owner is not None
            return result
        except (json.JSONDecodeError, TypeError):
            pass

    event = await resolve_event_slug(slug)
    if not event:
        return {"slug": slug, "status": "unknown"}

    now_utc = datetime.now(timezone.utc)
    result = _compute_status(slug, event, now_utc)

    await redis_store.set_event_status(slug, json.dumps(result))

    # When event transitions to ended, trigger archival immediately
    if result.get("status") == "ended":
        await _trigger_archive_if_needed(slug)

    # Include archive_ready flag for ended events
    if result.get("status") == "ended":
        existing = await redis_store.get_archive_meta(slug)
        result["archive_ready"] = existing is not None

    # Add live recording lock info
    owner = await redis_store.get_recording_lock_owner(slug)
    result["recording_active"] = owner is not None

    return result


async def _trigger_archive_if_needed(slug: str) -> None:
    """Immediately trigger archival for a just-ended event (skip 30s cycle wait)."""
    existing = await redis_store.get_archive_meta(slug)
    if existing:
        return  # Already archived

    watched = await redis_store.get_watched_markets()
    if not watched:
        return

    for token_id, market_id in list(watched.items()):
        market_info = await redis_store.get_token_market_info(token_id)
        if not market_info:
            continue
        info_slug = market_info.get("slug", market_id)
        if info_slug != slug:
            continue

        logger.info("Immediate archival for ended event: %s", slug)
        try:
            await archive_event(slug, market_info)
        except Exception as e:
            logger.warning("Immediate archive failed for %s: %s", slug, e)
        return  # Only need to archive once per slug


def _compute_status(slug: str, event: dict, now_utc: datetime) -> dict:
    """Compute event status from event data and current time."""
    end_str = event.get("endDate", "") or event.get("end_date", "")
    start_str = ""
    markets = event.get("markets", [])
    if markets:
        m0 = markets[0]
        start_str = m0.get("eventStartTime", m0.get("startDate", "")) or ""
    if not start_str:
        start_str = event.get("startDate", "") or event.get("start_date", "")

    status = "unknown"
    ended_at = None
    seconds_remaining = None

    if end_str:
        try:
            end_dt = datetime.fromisoformat(end_str.replace("Z", "+00:00"))
            start_dt = (
                datetime.fromisoformat(start_str.replace("Z", "+00:00"))
                if start_str
                else end_dt
            )
            if end_dt <= now_utc:
                status = "ended"
                ended_at = end_str
            elif start_dt <= now_utc:
                status = "live"
                seconds_remaining = (end_dt - now_utc).total_seconds()
            else:
                status = "upcoming"
                seconds_remaining = (start_dt - now_utc).total_seconds()
        except (ValueError, TypeError):
            pass

    # Also check the active/closed flags
    if status == "unknown":
        if event.get("closed"):
            status = "ended"
        elif event.get("active"):
            status = "live"

    return {
        "slug": slug,
        "status": status,
        "ended_at": ended_at,
        "seconds_remaining": round(seconds_remaining, 1) if seconds_remaining is not None else None,
    }


# ── Watch (register tokens for recording) ────────────────────────────────────


async def watch_event_tokens(slug: str, event: dict) -> list[str]:
    """Register all tokens from an event for data collection.

    Idempotent — safe to call multiple times.
    Returns list of watched token IDs.
    """
    markets = event.get("markets", [])
    watched_tokens: list[str] = []

    for m in markets:
        token_ids_raw = m.get("clobTokenIds", [])
        if isinstance(token_ids_raw, str):
            try:
                token_ids_raw = json.loads(token_ids_raw)
            except (ValueError, TypeError):
                token_ids_raw = [token_ids_raw]
        market_id = m.get("id", "")
        for tid in token_ids_raw:
            if not tid:
                continue
            await redis_store.add_watched_market(tid, market_id)
            watched_tokens.append(tid)
            info = {
                "id": market_id,
                "question": m.get("question", ""),
                "slug": slug,
                "startDate": m.get("startDate", "") or m.get("eventStartTime", ""),
                "endDate": m.get("endDate", "") or event.get("endDate", ""),
                "clobTokenIds": token_ids_raw,
                "outcomes": m.get("outcomes", []),
            }
            await redis_store.set_token_market_info(tid, json.dumps(info))

    return watched_tokens


# ── Next event lookup ────────────────────────────────────────────────────────

# Patterns like btc-updown-5m-1774334100
_BTC_SLUG_RE = re.compile(r"^(btc-updown-\d+m)-(\d+)$")

# Generic slug with trailing timestamp
_GENERIC_TS_RE = re.compile(r"^(.+?)-(\d{10})$")


async def get_next_live_event(current_slug: str) -> dict | None:
    """Find the next live or upcoming event of the same type."""
    m = _BTC_SLUG_RE.match(current_slug)
    if m:
        prefix = m.group(1)
        curr_ts = int(m.group(2))
        # Determine interval from prefix
        interval = _interval_from_prefix(prefix)
        return await _find_next_btc(prefix, curr_ts, interval)

    m = _GENERIC_TS_RE.match(current_slug)
    if m:
        prefix = m.group(1)
        curr_ts = int(m.group(2))
        interval = 300  # default 5m
        return await _find_next_btc(prefix, curr_ts, interval)

    return None


def _interval_from_prefix(prefix: str) -> int:
    if "5m" in prefix:
        return 300
    if "15m" in prefix:
        return 900
    if "30m" in prefix:
        return 1800
    return 300


async def _find_next_btc(prefix: str, curr_ts: int, interval: int) -> dict | None:
    """Search forward for the next live/upcoming event."""
    now_ts = int(datetime.now(timezone.utc).timestamp())
    # Align to interval boundary
    window_start = now_ts - (now_ts % interval)

    for offset in range(0, 6):
        candidate_ts = window_start + offset * interval
        if candidate_ts <= curr_ts:
            continue
        slug = f"{prefix}-{candidate_ts}"
        try:
            event = await resolve_event_slug(slug)
            if event:
                return {
                    "slug": slug,
                    "event": event,
                    "status": _compute_status(slug, event, datetime.now(timezone.utc)).get("status", "unknown"),
                }
        except Exception:
            continue
    return None


async def find_current_or_next_event(prefix: str, interval: int) -> dict | None:
    """Find the current LIVE or next upcoming event for a BTC series.

    Unlike ``_find_next_btc`` this includes the slot aligned to *now*,
    so it can discover an event that is already in progress.
    """
    now_ts = int(datetime.now(timezone.utc).timestamp())
    window_start = now_ts - (now_ts % interval)

    for offset in range(0, 6):
        candidate_ts = window_start + offset * interval
        slug = f"{prefix}-{candidate_ts}"
        try:
            event = await resolve_event_slug(slug)
            if not event:
                continue
            status_info = _compute_status(slug, event, datetime.now(timezone.utc))
            st = status_info.get("status", "unknown")
            if st in ("live", "upcoming"):
                return {
                    "slug": slug,
                    "event": event,
                    "status": st,
                    "seconds_remaining": status_info.get("seconds_remaining"),
                }
        except Exception:
            continue
    return None


# ── Archival ─────────────────────────────────────────────────────────────────

async def auto_archive_if_ended() -> None:
    """Check watched markets for ended events and archive them."""
    watched = await redis_store.get_watched_markets()
    if not watched:
        return

    # Group tokens by market_id for lookup
    for token_id, market_id in list(watched.items()):
        market_info = await redis_store.get_token_market_info(token_id)
        if not market_info:
            continue

        end_str = market_info.get("endDate", "") or market_info.get("end_date", "")
        if not end_str:
            continue

        try:
            end_dt = datetime.fromisoformat(end_str.replace("Z", "+00:00"))
        except (ValueError, TypeError):
            continue

        now_utc = datetime.now(timezone.utc)
        if end_dt > now_utc:
            continue

        # Event has ended — archive
        slug = market_info.get("slug", market_id)
        existing = await redis_store.get_archive_meta(slug)
        if existing:
            continue  # Already archived

        logger.info("Archiving ended event: %s (token %s)", slug, token_id)
        try:
            await archive_event(slug, market_info)
        except Exception as e:
            logger.warning("Failed to archive %s: %s", slug, e)


async def archive_event(slug: str, market_info: dict) -> dict:
    """Archive all collected data for an event."""
    # Flush in-memory Parquet buffer so all data is on disk before archiving
    from app.storage.duckdb_store import get_buffer
    try:
        get_buffer().flush_all()
    except Exception as e:
        logger.warning("Buffer flush before archive failed: %s", e)

    start_str = market_info.get("startDate", "") or market_info.get("start_date", "")
    end_str = market_info.get("endDate", "") or market_info.get("end_date", "")
    market_id = market_info.get("id", slug)

    token_ids = market_info.get("clobTokenIds", [])
    if isinstance(token_ids, str):
        try:
            token_ids = json.loads(token_ids)
        except (json.JSONDecodeError, TypeError):
            token_ids = [token_ids]

    # Derive precise event window from slug timestamp BEFORE archiving,
    # so the time filter uses the actual event window (not market creation time).
    event_start = start_str
    event_end = end_str
    m = re.search(r"(\d+)m-(\d{10})$", slug)
    if m:
        interval_min = int(m.group(1))
        epoch = int(m.group(2))
        event_start = datetime.fromtimestamp(epoch, tz=timezone.utc).isoformat()
        event_end = datetime.fromtimestamp(epoch + interval_min * 60, tz=timezone.utc).isoformat()

    filter_start = event_start
    filter_end = event_end

    # Copy data to archive directory
    prices_count = 0
    ob_count = 0
    live_trades_count = 0
    ob_deltas_count = 0
    try:
        prices_count = archive_event_data(
            slug, market_id, "prices", filter_start, filter_end,
        )
        ob_count = archive_event_data(
            slug, market_id, "orderbooks", filter_start, filter_end,
        )
        live_trades_count = archive_event_data(
            slug, market_id, "live_trades", filter_start, filter_end,
        )
        ob_deltas_count = archive_event_data(
            slug, market_id, "ob_deltas", filter_start, filter_end,
        )
    except Exception as e:
        logger.warning("Partial archive for %s: %s", slug, e)

    # Get actual data time range from parquet files
    data_range = get_archive_data_range(slug)

    # Preserve outcomes from market_info (e.g. ["Up", "Down"])
    outcomes = market_info.get("outcomes", [])
    if isinstance(outcomes, str):
        try:
            outcomes = json.loads(outcomes)
        except (json.JSONDecodeError, TypeError):
            outcomes = []

    meta = {
        "slug": slug,
        "title": market_info.get("question", slug),
        "market_id": market_id,
        "start_time": event_start,
        "end_time": event_end,
        "data_start": data_range.get("data_start", ""),
        "data_end": data_range.get("data_end", ""),
        "token_ids": token_ids,
        "outcomes": outcomes,
        "prices_count": prices_count,
        "orderbooks_count": ob_count,
        "live_trades_count": live_trades_count,
        "ob_deltas_count": ob_deltas_count,
        "archived_at": datetime.now(timezone.utc).isoformat(),
    }
    await redis_store.set_archive_meta(slug, json.dumps(meta))

    # Close WS connections for ended event tokens BEFORE unwatching
    # (unwatch removes token_market_info which is needed for slug resolution)
    ws_mgr = _get_ws_manager()
    if ws_mgr and token_ids:
        try:
            await ws_mgr.close_clients_for_assets(
                [str(tid) for tid in token_ids],
                reason="event_ended",
            )
        except Exception as e:
            logger.warning("Failed to close WS clients for %s: %s", slug, e)

    # Mark recording session as complete
    if ws_mgr:
        try:
            await ws_mgr.complete_recording(slug, data_counts={
                "prices": prices_count,
                "orderbooks": ob_count,
                "live_trades": live_trades_count,
                "ob_deltas": ob_deltas_count,
            })
        except Exception as e:
            logger.warning("Failed to complete recording session for %s: %s", slug, e)

    # Unwatch tokens after successful archival + client closure
    for tid in token_ids:
        try:
            await redis_store.remove_watched_market(str(tid))
        except Exception:
            pass

    return meta


async def list_archived_events() -> list[dict]:
    """List all archived event slugs with metadata."""
    slugs = await redis_store.list_archive_slugs()
    result: list[dict] = []
    for slug in slugs:
        meta = await redis_store.get_archive_meta(slug)
        if meta:
            meta = await _ensure_archive_meta_fields(slug, meta)
            result.append(meta)
    return result


async def _ensure_archive_meta_fields(slug: str, meta: dict) -> dict:
    """Backfill data_start/data_end and fix start_time/end_time for legacy archives."""
    changed = False

    # Backfill data_start / data_end from parquet if missing
    if not meta.get("data_start") or not meta.get("data_end"):
        data_range = get_archive_data_range(slug)
        meta["data_start"] = data_range.get("data_start", "")
        meta["data_end"] = data_range.get("data_end", "")
        changed = True

    # Fix start_time / end_time from slug timestamp if they look wrong
    m = re.search(r"(\d+)m-(\d{10})$", slug)
    if m:
        interval_min = int(m.group(1))
        epoch = int(m.group(2))
        correct_start = datetime.fromtimestamp(epoch, tz=timezone.utc).isoformat()
        correct_end = datetime.fromtimestamp(epoch + interval_min * 60, tz=timezone.utc).isoformat()
        if meta.get("start_time") != correct_start or meta.get("end_time") != correct_end:
            meta["start_time"] = correct_start
            meta["end_time"] = correct_end
            changed = True

    if changed:
        await redis_store.set_archive_meta(slug, json.dumps(meta))

    return meta
