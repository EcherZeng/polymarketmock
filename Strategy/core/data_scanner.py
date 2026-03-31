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
    """Scan sessions/ directory for slugs that have an archive/ sub-directory."""
    sessions_dir = data_dir / "sessions"
    if not sessions_dir.exists():
        return []

    results: list[ArchiveInfo] = []
    archived_slugs: set[str] = set()

    for d in sorted(sessions_dir.iterdir()):
        if not d.is_dir():
            continue
        archive_dir = d / "archive"
        if not archive_dir.exists():
            continue
        parquet_files = list(archive_dir.glob("*.parquet"))
        if not parquet_files:
            continue
        archived_slugs.add(d.name)
        files = [f.name for f in parquet_files]
        size = sum(f.stat().st_size for f in parquet_files)

        # Try to read time range, token ids, and row counts
        time_range: dict = {}
        token_ids: list[str] = []
        prices_count = 0
        orderbooks_count = 0
        live_trades_count = 0

        prices_path = archive_dir / "prices.parquet"
        if prices_path.exists():
            try:
                df = duckdb.sql(
                    f"SELECT MIN(timestamp) as t_min, MAX(timestamp) as t_max, COUNT(*) as cnt "
                    f"FROM read_parquet('{prices_path}')"
                ).fetchdf()
                if not df.empty:
                    t_min = df.iloc[0]["t_min"]
                    t_max = df.iloc[0]["t_max"]
                    prices_count = int(df.iloc[0]["cnt"])
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

        ob_path = archive_dir / "orderbooks.parquet"
        if ob_path.exists():
            try:
                cnt_df = duckdb.sql(
                    f"SELECT COUNT(*) as cnt FROM read_parquet('{ob_path}')"
                ).fetchdf()
                if not cnt_df.empty:
                    orderbooks_count = int(cnt_df.iloc[0]["cnt"])
            except Exception:
                pass

        lt_path = archive_dir / "live_trades.parquet"
        if lt_path.exists():
            try:
                cnt_df = duckdb.sql(
                    f"SELECT COUNT(*) as cnt FROM read_parquet('{lt_path}')"
                ).fetchdf()
                if not cnt_df.empty:
                    live_trades_count = int(cnt_df.iloc[0]["cnt"])
            except Exception:
                pass

        results.append(ArchiveInfo(
            slug=d.name,
            path=str(archive_dir),
            files=files,
            size_bytes=size,
            time_range=time_range,
            token_ids=token_ids,
            prices_count=prices_count,
            orderbooks_count=orderbooks_count,
            live_trades_count=live_trades_count,
            source="archive",
        ))

    # ── Also discover sessions with live/ data but no archive ────────────
    for d in sorted(sessions_dir.iterdir()):
        if not d.is_dir() or d.name in archived_slugs:
            continue
        live_dir = d / "live"
        if not live_dir.exists():
            continue
        # Check if there are any parquet files under live/
        all_parquets: list[Path] = []
        for sub in live_dir.iterdir():
            if sub.is_dir():
                all_parquets.extend(sub.glob("*.parquet"))
        if not all_parquets:
            continue

        files = sorted({p.parent.name for p in all_parquets})  # data type names
        size = sum(f.stat().st_size for f in all_parquets)

        time_range = {}
        token_ids = []
        prices_count = 0
        orderbooks_count = 0
        live_trades_count = 0

        # Try prices
        prices_dir = live_dir / "prices"
        if prices_dir.exists() and list(prices_dir.glob("*.parquet")):
            try:
                glob_str = str(prices_dir / "*.parquet").replace("\\", "/")
                df = duckdb.sql(
                    f"SELECT MIN(timestamp) as t_min, MAX(timestamp) as t_max, COUNT(*) as cnt "
                    f"FROM read_parquet('{glob_str}')"
                ).fetchdf()
                if not df.empty:
                    t_min = df.iloc[0]["t_min"]
                    t_max = df.iloc[0]["t_max"]
                    prices_count = int(df.iloc[0]["cnt"])
                    time_range = {
                        "start": str(t_min) if t_min is not None else "",
                        "end": str(t_max) if t_max is not None else "",
                    }
                tid_df = duckdb.sql(
                    f"SELECT DISTINCT token_id FROM read_parquet('{glob_str}')"
                ).fetchdf()
                token_ids = [decode_token(int(t)) for t in tid_df["token_id"].tolist()]
            except Exception as e:
                logger.warning("Failed to read live metadata %s/prices: %s", d.name, e)

        # If no prices, try orderbooks for time_range and token_ids
        if not time_range:
            ob_dir = live_dir / "orderbooks"
            if ob_dir.exists() and list(ob_dir.glob("*.parquet")):
                try:
                    glob_str = str(ob_dir / "*.parquet").replace("\\", "/")
                    df = duckdb.sql(
                        f"SELECT MIN(timestamp) as t_min, MAX(timestamp) as t_max, COUNT(*) as cnt "
                        f"FROM read_parquet('{glob_str}')"
                    ).fetchdf()
                    if not df.empty:
                        t_min = df.iloc[0]["t_min"]
                        t_max = df.iloc[0]["t_max"]
                        orderbooks_count = int(df.iloc[0]["cnt"])
                        time_range = {
                            "start": str(t_min) if t_min is not None else "",
                            "end": str(t_max) if t_max is not None else "",
                        }
                    tid_df = duckdb.sql(
                        f"SELECT DISTINCT token_id FROM read_parquet('{glob_str}')"
                    ).fetchdf()
                    token_ids = [decode_token(int(t)) for t in tid_df["token_id"].tolist()]
                except Exception as e:
                    logger.warning("Failed to read live metadata %s/orderbooks: %s", d.name, e)

        # Orderbooks count (if not already read)
        if not orderbooks_count:
            ob_dir = live_dir / "orderbooks"
            if ob_dir.exists() and list(ob_dir.glob("*.parquet")):
                try:
                    glob_str = str(ob_dir / "*.parquet").replace("\\", "/")
                    cnt_df = duckdb.sql(
                        f"SELECT COUNT(*) as cnt FROM read_parquet('{glob_str}')"
                    ).fetchdf()
                    if not cnt_df.empty:
                        orderbooks_count = int(cnt_df.iloc[0]["cnt"])
                except Exception:
                    pass

        # Live trades count
        lt_dir = live_dir / "live_trades"
        if lt_dir.exists() and list(lt_dir.glob("*.parquet")):
            try:
                glob_str = str(lt_dir / "*.parquet").replace("\\", "/")
                cnt_df = duckdb.sql(
                    f"SELECT COUNT(*) as cnt FROM read_parquet('{glob_str}')"
                ).fetchdf()
                if not cnt_df.empty:
                    live_trades_count = int(cnt_df.iloc[0]["cnt"])
            except Exception:
                pass

        # Skip sessions without enough data for backtesting
        if prices_count < 10 and orderbooks_count < 10:
            continue

        results.append(ArchiveInfo(
            slug=d.name,
            path=str(live_dir),
            files=files,
            size_bytes=size,
            time_range=time_range,
            token_ids=token_ids,
            prices_count=prices_count,
            orderbooks_count=orderbooks_count,
            live_trades_count=live_trades_count,
            source="live",
        ))

    return results


def scan_live_markets(data_dir: Path) -> list[dict]:
    """Scan sessions/*/live/{prices,orderbooks}/ for live-collected market data."""
    results: list[dict] = []
    seen: set[str] = set()
    sessions_dir = data_dir / "sessions"
    if not sessions_dir.exists():
        return []

    for slug_dir in sessions_dir.iterdir():
        if not slug_dir.is_dir():
            continue
        slug = slug_dir.name
        for subdir in ("prices", "orderbooks"):
            data_path = slug_dir / "live" / subdir
            if not data_path.exists():
                continue
            key = f"{slug}/{subdir}"
            if key in seen:
                continue
            seen.add(key)
            parquet_files = list(data_path.glob("*.parquet"))
            results.append({
                "slug": slug,
                "data_types": [subdir],
                "files": len(parquet_files),
            })

    # Merge data_types for same slug
    merged: dict[str, dict] = {}
    for r in results:
        s = r["slug"]
        if s in merged:
            merged[s]["data_types"].extend(r["data_types"])
            merged[s]["files"] += r["files"]
        else:
            merged[s] = r
    return list(merged.values())
