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
    list_available_markets,
    query_orderbooks,
    query_prices,
)

logger = logging.getLogger(__name__)


# ── Status check ─────────────────────────────────────────────────────────────

async def check_event_status(slug: str) -> dict:
    """Return current status of an event: upcoming / live / ended."""
    # Try cache first
    cached = await redis_store.get_event_status(slug)
    if cached:
        try:
            return json.loads(cached)
        except (json.JSONDecodeError, TypeError):
            pass

    event = await resolve_event_slug(slug)
    if not event:
        return {"slug": slug, "status": "unknown"}

    now_utc = datetime.now(timezone.utc)
    result = _compute_status(slug, event, now_utc)

    await redis_store.set_event_status(slug, json.dumps(result))
    return result


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
    start_str = market_info.get("startDate", "") or market_info.get("start_date", "")
    end_str = market_info.get("endDate", "") or market_info.get("end_date", "")
    market_id = market_info.get("id", slug)

    token_ids = market_info.get("clobTokenIds", [])
    if isinstance(token_ids, str):
        try:
            token_ids = json.loads(token_ids)
        except (json.JSONDecodeError, TypeError):
            token_ids = [token_ids]

    # Copy data to archive directory
    prices_count = 0
    ob_count = 0
    trades_count = 0
    live_trades_count = 0
    try:
        prices_count = archive_event_data(
            slug, market_id, "prices", start_str, end_str,
        )
        ob_count = archive_event_data(
            slug, market_id, "orderbooks", start_str, end_str,
        )
        trades_count = archive_event_data(
            slug, market_id, "trades", start_str, end_str,
        )
        live_trades_count = archive_event_data(
            slug, market_id, "live_trades", start_str, end_str,
        )
    except Exception as e:
        logger.warning("Partial archive for %s: %s", slug, e)

    meta = {
        "slug": slug,
        "title": market_info.get("question", slug),
        "market_id": market_id,
        "start_time": start_str,
        "end_time": end_str,
        "token_ids": token_ids,
        "prices_count": prices_count,
        "orderbooks_count": ob_count,
        "trades_count": trades_count,
        "live_trades_count": live_trades_count,
        "archived_at": datetime.now(timezone.utc).isoformat(),
    }
    await redis_store.set_archive_meta(slug, json.dumps(meta))

    # Unwatch tokens after successful archival
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
            result.append(meta)
    return result
