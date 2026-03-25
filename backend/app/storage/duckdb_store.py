"""DuckDB + Parquet storage for real Polymarket market data (prices, orderbooks)."""

from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path

import duckdb
import pyarrow as pa
import pyarrow.parquet as pq

from app.config import settings


def _ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)


# ── Price snapshots ──────────────────────────────────────────────────────────

PRICE_SCHEMA = pa.schema([
    ("timestamp", pa.string()),
    ("token_id", pa.string()),
    ("mid_price", pa.float64()),
    ("best_bid", pa.float64()),
    ("best_ask", pa.float64()),
    ("spread", pa.float64()),
])


def write_price_snapshot(
    market_id: str,
    token_id: str,
    mid_price: float,
    best_bid: float,
    best_ask: float,
    spread: float,
) -> None:
    now = datetime.now(timezone.utc)
    date_str = now.strftime("%Y-%m-%d")
    dir_path = os.path.join(settings.data_dir, "prices", market_id)
    _ensure_dir(dir_path)
    file_path = os.path.join(dir_path, f"{date_str}.parquet")

    table = pa.table(
        {
            "timestamp": [now.isoformat()],
            "token_id": [token_id],
            "mid_price": [mid_price],
            "best_bid": [best_bid],
            "best_ask": [best_ask],
            "spread": [spread],
        },
        schema=PRICE_SCHEMA,
    )

    if os.path.exists(file_path):
        existing = pq.read_table(file_path)
        table = pa.concat_tables([existing, table])

    pq.write_table(table, file_path)


# ── Orderbook snapshots ─────────────────────────────────────────────────────

ORDERBOOK_SCHEMA = pa.schema([
    ("timestamp", pa.string()),
    ("token_id", pa.string()),
    ("bid_prices", pa.string()),   # JSON array
    ("bid_sizes", pa.string()),    # JSON array
    ("ask_prices", pa.string()),   # JSON array
    ("ask_sizes", pa.string()),    # JSON array
])


def write_orderbook_snapshot(
    market_id: str,
    token_id: str,
    bid_prices: str,
    bid_sizes: str,
    ask_prices: str,
    ask_sizes: str,
) -> None:
    now = datetime.now(timezone.utc)
    date_str = now.strftime("%Y-%m-%d")
    dir_path = os.path.join(settings.data_dir, "orderbooks", market_id)
    _ensure_dir(dir_path)
    file_path = os.path.join(dir_path, f"{date_str}.parquet")

    table = pa.table(
        {
            "timestamp": [now.isoformat()],
            "token_id": [token_id],
            "bid_prices": [bid_prices],
            "bid_sizes": [bid_sizes],
            "ask_prices": [ask_prices],
            "ask_sizes": [ask_sizes],
        },
        schema=ORDERBOOK_SCHEMA,
    )

    if os.path.exists(file_path):
        existing = pq.read_table(file_path)
        table = pa.concat_tables([existing, table])

    pq.write_table(table, file_path)


# ── Trade snapshots (inferred from orderbook diffs) ─────────────────────

TRADE_SCHEMA = pa.schema([
    ("timestamp", pa.string()),
    ("token_id", pa.string()),
    ("side", pa.string()),
    ("price", pa.float64()),
    ("size", pa.float64()),
    ("inferred", pa.bool_()),
])


def write_trade_snapshot(
    market_id: str,
    token_id: str,
    side: str,
    price: float,
    size: float,
    timestamp: str | None = None,
    inferred: bool = True,
) -> None:
    now = datetime.now(timezone.utc)
    date_str = now.strftime("%Y-%m-%d")
    dir_path = os.path.join(settings.data_dir, "trades", market_id)
    _ensure_dir(dir_path)
    file_path = os.path.join(dir_path, f"{date_str}.parquet")

    table = pa.table(
        {
            "timestamp": [timestamp or now.isoformat()],
            "token_id": [token_id],
            "side": [side],
            "price": [price],
            "size": [size],
            "inferred": [inferred],
        },
        schema=TRADE_SCHEMA,
    )

    if os.path.exists(file_path):
        existing = pq.read_table(file_path)
        table = pa.concat_tables([existing, table])

    pq.write_table(table, file_path)


