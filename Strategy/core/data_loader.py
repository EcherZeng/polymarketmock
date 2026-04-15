"""Data loader — reads Parquet archives via DuckDB (no backend imports).

ob_deltas uses a compact namedtuple-based representation instead of
list[dict] to avoid 74 MB → ~42 MB per slug (187 K dicts eliminated).
All other data types stay as list[dict] (small row counts).
"""

from __future__ import annotations

import logging
from collections import namedtuple
from datetime import timezone
from pathlib import Path

import duckdb

from core.data_scanner import decode_side, decode_token
from core.types import ArchiveData

logger = logging.getLogger(__name__)


# ── Compact row helpers ──────────────────────────────────────────────────────
# A namedtuple is ~96 bytes vs ~400 bytes for a Python dict with 5 keys.
# The .get() / __contains__ methods keep backward compat with all consumers
# that use  row.get("field")  or  "field" in row.

_compact_row_cache: dict[tuple[str, ...], type] = {}


def _make_row_cls(columns: tuple[str, ...]) -> type:
    """Create (or reuse) a namedtuple subclass with dict-like .get()."""
    if columns in _compact_row_cache:
        return _compact_row_cache[columns]

    Base = namedtuple("Row", columns)  # type: ignore[misc]

    class CompactRow(Base):
        __slots__ = ()

        def get(self, key: str, default=None):
            try:
                return self[self._fields.index(key)]
            except ValueError:
                return default

        def __contains__(self, key: object) -> bool:
            return key in self._fields

    CompactRow.__name__ = CompactRow.__qualname__ = "CompactRow"
    _compact_row_cache[columns] = CompactRow
    return CompactRow


def _decode_compact_stream(
    columns: tuple[str, ...],
    result,
    has_side: bool,
    *,
    batch_size: int = 2000,
) -> list:
    """Stream-decode DuckDB result into compact namedtuple rows.

    Uses fetchmany() to avoid materialising the entire raw tuple list
    at once (saves ~47 MB peak for 187 K ob_deltas rows).
    """
    RowCls = _make_row_cls(columns)
    col_idx = {c: i for i, c in enumerate(columns)}
    ti = col_idx.get("timestamp")
    tki = col_idx.get("token_id")
    si = col_idx.get("side") if has_side else None

    rows: list = []
    while True:
        batch = result.fetchmany(batch_size)
        if not batch:
            break
        for r in batch:
            vals = list(r)
            # Decode timestamp — force UTC when DuckDB returns naive datetime
            if ti is not None:
                v = vals[ti]
                if hasattr(v, "isoformat"):
                    if hasattr(v, "tzinfo") and v.tzinfo is None:
                        v = v.replace(tzinfo=timezone.utc)
                    vals[ti] = v.isoformat()
                else:
                    vals[ti] = str(v)
            # Decode int32 token_id to string
            if tki is not None and isinstance(vals[tki], int):
                vals[tki] = decode_token(vals[tki])
            # Decode int8 side
            if si is not None and isinstance(vals[si], int):
                vals[si] = decode_side(vals[si])
            rows.append(RowCls(*vals))

    return rows


def _load_compact_parquet(
    path: Path,
    order_by: str = "timestamp",
    has_side: bool = False,
) -> list:
    """Read a single Parquet file → compact namedtuple rows.

    Skips the pandas DataFrame intermediate and uses streaming fetchmany()
    to keep peak memory at O(output) instead of O(2 × output).
    """
    if not path.exists():
        return []
    try:
        path_str = str(path).replace("\\", "/")
        conn = duckdb.connect()
        try:
            result = conn.sql(
                f"SELECT * FROM read_parquet('{path_str}') ORDER BY {order_by}"
            )
            columns = tuple(result.columns)
            return _decode_compact_stream(columns, result, has_side)
        finally:
            conn.close()
    except Exception as e:
        logger.warning("Failed to read %s: %s", path, e)
        return []


def _load_compact_parquet_glob(
    directory: Path,
    order_by: str = "timestamp",
    has_side: bool = False,
) -> list:
    """Read all Parquet files in *directory* → compact namedtuple rows."""
    if not directory.exists():
        return []
    if not list(directory.glob("*.parquet")):
        return []
    try:
        glob_str = str(directory / "*.parquet").replace("\\", "/")
        conn = duckdb.connect()
        try:
            result = conn.sql(
                f"SELECT * FROM read_parquet('{glob_str}') ORDER BY {order_by}"
            )
            columns = tuple(result.columns)
            return _decode_compact_stream(columns, result, has_side)
        finally:
            conn.close()
    except Exception as e:
        logger.warning("Failed to read glob %s: %s", directory, e)
        return []


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
    """Decode int32 token_id and int8 side to strings — in-place to avoid doubling memory."""
    for r in rows:
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
    return rows


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
        ob_deltas = _load_compact_parquet(
            base / "ob_deltas.parquet", has_side=True,
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
    ob_deltas = _load_compact_parquet_glob(
        live_base / "ob_deltas", has_side=True,
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
