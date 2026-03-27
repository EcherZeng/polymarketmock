"""DuckDB + Parquet storage — optimised V2 schemas with compact types and buffered writes."""

from __future__ import annotations

import json
import logging
import os
import shutil
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

import duckdb
import pyarrow as pa
import pyarrow.parquet as pq

from app.config import settings

logger = logging.getLogger(__name__)


def _ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)


# ── Side mapping ─────────────────────────────────────────────────────────────

SIDE_MAP: dict[str, int] = {"BUY": 0, "SELL": 1, "UNKNOWN": 2}
SIDE_RMAP: dict[int, str] = {v: k for k, v in SIDE_MAP.items()}


def _encode_side(side: str) -> int:
    return SIDE_MAP.get(side.upper(), 2)


# ── Token-id ↔ int32 mapping ────────────────────────────────────────────────

_TOKEN_MAP: dict[str, int] = {}
_TOKEN_RMAP: dict[int, str] = {}
_token_lock = threading.Lock()
_TOKEN_MAP_PATH: str = ""


def load_token_map() -> None:
    global _TOKEN_MAP, _TOKEN_RMAP, _TOKEN_MAP_PATH
    _TOKEN_MAP_PATH = os.path.join(settings.data_dir, "token_map.json")
    if os.path.exists(_TOKEN_MAP_PATH):
        with open(_TOKEN_MAP_PATH, "r") as f:
            _TOKEN_MAP = {k: int(v) for k, v in json.load(f).items()}
        _TOKEN_RMAP = {v: k for k, v in _TOKEN_MAP.items()}


def _save_token_map() -> None:
    if _TOKEN_MAP_PATH:
        _ensure_dir(os.path.dirname(_TOKEN_MAP_PATH))
        with open(_TOKEN_MAP_PATH, "w") as f:
            json.dump(_TOKEN_MAP, f)


def encode_token(token_id: str) -> int:
    with _token_lock:
        if token_id in _TOKEN_MAP:
            return _TOKEN_MAP[token_id]
        new_id = (max(_TOKEN_MAP.values()) + 1) if _TOKEN_MAP else 0
        _TOKEN_MAP[token_id] = new_id
        _TOKEN_RMAP[new_id] = token_id
        _save_token_map()
        return new_id


def decode_token(tid: int) -> str:
    return _TOKEN_RMAP.get(tid, str(tid))


# ── V2 Schemas ───────────────────────────────────────────────────────────────

PRICE_SCHEMA = pa.schema([
    ("timestamp", pa.timestamp("us", tz="UTC")),
    ("token_id", pa.int32()),
    ("mid_price", pa.float32()),
    ("best_bid", pa.float32()),
    ("best_ask", pa.float32()),
    ("spread", pa.float32()),
])

ORDERBOOK_SCHEMA = pa.schema([
    ("timestamp", pa.timestamp("us", tz="UTC")),
    ("token_id", pa.int32()),
    ("bid_prices", pa.list_(pa.float32())),
    ("bid_sizes", pa.list_(pa.float32())),
    ("ask_prices", pa.list_(pa.float32())),
    ("ask_sizes", pa.list_(pa.float32())),
])

TRADE_SCHEMA = pa.schema([
    ("timestamp", pa.timestamp("us", tz="UTC")),
    ("token_id", pa.int32()),
    ("side", pa.int8()),
    ("price", pa.float32()),
    ("size", pa.float32()),
    ("inferred", pa.bool_()),
])

LIVE_TRADE_SCHEMA = pa.schema([
    ("timestamp", pa.timestamp("us", tz="UTC")),
    ("transaction_hash", pa.string()),
    ("token_id", pa.int32()),
    ("side", pa.int8()),
    ("price", pa.float32()),
    ("size", pa.float32()),
    ("outcome", pa.string()),
])

OB_DELTA_SCHEMA = pa.schema([
    ("timestamp", pa.timestamp("us", tz="UTC")),
    ("token_id", pa.int32()),
    ("side", pa.int8()),
    ("price", pa.float32()),
    ("size", pa.float32()),
])

_SCHEMAS: dict[str, pa.Schema] = {
    "prices": PRICE_SCHEMA,
    "orderbooks": ORDERBOOK_SCHEMA,
    "trades": TRADE_SCHEMA,
    "live_trades": LIVE_TRADE_SCHEMA,
    "ob_deltas": OB_DELTA_SCHEMA,
}


