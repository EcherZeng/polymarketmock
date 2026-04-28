"""Data store — DuckDB + Parquet persistence for trade records."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

import duckdb

from config import settings
from core.types import LiveFill, SessionInfo, SessionResult, SessionState

logger = logging.getLogger(__name__)


class DataStore:
    """Persistent storage for live trading data using DuckDB."""

    def __init__(self, data_dir: Path | None = None) -> None:
        self._data_dir = data_dir or settings.data_dir
        self._data_dir.mkdir(parents=True, exist_ok=True)
        self._db_path = self._data_dir / "trade.duckdb"
        self._conn: duckdb.DuckDBPyConnection | None = None

    async def start(self) -> None:
        self._conn = duckdb.connect(str(self._db_path))
        self._create_tables()
        logger.info("DataStore started: %s", self._db_path)

    async def stop(self) -> None:
        if self._conn:
            self._conn.close()
            self._conn = None

    def _create_tables(self) -> None:
        assert self._conn is not None
        # Create sequences BEFORE tables that reference them
        self._conn.execute("CREATE SEQUENCE IF NOT EXISTS trade_seq START 1")
        self._conn.execute("CREATE SEQUENCE IF NOT EXISTS price_seq START 1")
        self._conn.execute("CREATE SEQUENCE IF NOT EXISTS error_seq START 1")
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                slug VARCHAR PRIMARY KEY,
                token_ids VARCHAR,
                outcomes VARCHAR,
                start_epoch BIGINT,
                end_epoch BIGINT,
                duration_s INTEGER,
                state VARCHAR,
                trade_pnl DOUBLE DEFAULT 0,
                settlement_pnl DOUBLE DEFAULT 0,
                total_pnl DOUBLE DEFAULT 0,
                settlement_outcome VARCHAR DEFAULT '',
                error VARCHAR DEFAULT '',
                created_at TIMESTAMP DEFAULT current_timestamp,
                updated_at TIMESTAMP DEFAULT current_timestamp
            )
        """)
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS trades (
                id INTEGER PRIMARY KEY DEFAULT nextval('trade_seq'),
                order_id VARCHAR,
                session_slug VARCHAR,
                token_id VARCHAR,
                side VARCHAR,
                filled_shares DOUBLE,
                avg_price DOUBLE,
                total_cost DOUBLE,
                fees DOUBLE DEFAULT 0,
                timestamp TIMESTAMP,
                created_at TIMESTAMP DEFAULT current_timestamp
            )
        """)
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS price_snapshots (
                id INTEGER PRIMARY KEY DEFAULT nextval('price_seq'),
                session_slug VARCHAR,
                token_id VARCHAR,
                mid_price DOUBLE,
                best_bid DOUBLE,
                best_ask DOUBLE,
                spread DOUBLE,
                anchor_price DOUBLE,
                timestamp TIMESTAMP
            )
        """)
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS errors (
                id INTEGER PRIMARY KEY DEFAULT nextval('error_seq'),
                session_slug VARCHAR,
                error_type VARCHAR,
                message VARCHAR,
                context VARCHAR,
                timestamp TIMESTAMP DEFAULT current_timestamp
            )
        """)

    # ── Sessions ──────────────────────────────────────────────

    def save_session(self, session: SessionInfo, state: SessionState) -> None:
        assert self._conn is not None
        self._conn.execute("""
            INSERT OR REPLACE INTO sessions
            (slug, token_ids, outcomes, start_epoch, end_epoch, duration_s, state, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, current_timestamp)
        """, [
            session.slug,
            json.dumps(session.token_ids),
            json.dumps(session.outcomes),
            session.start_epoch,
            session.end_epoch,
            session.duration_s,
            state.value,
        ])

    def update_session_result(self, result: SessionResult) -> None:
        assert self._conn is not None
        self._conn.execute("""
            UPDATE sessions SET
                state = ?,
                trade_pnl = ?,
                settlement_pnl = ?,
                total_pnl = ?,
                settlement_outcome = ?,
                error = ?,
                updated_at = current_timestamp
            WHERE slug = ?
        """, [
            result.state.value,
            result.trade_pnl,
            result.settlement_pnl,
            result.total_pnl,
            result.settlement_outcome,
            result.error,
            result.session.slug,
        ])

    def get_sessions(self, limit: int = 50) -> list[dict]:
        assert self._conn is not None
        rows = self._conn.execute(
            "SELECT * FROM sessions ORDER BY start_epoch DESC LIMIT ?", [limit],
        ).fetchall()
        cols = [d[0] for d in self._conn.description]  # type: ignore
        return [dict(zip(cols, row)) for row in rows]

    def get_session(self, slug: str) -> dict | None:
        assert self._conn is not None
        rows = self._conn.execute(
            "SELECT * FROM sessions WHERE slug = ?", [slug],
        ).fetchall()
        if not rows:
            return None
        cols = [d[0] for d in self._conn.description]  # type: ignore
        return dict(zip(cols, rows[0]))

    # ── Trades ────────────────────────────────────────────────

    def save_trade(self, fill: LiveFill) -> None:
        assert self._conn is not None
        self._conn.execute("""
            INSERT INTO trades
            (order_id, session_slug, token_id, side, filled_shares, avg_price, total_cost, fees, timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, [
            fill.order_id,
            fill.session_slug,
            fill.token_id,
            fill.side,
            fill.filled_shares,
            fill.avg_price,
            fill.total_cost,
            fill.fees,
            fill.timestamp,
        ])

    def get_trades(self, session_slug: str | None = None, limit: int = 100) -> list[dict]:
        assert self._conn is not None
        if session_slug:
            rows = self._conn.execute(
                "SELECT * FROM trades WHERE session_slug = ? ORDER BY timestamp DESC LIMIT ?",
                [session_slug, limit],
            ).fetchall()
        else:
            rows = self._conn.execute(
                "SELECT * FROM trades ORDER BY timestamp DESC LIMIT ?", [limit],
            ).fetchall()
        cols = [d[0] for d in self._conn.description]  # type: ignore
        return [dict(zip(cols, row)) for row in rows]

    # ── Price snapshots ───────────────────────────────────────

    def save_price_snapshot(
        self,
        session_slug: str,
        token_id: str,
        mid_price: float,
        best_bid: float,
        best_ask: float,
        spread: float,
        anchor_price: float,
    ) -> None:
        assert self._conn is not None
        self._conn.execute("""
            INSERT INTO price_snapshots
            (session_slug, token_id, mid_price, best_bid, best_ask, spread, anchor_price, timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?, current_timestamp)
        """, [session_slug, token_id, mid_price, best_bid, best_ask, spread, anchor_price])

    def get_price_snapshots(self, session_slug: str, limit: int = 300) -> list[dict]:
        assert self._conn is not None
        rows = self._conn.execute(
            "SELECT * FROM price_snapshots WHERE session_slug = ? ORDER BY timestamp DESC LIMIT ?",
            [session_slug, limit],
        ).fetchall()
        cols = [d[0] for d in self._conn.description]  # type: ignore
        return [dict(zip(cols, row)) for row in rows]

    # ── Errors ────────────────────────────────────────────────

    def save_error(self, session_slug: str, error_type: str, message: str, context: dict | None = None) -> None:
        assert self._conn is not None
        self._conn.execute("""
            INSERT INTO errors (session_slug, error_type, message, context)
            VALUES (?, ?, ?, ?)
        """, [session_slug, error_type, message, json.dumps(context or {})])

    # ── PnL aggregation ──────────────────────────────────────

    def get_total_pnl(self) -> dict:
        assert self._conn is not None
        row = self._conn.execute("""
            SELECT
                COALESCE(SUM(total_pnl), 0) as total_pnl,
                COALESCE(SUM(trade_pnl), 0) as total_trade_pnl,
                COALESCE(SUM(settlement_pnl), 0) as total_settlement_pnl,
                COUNT(*) as total_sessions,
                COUNT(CASE WHEN total_pnl > 0 THEN 1 END) as winning_sessions,
                COUNT(CASE WHEN total_pnl < 0 THEN 1 END) as losing_sessions
            FROM sessions
            WHERE state IN ('settled', 'closing')
        """).fetchone()
        if not row:
            return {"total_pnl": 0, "total_sessions": 0}
        return {
            "total_pnl": round(row[0], 6),
            "total_trade_pnl": round(row[1], 6),
            "total_settlement_pnl": round(row[2], 6),
            "total_sessions": row[3],
            "winning_sessions": row[4],
            "losing_sessions": row[5],
        }

    def get_recent_pnl(self, n: int = 10) -> list[dict]:
        assert self._conn is not None
        rows = self._conn.execute("""
            SELECT slug, state, trade_pnl, settlement_pnl, total_pnl, settlement_outcome
            FROM sessions
            WHERE state IN ('settled', 'closing')
            ORDER BY start_epoch DESC
            LIMIT ?
        """, [n]).fetchall()
        cols = ["slug", "state", "trade_pnl", "settlement_pnl", "total_pnl", "settlement_outcome"]
        return [dict(zip(cols, row)) for row in rows]

    # ── P0-3: Position recovery on restart ────────────────────

    async def restore_positions(self, tracker) -> None:
        """Restore open positions from DuckDB trades for sessions not yet settled.

        Replays BUY/SELL fills for any session in 'active' or 'closing' state.
        """
        assert self._conn is not None
        rows = self._conn.execute("""
            SELECT t.token_id, t.side, t.filled_shares, t.avg_price, t.total_cost,
                   t.order_id, t.session_slug, t.timestamp
            FROM trades t
            JOIN sessions s ON t.session_slug = s.slug
            WHERE s.state IN ('active', 'closing')
            ORDER BY t.timestamp ASC
        """).fetchall()

        if not rows:
            logger.info("No open positions to restore")
            return

        restored = 0
        for row in rows:
            token_id, side, filled_shares, avg_price, total_cost, order_id, session_slug, ts = row
            fill = LiveFill(
                order_id=order_id or "",
                token_id=token_id,
                side=side,
                filled_shares=filled_shares,
                avg_price=avg_price,
                total_cost=total_cost,
                timestamp=str(ts) if ts else "",
                session_slug=session_slug,
            )
            tracker.apply_fill(fill)
            restored += 1

        logger.info("Restored %d trade fills → positions: %s", restored, tracker.positions)
