"""Data source query API — directory scanning."""

from __future__ import annotations

import re
import shutil

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from config import config
from core.data_scanner import scan_archives, scan_live_markets

router = APIRouter()


@router.get("/data/archives")
async def list_archives():
    """List all archived events discovered from directory."""
    archives = scan_archives(config.data_dir)
    return [
        {
            "slug": a.slug,
            "path": a.path,
            "files": a.files,
            "size_mb": round(a.size_bytes / 1_048_576, 2),
            "time_range": a.time_range,
            "token_ids": a.token_ids,
            "prices_count": a.prices_count,
            "orderbooks_count": a.orderbooks_count,
            "live_trades_count": a.live_trades_count,
            "source": a.source,
        }
        for a in archives
    ]


@router.get("/data/archives/{slug}")
async def get_archive_detail(slug: str):
    """Get detailed info for a specific archive."""
    archives = scan_archives(config.data_dir)
    for a in archives:
        if a.slug == slug:
            return {
                "slug": a.slug,
                "path": a.path,
                "files": a.files,
                "size_mb": round(a.size_bytes / 1_048_576, 2),
                "time_range": a.time_range,
                "token_ids": a.token_ids,
                "prices_count": a.prices_count,
                "orderbooks_count": a.orderbooks_count,
                "live_trades_count": a.live_trades_count,
                "source": a.source,
            }
    raise HTTPException(status_code=404, detail=f"Archive '{slug}' not found")


@router.get("/data/markets")
async def list_markets():
    """List markets with live-collected data."""
    return scan_live_markets(config.data_dir)


# ── Incomplete data detection & cleanup ──────────────────────────────────────

# Thresholds: minimum prices_count required for a session to be "complete"
_DURATION_MIN_PRICES: dict[int, int] = {
    5: 100,
    15: 1000,
}
_DEFAULT_MIN_PRICES = 100  # fallback for unknown durations


def _extract_duration_min(slug: str) -> int:
    """Extract duration in minutes from slug like 'btc-updown-15m-1774938000'."""
    m = re.search(r"(\d+)m-\d{10}$", slug)
    return int(m.group(1)) if m else 0


@router.get("/data/incomplete")
async def list_incomplete_archives(
    min_prices_5m: int = Query(100, ge=0, description="5 分钟场次最低 prices 条数"),
    min_prices_15m: int = Query(1000, ge=0, description="15 分钟场次最低 prices 条数"),
):
    """扫描所有归档，返回不满足最低数据量的不完整数据源列表。"""
    archives = scan_archives(config.data_dir)
    thresholds = {5: min_prices_5m, 15: min_prices_15m}
    incomplete: list[dict] = []
    for a in archives:
        dur = _extract_duration_min(a.slug)
        threshold = thresholds.get(dur, _DEFAULT_MIN_PRICES)
        if a.prices_count < threshold:
            incomplete.append({
                "slug": a.slug,
                "source": a.source,
                "duration_min": dur,
                "prices_count": a.prices_count,
                "orderbooks_count": a.orderbooks_count,
                "live_trades_count": a.live_trades_count,
                "size_mb": round(a.size_bytes / 1_048_576, 2),
                "time_range": a.time_range,
                "threshold": threshold,
            })
    return {
        "total_archives": len(archives),
        "incomplete_count": len(incomplete),
        "thresholds": thresholds,
        "items": incomplete,
    }


class DeleteRequest(BaseModel):
    slugs: list[str]


@router.post("/data/cleanup")
async def cleanup_incomplete(req: DeleteRequest):
    """删除指定的不完整数据源目录（硬删 session 目录）。"""
    deleted: list[str] = []
    not_found: list[str] = []
    sessions_dir = config.data_dir / "sessions"
    for slug in req.slugs:
        # Validate slug format to prevent path traversal
        if not re.match(r"^[\w\-]+$", slug):
            continue
        session_dir = sessions_dir / slug
        if session_dir.is_dir():
            shutil.rmtree(session_dir)
            deleted.append(slug)
        else:
            not_found.append(slug)
    return {
        "deleted": deleted,
        "not_found": not_found,
        "deleted_count": len(deleted),
    }


@router.delete("/data/archives/{slug}")
async def delete_single_archive(slug: str):
    """删除单个数据源目录。"""
    if not re.match(r"^[\w\-]+$", slug):
        raise HTTPException(status_code=400, detail="Invalid slug format")
    sessions_dir = config.data_dir / "sessions"
    session_dir = sessions_dir / slug
    if not session_dir.is_dir():
        raise HTTPException(status_code=404, detail=f"Session '{slug}' not found")
    shutil.rmtree(session_dir)
    return {"deleted": slug}