# ── Parquet buffer — batched writes ──────────────────────────────────────────


class ParquetBuffer:
    """Accumulates rows in memory and flushes to Parquet periodically."""

    def __init__(self, flush_interval: int = 30, flush_threshold: int = 100) -> None:
        self._buffers: dict[str, list[dict]] = {}
        self._last_flush: dict[str, float] = {}
        self._lock = threading.Lock()
        self.flush_interval = flush_interval
        self.flush_threshold = flush_threshold

    def _key(self, data_type: str, market_id: str) -> str:
        return f"{data_type}/{market_id}"

    def append(self, data_type: str, market_id: str, row: dict) -> None:
        key = self._key(data_type, market_id)
        with self._lock:
            self._buffers.setdefault(key, []).append(row)
        self.maybe_flush(data_type, market_id)

    def maybe_flush(self, data_type: str, market_id: str) -> None:
        key = self._key(data_type, market_id)
        with self._lock:
            rows = self._buffers.get(key)
            if not rows:
                return
            now = time.monotonic()
            last = self._last_flush.get(key, 0)
            should = len(rows) >= self.flush_threshold or (now - last >= self.flush_interval and len(rows) > 0)
            if not should:
                return
            to_write = list(rows)
            rows.clear()
            self._last_flush[key] = now
        self._write(data_type, market_id, to_write)

    def flush_all(self) -> None:
        with self._lock:
            snapshot = {k: list(v) for k, v in self._buffers.items() if v}
            self._buffers.clear()
        for key, rows in snapshot.items():
            parts = key.split("/", 1)
            if len(parts) == 2:
                self._write(parts[0], parts[1], rows)

    def _write(self, data_type: str, market_id: str, rows: list[dict]) -> None:
        if not rows:
            return
        schema = _SCHEMAS.get(data_type)
        if not schema:
            return

        by_date: dict[str, list[dict]] = {}
        for r in rows:
            ts = r.get("timestamp")
            date_str = ts.strftime("%Y-%m-%d") if isinstance(ts, datetime) else datetime.now(timezone.utc).strftime("%Y-%m-%d")
            by_date.setdefault(date_str, []).append(r)

        dir_path = os.path.join(settings.data_dir, data_type, market_id)
        _ensure_dir(dir_path)

        for date_str, day_rows in by_date.items():
            file_path = os.path.join(dir_path, f"{date_str}.parquet")
            try:
                columns: dict[str, list] = {field.name: [] for field in schema}
                for r in day_rows:
                    for field in schema:
                        columns[field.name].append(r.get(field.name))
                table = pa.table(columns, schema=schema)
                if os.path.exists(file_path):
                    existing = pq.read_table(file_path, schema=schema)
                    table = pa.concat_tables([existing, table])
                pq.write_table(table, file_path, compression="zstd")
            except Exception as e:
                logger.warning("Parquet flush failed %s/%s/%s: %s", data_type, market_id, date_str, e)


_buffer: ParquetBuffer | None = None


def get_buffer() -> ParquetBuffer:
    assert _buffer is not None, "ParquetBuffer not initialised — call init_parquet_buffer()"
    return _buffer


def init_parquet_buffer() -> None:
    global _buffer
    load_token_map()
    _buffer = ParquetBuffer(
        flush_interval=settings.parquet_flush_interval,
        flush_threshold=settings.parquet_flush_threshold,
    )


def shutdown_parquet_buffer() -> None:
    if _buffer:
        _buffer.flush_all()


# ── Write helpers ────────────────────────────────────────────────────────────


def _parse_ts(timestamp: str | None) -> datetime:
    if timestamp:
        try:
            ts = datetime.fromisoformat(timestamp)
            return ts if ts.tzinfo else ts.replace(tzinfo=timezone.utc)
        except (ValueError, TypeError):
            pass
    return datetime.now(timezone.utc)


def write_price_snapshot(
    market_id: str,
    token_id: str,
    mid_price: float,
    best_bid: float,
    best_ask: float,
    spread: float,
    timestamp: str | None = None,
) -> None:
    get_buffer().append("prices", market_id, {
        "timestamp": _parse_ts(timestamp),
        "token_id": encode_token(token_id),
        "mid_price": mid_price,
        "best_bid": best_bid,
        "best_ask": best_ask,
        "spread": spread,
    })


