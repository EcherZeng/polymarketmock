"""Data store — DuckDB for trades/sessions + in-memory cache for snapshots."""

from __future__ import annotations

import json
import logging
from collections import deque
from datetime import datetime, timezone
from pathlib import Path

import duckdb

from config import settings
from models.types import LiveFill, SessionInfo, SessionResult, SessionState

logger = logging.getLogger(__name__)

_SNAPSHOT_CAP = 300


class DataStore:

    def __init__(self, data_dir: Path | None = None) -> None:
        self._data_dir = data_dir or settings.data_dir
        self._data_dir.mkdir(parents=True, exist_ok=True)
        self._db_path = self._data_dir / "trade.duckdb"
        self._conn: duckdb.DuckDBPyConnection | None = None
        # In-memory price snapshot cache: slug → deque of dicts
        self._snapshots: dict[str, deque[dict]] = {}

    async def start(self) -> None:
        self._conn = duckdb.connect(str(self._db_path))
        self._create_tables()
        logger.info("DataStore started: %s", self._db_path)

    async def stop(self) -> None:
        self._snapshots.clear()
        if self._conn:
            self._conn.close()
            self._conn = None

    def _create_tables(self) -> None:
        assert self._conn is not None
        self._conn.execute("CREATE SEQUENCE IF NOT EXISTS trade_seq START 1")
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
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_trades_slug ON trades(session_slug)"
        )

    # ── Sessions (DuckDB — write twice: create + settle) ──────

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

    def settle_session(self, result: SessionResult) -> None:
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
        # Session done — drop its snapshot cache
        self._snapshots.pop(result.session.slug, None)

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

    # ── Trades (DuckDB) ──────────────────────────────────────

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

    # ── Price snapshots (in-memory) ───────────────────────────

    def push_snapshot(self, slug: str, token_id: str, mid_price: float,
                      best_bid: float, best_ask: float, spread: float,
                      anchor_price: float) -> None:
        buf = self._snapshots.get(slug)
        if buf is None:
            buf = deque(maxlen=_SNAPSHOT_CAP)
            self._snapshots[slug] = buf
        buf.append({
            "token_id": token_id,
            "mid_price": mid_price,
            "best_bid": best_bid,
            "best_ask": best_ask,
            "spread": spread,
            "anchor_price": anchor_price,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

    def get_snapshots(self, slug: str) -> list[dict]:
        buf = self._snapshots.get(slug)
        return list(buf) if buf else []

    def clear_snapshots(self, slug: str) -> None:
        self._snapshots.pop(slug, None)

    # ── PnL aggregation ──────────────────────────────────────

    def get_total_pnl(self) -> dict:
        assert self._conn is not None
        row = self._conn.execute("""
            SELECT
                COALESCE(SUM(total_pnl), 0),
                COALESCE(SUM(trade_pnl), 0),
                COALESCE(SUM(settlement_pnl), 0),
                COUNT(*),
                COUNT(CASE WHEN total_pnl > 0 THEN 1 END),
                COUNT(CASE WHEN total_pnl < 0 THEN 1 END)
            FROM sessions WHERE state = 'settled'
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
            FROM sessions WHERE state = 'settled'
            ORDER BY start_epoch DESC LIMIT ?
        """, [n]).fetchall()
        cols = ["slug", "state", "trade_pnl", "settlement_pnl", "total_pnl", "settlement_outcome"]
        return [dict(zip(cols, row)) for row in rows]

    # ── Position recovery on restart ──────────────────────────

    def get_unsettled_fills(self) -> list[LiveFill]:
        """Return fills for sessions not yet settled (for position recovery)."""
        assert self._conn is not None
        rows = self._conn.execute("""
            SELECT t.token_id, t.side, t.filled_shares, t.avg_price, t.total_cost,
                   t.order_id, t.session_slug, t.timestamp
            FROM trades t
            JOIN sessions s ON t.session_slug = s.slug
            WHERE s.state NOT IN ('settled')
            ORDER BY t.timestamp ASC
        """).fetchall()
        return [
            LiveFill(
                order_id=row[5] or "",
                token_id=row[0],
                side=row[1],
                filled_shares=row[2],
                avg_price=row[3],
                total_cost=row[4],
                timestamp=str(row[7]) if row[7] else "",
                session_slug=row[6],
            )
            for row in rows
        ]