# ── Live trade snapshots (real on-chain trades from Data API) ────────────────

LIVE_TRADE_SCHEMA = pa.schema([
    ("timestamp", pa.string()),
    ("transaction_hash", pa.string()),
    ("market_id", pa.string()),
    ("token_id", pa.string()),
    ("condition_id", pa.string()),
    ("side", pa.string()),
    ("price", pa.float64()),
    ("size", pa.float64()),
    ("outcome", pa.string()),
    ("pseudonym", pa.string()),
    ("name", pa.string()),
])


def write_live_trade(
    market_id: str,
    token_id: str,
    condition_id: str,
    side: str,
    price: float,
    size: float,
    outcome: str = "",
    pseudonym: str = "",
    name: str = "",
    transaction_hash: str = "",
    timestamp: str | None = None,
) -> None:
    now = datetime.now(timezone.utc)
    date_str = now.strftime("%Y-%m-%d")
    dir_path = os.path.join(settings.data_dir, "live_trades", market_id)
    _ensure_dir(dir_path)
    file_path = os.path.join(dir_path, f"{date_str}.parquet")

    table = pa.table(
        {
            "timestamp": [timestamp or now.isoformat()],
            "transaction_hash": [transaction_hash],
            "market_id": [market_id],
            "token_id": [token_id],
            "condition_id": [condition_id],
            "side": [side],
            "price": [price],
            "size": [size],
            "outcome": [outcome],
            "pseudonym": [pseudonym],
            "name": [name],
        },
        schema=LIVE_TRADE_SCHEMA,
    )

    if os.path.exists(file_path):
        existing = pq.read_table(file_path)
        table = pa.concat_tables([existing, table])

    pq.write_table(table, file_path)


def query_live_trades(
    market_id: str,
    start_time: str | None = None,
    end_time: str | None = None,
) -> list[dict]:
    dir_path = os.path.join(settings.data_dir, "live_trades", market_id)
    if not os.path.isdir(dir_path):
        return []

    glob = os.path.join(dir_path, "*.parquet").replace("\\", "/")
    sql = f"SELECT * FROM read_parquet('{glob}') "
    conditions: list[str] = []
    if start_time:
        conditions.append(f"timestamp >= '{start_time}'")
    if end_time:
        conditions.append(f"timestamp <= '{end_time}'")
    if conditions:
        sql += " WHERE " + " AND ".join(conditions)
    sql += " ORDER BY timestamp"

    con = duckdb.connect()
    try:
        result = con.execute(sql).fetchdf()
        return result.to_dict(orient="records")
    except Exception:
        return []
    finally:
        con.close()


# ── Query helpers via DuckDB ────────────────────────────────────────────────