def write_orderbook_snapshot(
    market_id: str,
    token_id: str,
    bid_prices: list[float],
    bid_sizes: list[float],
    ask_prices: list[float],
    ask_sizes: list[float],
    timestamp: str | None = None,
) -> None:
    get_buffer().append("orderbooks", market_id, {
        "timestamp": _parse_ts(timestamp),
        "token_id": encode_token(token_id),
        "bid_prices": [float(p) for p in bid_prices],
        "bid_sizes": [float(s) for s in bid_sizes],
        "ask_prices": [float(p) for p in ask_prices],
        "ask_sizes": [float(s) for s in ask_sizes],
    })


def write_trade_snapshot(
    market_id: str,
    token_id: str,
    side: str,
    price: float,
    size: float,
    timestamp: str | None = None,
    inferred: bool = True,
) -> None:
    get_buffer().append("trades", market_id, {
        "timestamp": _parse_ts(timestamp),
        "token_id": encode_token(token_id),
        "side": _encode_side(side),
        "price": price,
        "size": size,
        "inferred": inferred,
    })


def write_live_trade(
    market_id: str,
    token_id: str,
    side: str,
    price: float,
    size: float,
    outcome: str = "",
    transaction_hash: str = "",
    timestamp: str | None = None,
) -> None:
    get_buffer().append("live_trades", market_id, {
        "timestamp": _parse_ts(timestamp),
        "transaction_hash": transaction_hash,
        "token_id": encode_token(token_id),
        "side": _encode_side(side),
        "price": price,
        "size": size,
        "outcome": outcome,
    })


def write_ob_delta(
    market_id: str,
    token_id: str,
    side: str,
    price: float,
    size: float,
    timestamp: str | None = None,
) -> None:
    get_buffer().append("ob_deltas", market_id, {
        "timestamp": _parse_ts(timestamp),
        "token_id": encode_token(token_id),
        "side": _encode_side(side),
        "price": price,
        "size": size,
    })


# ── Query helpers ────────────────────────────────────────────────────────────


def _build_time_filter(start_time: str | None, end_time: str | None) -> str:
    conditions: list[str] = []
    if start_time:
        conditions.append(f"timestamp >= '{start_time}'")
    if end_time:
        conditions.append(f"timestamp <= '{end_time}'")
    return (" WHERE " + " AND ".join(conditions)) if conditions else ""


def _post_process_rows(rows: list[dict], has_side: bool = False) -> list[dict]:
    """Decode token_id and side back to strings, convert timestamps to ISO, convert ndarray to list."""
    import numpy as np
    for r in rows:
        tid = r.get("token_id")
        if isinstance(tid, int):
            r["token_id"] = decode_token(tid)
        if has_side:
            s = r.get("side")
            if isinstance(s, int):
                r["side"] = SIDE_RMAP.get(s, "UNKNOWN")
        ts = r.get("timestamp")
        if isinstance(ts, datetime):
            r["timestamp"] = ts.isoformat()
        elif hasattr(ts, "isoformat"):
            r["timestamp"] = ts.isoformat()
        # Convert numpy arrays to Python lists for JSON serialization
        for key, val in r.items():
            if isinstance(val, np.ndarray):
                r[key] = val.tolist()
    return rows


def query_prices(
    market_id: str,
    start_time: str | None = None,
    end_time: str | None = None,
) -> list[dict]:
    dir_path = os.path.join(settings.data_dir, "prices", market_id)
    if not os.path.isdir(dir_path):
        return []
    glob = os.path.join(dir_path, "*.parquet").replace("\\", "/")
    sql = f"SELECT * FROM read_parquet('{glob}')" + _build_time_filter(start_time, end_time) + " ORDER BY timestamp"
    con = duckdb.connect()
    try:
        return _post_process_rows(con.execute(sql).fetchdf().to_dict(orient="records"))
    except Exception:
        return []
    finally:
        con.close()


def query_orderbooks(
    market_id: str,
    start_time: str | None = None,
    end_time: str | None = None,
) -> list[dict]:
    dir_path = os.path.join(settings.data_dir, "orderbooks", market_id)
    if not os.path.isdir(dir_path):
        return []
    glob = os.path.join(dir_path, "*.parquet").replace("\\", "/")
    sql = f"SELECT * FROM read_parquet('{glob}')" + _build_time_filter(start_time, end_time) + " ORDER BY timestamp"
    con = duckdb.connect()
    try:
        return _post_process_rows(con.execute(sql).fetchdf().to_dict(orient="records"))
    except Exception:
        return []
    finally:
        con.close()


