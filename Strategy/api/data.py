"""Data source query API — directory scanning."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

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
