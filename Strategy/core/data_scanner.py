"""Data scanner — discovers available archives and markets via directory structure."""

from __future__ import annotations

import json
import logging
from pathlib import Path

import duckdb

from core.types import ArchiveInfo

logger = logging.getLogger(__name__)

# ── Token-id mapping ─────────────────────────────────────────────────────────

_TOKEN_MAP: dict[str, int] = {}  # full_token_str → int32
_TOKEN_RMAP: dict[int, str] = {}  # int32 → full_token_str

SIDE_RMAP: dict[int, str] = {0: "BUY", 1: "SELL", 2: "UNKNOWN"}


def load_token_map(data_dir: Path) -> None:
    """Load token_map.json from data directory."""
    global _TOKEN_MAP, _TOKEN_RMAP
    map_path = data_dir / "token_map.json"
    if map_path.exists():
        with open(map_path, "r") as f:
            raw = json.load(f)
        _TOKEN_MAP = {k: int(v) for k, v in raw.items()}
        _TOKEN_RMAP = {v: k for k, v in _TOKEN_MAP.items()}
        logger.info("Loaded token map: %d entries", len(_TOKEN_MAP))


def decode_token(tid: int) -> str:
    """Decode int32 token_id to full string."""
    return _TOKEN_RMAP.get(tid, str(tid))


def decode_side(side: int) -> str:
    """Decode int8 side to string."""
    return SIDE_RMAP.get(side, "UNKNOWN")


# ── Archive scanning ─────────────────────────────────────────────────────────


def scan_archives(data_dir: Path) -> list[ArchiveInfo]:
    """Scan archives/ directory. Each sub-directory is a slug."""
    archives_dir = data_dir / "archives"
    if not archives_dir.exists():
        return []

    results: list[ArchiveInfo] = []
    for d in sorted(archives_dir.iterdir()):
        if not d.is_dir():
            continue
        parquet_files = list(d.glob("*.parquet"))
        files = [f.name for f in parquet_files]
        size = sum(f.stat().st_size for f in parquet_files)

        # Try to read time range and token ids from prices.parquet
        time_range: dict = {}
        token_ids: list[str] = []
        prices_path = d / "prices.parquet"
        if prices_path.exists():
            try:
                df = duckdb.sql(
                    f"SELECT MIN(timestamp) as t_min, MAX(timestamp) as t_max "
                    f"FROM read_parquet('{prices_path}')"
                ).fetchdf()
                if not df.empty:
                    t_min = df.iloc[0]["t_min"]
                    t_max = df.iloc[0]["t_max"]
                    time_range = {
                        "start": str(t_min) if t_min is not None else "",
                        "end": str(t_max) if t_max is not None else "",
                    }
                # Get unique token ids
                tid_df = duckdb.sql(
                    f"SELECT DISTINCT token_id FROM read_parquet('{prices_path}')"
                ).fetchdf()
                token_ids = [decode_token(int(t)) for t in tid_df["token_id"].tolist()]
            except Exception as e:
                logger.warning("Failed to read archive metadata %s: %s", d.name, e)

        results.append(ArchiveInfo(
            slug=d.name,
            path=str(d),
            files=files,
            size_bytes=size,
            time_range=time_range,
            token_ids=token_ids,
        ))
    return results


def scan_live_markets(data_dir: Path) -> list[dict]:
    """Scan prices/ + orderbooks/ directories for live-collected market data."""
    results: list[dict] = []
    seen: set[str] = set()

    for subdir in ("prices", "orderbooks"):
        base = data_dir / subdir
        if not base.exists():
            continue
        for d in base.iterdir():
            if d.is_dir() and d.name not in seen:
                seen.add(d.name)
                parquet_files = list(d.glob("*.parquet"))
                results.append({
                    "market_id": d.name,
                    "data_types": [subdir],
                    "files": len(parquet_files),
                })

    # Merge data_types for same market_id
    merged: dict[str, dict] = {}
    for r in results:
        mid = r["market_id"]
        if mid in merged:
            merged[mid]["data_types"].extend(r["data_types"])
            merged[mid]["files"] += r["files"]
        else:
            merged[mid] = r
    return list(merged.values())