def query_trades(
    market_id: str,
    start_time: str | None = None,
    end_time: str | None = None,
) -> list[dict]:
    dir_path = os.path.join(settings.data_dir, "trades", market_id)
    if not os.path.isdir(dir_path):
        return []
    glob = os.path.join(dir_path, "*.parquet").replace("\\", "/")
    sql = f"SELECT * FROM read_parquet('{glob}')" + _build_time_filter(start_time, end_time) + " ORDER BY timestamp"
    con = duckdb.connect()
    try:
        return _post_process_rows(con.execute(sql).fetchdf().to_dict(orient="records"), has_side=True)
    except Exception:
        return []
    finally:
        con.close()


def query_live_trades(
    market_id: str,
    start_time: str | None = None,
    end_time: str | None = None,
) -> list[dict]:
    dir_path = os.path.join(settings.data_dir, "live_trades", market_id)
    if not os.path.isdir(dir_path):
        return []
    glob = os.path.join(dir_path, "*.parquet").replace("\\", "/")
    sql = f"SELECT * FROM read_parquet('{glob}')" + _build_time_filter(start_time, end_time) + " ORDER BY timestamp"
    con = duckdb.connect()
    try:
        return _post_process_rows(con.execute(sql).fetchdf().to_dict(orient="records"), has_side=True)
    except Exception:
        return []
    finally:
        con.close()


def list_available_markets() -> list[dict]:
    """List market IDs that have price data available."""
    prices_dir = os.path.join(settings.data_dir, "prices")
    if not os.path.isdir(prices_dir):
        return []

    markets: list[dict] = []
    for market_id in os.listdir(prices_dir):
        market_path = os.path.join(prices_dir, market_id)
        if not os.path.isdir(market_path):
            continue
        files = sorted(Path(market_path).glob("*.parquet"))
        if not files:
            continue
        con = duckdb.connect()
        try:
            glob = os.path.join(market_path, "*.parquet").replace("\\", "/")
            row = con.execute(
                f"SELECT MIN(timestamp) as earliest, MAX(timestamp) as latest, COUNT(*) as cnt "
                f"FROM read_parquet('{glob}')"
            ).fetchone()
            if row:
                token_rows = con.execute(
                    f"SELECT DISTINCT token_id FROM read_parquet('{glob}')"
                ).fetchall()
                for tr in token_rows:
                    markets.append({
                        "market_id": market_id,
                        "token_id": decode_token(tr[0]) if isinstance(tr[0], int) else str(tr[0]),
                        "earliest_data": row[0].isoformat() if isinstance(row[0], datetime) else str(row[0]),
                        "latest_data": row[1].isoformat() if isinstance(row[1], datetime) else str(row[1]),
                        "data_points": row[2],
                    })
        except Exception:
            pass
        finally:
            con.close()
    return markets


# ── Archive helpers ──────────────────────────────────────────────────────────


def archive_event_data(
    slug: str,
    market_id: str,
    data_type: str,
    start_time: str | None = None,
    end_time: str | None = None,
) -> int:
    """Copy data for a market into the archive directory. Returns rows archived."""
    src_dir = os.path.join(settings.data_dir, data_type, market_id)
    if not os.path.isdir(src_dir):
        return 0
    archive_dir = os.path.join(settings.data_dir, "archives", slug)
    _ensure_dir(archive_dir)
    dest_path = os.path.join(archive_dir, f"{data_type}.parquet")
    glob_path = os.path.join(src_dir, "*.parquet").replace("\\", "/")
    sql = f"SELECT * FROM read_parquet('{glob_path}')" + _build_time_filter(start_time, end_time) + " ORDER BY timestamp"
    schema = _SCHEMAS.get(data_type)
    con = duckdb.connect()
    try:
        result = con.execute(sql).fetchdf()
        if result.empty:
            return 0
        table = pa.Table.from_pandas(result, schema=schema, preserve_index=False)
        pq.write_table(table, dest_path, compression="zstd")
        return len(result)
    except Exception:
        return 0
    finally:
        con.close()


def query_archive_prices(
    slug: str, start_time: str | None = None, end_time: str | None = None,
) -> list[dict]:
    fp = os.path.join(settings.data_dir, "archives", slug, "prices.parquet")
    return _query_parquet_file(fp, start_time, end_time) if os.path.exists(fp) else []