def query_prices(
    market_id: str,
    start_time: str | None = None,
    end_time: str | None = None,
) -> list[dict]:
    dir_path = os.path.join(settings.data_dir, "prices", market_id)
    if not os.path.isdir(dir_path):
        return []

    glob = os.path.join(dir_path, "*.parquet").replace("\\", "/")
    sql = f"SELECT * FROM read_parquet('{glob}') "
    conditions: list[str] = []
    if start_time:
        conditions.append(f"timestamp >= '{start_time}'")
    if end_time:
        conditions.append(f"timestamp <= '{end_time}'")
    if conditions:
        sql += " WHERE " + " AND ".join(conditions)
    sql += " ORDER BY timestamp"

    con = duckdb.connect()
    try:
        result = con.execute(sql).fetchdf()
        return result.to_dict(orient="records")
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
    sql = f"SELECT * FROM read_parquet('{glob}') "
    conditions: list[str] = []
    if start_time:
        conditions.append(f"timestamp >= '{start_time}'")
    if end_time:
        conditions.append(f"timestamp <= '{end_time}'")
    if conditions:
        sql += " WHERE " + " AND ".join(conditions)
    sql += " ORDER BY timestamp"

    con = duckdb.connect()
    try:
        result = con.execute(sql).fetchdf()
        return result.to_dict(orient="records")
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
    sql = f"SELECT * FROM read_parquet('{glob}') "
    conditions: list[str] = []
    if start_time:
        conditions.append(f"timestamp >= '{start_time}'")
    if end_time:
        conditions.append(f"timestamp <= '{end_time}'")
    if conditions:
        sql += " WHERE " + " AND ".join(conditions)
    sql += " ORDER BY timestamp"

    con = duckdb.connect()
    try:
        result = con.execute(sql).fetchdf()
        return result.to_dict(orient="records")
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
                        "token_id": tr[0],
                        "earliest_data": row[0],
                        "latest_data": row[1],
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
    """Copy price or orderbook data for a market into the archive directory.

    Returns the number of rows archived.
    """
    src_dir = os.path.join(settings.data_dir, data_type, market_id)
    if not os.path.isdir(src_dir):
        return 0

    archive_dir = os.path.join(settings.data_dir, "archives", slug)
    _ensure_dir(archive_dir)
    dest_path = os.path.join(archive_dir, f"{data_type}.parquet")

    glob_path = os.path.join(src_dir, "*.parquet").replace("\\", "/")

    con = duckdb.connect()
    try:
        sql = f"SELECT * FROM read_parquet('{glob_path}')"
        conditions: list[str] = []
        if start_time:
            conditions.append(f"timestamp >= '{start_time}'")
        if end_time:
            conditions.append(f"timestamp <= '{end_time}'")
        if conditions:
            sql += " WHERE " + " AND ".join(conditions)
        sql += " ORDER BY timestamp"

        result = con.execute(sql).fetchdf()
        if result.empty:
            return 0

        import pyarrow as pa
        table = pa.Table.from_pandas(result)
        pq.write_table(table, dest_path)
        return len(result)
    except Exception:
        return 0
    finally:
        con.close()


def query_archive_prices(
    slug: str,
    start_time: str | None = None,
    end_time: str | None = None,
) -> list[dict]:
    """Query archived price data for a completed event."""
    file_path = os.path.join(settings.data_dir, "archives", slug, "prices.parquet")
    if not os.path.exists(file_path):
        return []
    return _query_parquet_file(file_path, start_time, end_time)


def query_archive_orderbooks(
    slug: str,
    start_time: str | None = None,
    end_time: str | None = None,
) -> list[dict]:
    """Query archived orderbook data for a completed event."""
    file_path = os.path.join(settings.data_dir, "archives", slug, "orderbooks.parquet")
    if not os.path.exists(file_path):
        return []
    return _query_parquet_file(file_path, start_time, end_time)


def query_archive_trades(
    slug: str,
    start_time: str | None = None,
    end_time: str | None = None,
) -> list[dict]:
    """Query archived trade data for a completed event."""
    file_path = os.path.join(settings.data_dir, "archives", slug, "trades.parquet")
    if not os.path.exists(file_path):
        return []
    return _query_parquet_file(file_path, start_time, end_time)


def _query_parquet_file(
    file_path: str,
    start_time: str | None = None,
    end_time: str | None = None,
) -> list[dict]:
    """Generic helper to query a single parquet file with optional time range."""
    fp = file_path.replace("\\", "/")
    sql = f"SELECT * FROM read_parquet('{fp}')"
    conditions: list[str] = []
    if start_time:
        conditions.append(f"timestamp >= '{start_time}'")
    if end_time:
        conditions.append(f"timestamp <= '{end_time}'")
    if conditions:
        sql += " WHERE " + " AND ".join(conditions)
    sql += " ORDER BY timestamp"

    con = duckdb.connect()
    try:
        result = con.execute(sql).fetchdf()
        return result.to_dict(orient="records")
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning("DuckDB query failed for %s: %s", fp, e)
        return []
    finally:
        con.close()


def list_archives() -> list[str]:
    """List all archived event slugs by scanning the archives directory."""
    archive_dir = os.path.join(settings.data_dir, "archives")
    if not os.path.isdir(archive_dir):
        return []
    return [
        d for d in os.listdir(archive_dir)
        if os.path.isdir(os.path.join(archive_dir, d))
    ]
