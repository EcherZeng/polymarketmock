"""Data loader — reads Parquet archives via DuckDB (no backend imports)."""

from __future__ import annotations

import logging
from datetime import timezone
from pathlib import Path

import duckdb

from core.data_scanner import decode_side, decode_token
from core.types import ArchiveData

logger = logging.getLogger(__name__)


def _query_parquet(path: Path, order_by: str = "timestamp") -> list[dict]:
    """Read a single Parquet file, return list of dicts ordered by timestamp."""
    if not path.exists():
        return []
    try:
        path_str = str(path).replace("\\", "/")
        conn = duckdb.connect()
        try:
            df = conn.sql(
                f"SELECT * FROM read_parquet('{path_str}') ORDER BY {order_by}"
            ).fetchdf()
            return df.to_dict("records")
        finally:
            conn.close()
    except Exception as e:
        logger.warning("Failed to read %s: %s", path, e)
        return []


def _query_parquet_glob(directory: Path, order_by: str = "timestamp") -> list[dict]:
    """Read all Parquet files in a directory via glob, merged and ordered."""
    if not directory.exists():
        return []
    parquet_files = list(directory.glob("*.parquet"))
    if not parquet_files:
        return []
    try:
        glob_str = str(directory / "*.parquet").replace("\\", "/")
        conn = duckdb.connect()
        try:
            df = conn.sql(
                f"SELECT * FROM read_parquet('{glob_str}') ORDER BY {order_by}"
            ).fetchdf()
            return df.to_dict("records")
        finally:
            conn.close()
    except Exception as e:
        logger.warning("Failed to read glob %s: %s", directory, e)
        return []


def _decode_rows(rows: list[dict], has_side: bool = False) -> list[dict]:
    """Decode int32 token_id and int8 side to strings."""
    decoded: list[dict] = []
    for row in rows:
        r = dict(row)
        # Decode token_id
        if "token_id" in r and isinstance(r["token_id"], (int,)):
            r["token_id"] = decode_token(r["token_id"])
        # Decode timestamp — force UTC when DuckDB returns naive datetime
        if "timestamp" in r:
            ts = r["timestamp"]
            if hasattr(ts, "isoformat"):
                if hasattr(ts, "tzinfo") and ts.tzinfo is None:
                    ts = ts.replace(tzinfo=timezone.utc)
                r["timestamp"] = ts.isoformat()
            else:
                r["timestamp"] = str(ts)
        # Decode side
        if has_side and "side" in r and isinstance(r["side"], (int,)):
            r["side"] = decode_side(r["side"])
        decoded.append(r)
    return decoded


def load_archive(data_dir: Path, slug: str) -> ArchiveData:
    """Load all Parquet files for one archived event.

    Tries the consolidated archive/ directory first. If it has no data,
    falls back to merging the live/ chunk files.
    """
    # ── 1. Try consolidated archive/ ─────────────────────────────────────
    base = data_dir / "sessions" / slug / "archive"
    if base.exists() and list(base.glob("*.parquet")):
        prices = _decode_rows(_query_parquet(base / "prices.parquet"))
        orderbooks = _decode_rows(_query_parquet(base / "orderbooks.parquet"))
        ob_deltas = _decode_rows(
            _query_parquet(base / "ob_deltas.parquet"), has_side=True,
        )
        live_trades = _decode_rows(
            _query_parquet(base / "live_trades.parquet"), has_side=True,
        )

        if prices or orderbooks:
            logger.info(
                "Loaded archive %s: %d prices, %d orderbooks, %d deltas, %d trades",
                slug, len(prices), len(orderbooks), len(ob_deltas), len(live_trades),
            )
            return ArchiveData(
                prices=prices,
                orderbooks=orderbooks,
                ob_deltas=ob_deltas,
                live_trades=live_trades,
            )

    # ── 2. Fallback: merge live/ chunk files ─────────────────────────────
    live_base = data_dir / "sessions" / slug / "live"
    if not live_base.exists():
        logger.warning("No archive or live data found for: %s", slug)
        return ArchiveData()

    prices = _decode_rows(_query_parquet_glob(live_base / "prices"))
    orderbooks = _decode_rows(_query_parquet_glob(live_base / "orderbooks"))
    ob_deltas = _decode_rows(
        _query_parquet_glob(live_base / "ob_deltas"), has_side=True,
    )
    live_trades = _decode_rows(
        _query_parquet_glob(live_base / "live_trades"), has_side=True,
    )

    logger.info(
        "Loaded live data %s: %d prices, %d orderbooks, %d deltas, %d trades",
        slug, len(prices), len(orderbooks), len(ob_deltas), len(live_trades),
    )
    return ArchiveData(
        prices=prices,
        orderbooks=orderbooks,
        ob_deltas=ob_deltas,
        live_trades=live_trades,
    )