def query_archive_orderbooks(
    slug: str, start_time: str | None = None, end_time: str | None = None,
) -> list[dict]:
    fp = os.path.join(settings.data_dir, "archives", slug, "orderbooks.parquet")
    return _query_parquet_file(fp, start_time, end_time) if os.path.exists(fp) else []


def query_archive_trades(
    slug: str, start_time: str | None = None, end_time: str | None = None,
) -> list[dict]:
    fp = os.path.join(settings.data_dir, "archives", slug, "trades.parquet")
    return _query_parquet_file(fp, start_time, end_time, has_side=True) if os.path.exists(fp) else []


def query_archive_live_trades(
    slug: str, start_time: str | None = None, end_time: str | None = None,
) -> list[dict]:
    fp = os.path.join(settings.data_dir, "archives", slug, "live_trades.parquet")
    return _query_parquet_file(fp, start_time, end_time, has_side=True) if os.path.exists(fp) else []


def query_ob_deltas(
    market_id: str,
    start_time: str | None = None,
    end_time: str | None = None,
) -> list[dict]:
    dir_path = os.path.join(settings.data_dir, "ob_deltas", market_id)
    if not os.path.isdir(dir_path):
        return []
    glob = os.path.join(dir_path, "*.parquet").replace("\\", "/")
    sql = f"SELECT * FROM read_parquet('{glob}')" + _build_time_filter(start_time, end_time) + " ORDER BY timestamp"
    con = duckdb.connect()
    try:
        return _post_process_rows(con.execute(sql).fetchdf().to_dict(orient="records"), has_side=True)
    except Exception:
        return []
    finally:
        con.close()


def query_archive_ob_deltas(
    slug: str, start_time: str | None = None, end_time: str | None = None,
) -> list[dict]:
    fp = os.path.join(settings.data_dir, "archives", slug, "ob_deltas.parquet")
    return _query_parquet_file(fp, start_time, end_time, has_side=True) if os.path.exists(fp) else []


def delete_archive(slug: str) -> bool:
    """Delete the archive directory for a given slug. Returns True if removed."""
    archive_dir = os.path.join(settings.data_dir, "archives", slug)
    if os.path.isdir(archive_dir):
        shutil.rmtree(archive_dir)
        return True
    return False


def _query_parquet_file(
    file_path: str,
    start_time: str | None = None,
    end_time: str | None = None,
    has_side: bool = False,
) -> list[dict]:
    fp = file_path.replace("\\", "/")
    sql = f"SELECT * FROM read_parquet('{fp}')" + _build_time_filter(start_time, end_time) + " ORDER BY timestamp"
    con = duckdb.connect()
    try:
        return _post_process_rows(con.execute(sql).fetchdf().to_dict(orient="records"), has_side=has_side)
    except Exception as e:
        logger.warning("DuckDB query failed for %s: %s", fp, e)
        return []
    finally:
        con.close()


def get_archive_data_range(slug: str) -> dict:
    """Return the actual min/max timestamps from archived parquet data."""
    archive_dir = os.path.join(settings.data_dir, "archives", slug)
    all_min: list[str] = []
    all_max: list[str] = []
    for name in ["prices", "orderbooks", "live_trades", "ob_deltas"]:
        fp = os.path.join(archive_dir, f"{name}.parquet").replace("\\", "/")
        if not os.path.exists(fp):
            continue
        con = duckdb.connect()
        try:
            row = con.execute(
                f"SELECT MIN(timestamp) as mn, MAX(timestamp) as mx FROM read_parquet('{fp}')"
            ).fetchdf().to_dict(orient="records")[0]
            mn = row.get("mn")
            mx = row.get("mx")
            if mn is not None and hasattr(mn, "isoformat"):
                all_min.append(mn.isoformat())
            if mx is not None and hasattr(mx, "isoformat"):
                all_max.append(mx.isoformat())
        except Exception:
            pass
        finally:
            con.close()
    return {
        "data_start": min(all_min) if all_min else "",
        "data_end": max(all_max) if all_max else "",
    }


def list_archives() -> list[str]:
    archive_dir = os.path.join(settings.data_dir, "archives")
    if not os.path.isdir(archive_dir):
        return []
    return [d for d in os.listdir(archive_dir) if os.path.isdir(os.path.join(archive_dir, d))]
