"""Core data types for the live trading engine."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum

# ── Slug parsing ─────────────────────────────────────────────────────────────

_BTC_SLUG_RE = re.compile(r"^btc-updown-(\d+)m-(\d{10})$")


def parse_slug_window(slug: str) -> tuple[int, int, int] | None:
    m = _BTC_SLUG_RE.match(slug)
    if not m:
        return None
    interval_min = int(m.group(1))
    epoch = int(m.group(2))
    return epoch, epoch + interval_min * 60, interval_min


def slug_to_iso(slug: str) -> tuple[str, str] | None:
    parsed = parse_slug_window(slug)
    if not parsed:
        return None
    start_epoch, end_epoch, _ = parsed
    start_dt = datetime.fromtimestamp(start_epoch, tz=timezone.utc)
    end_dt = datetime.fromtimestamp(end_epoch, tz=timezone.utc)
    return start_dt.isoformat(), end_dt.isoformat()


# ── Enums ────────────────────────────────────────────────────────────────────


class SessionState(str, Enum):
    PENDING = "pending"       # Discovered or preparing
    ACTIVE = "active"         # Within trading window
    SETTLING = "settling"     # Expired, waiting for resolution
    SETTLED = "settled"       # Market resolved, PnL finalised


# ── Data classes ─────────────────────────────────────────────────────────────


@dataclass
class SessionInfo:
    slug: str
    token_ids: list[str]
    outcomes: list[str]
    start_epoch: int
    end_epoch: int
    duration_s: int
    condition_id: str = ""
    question: str = ""


@dataclass
class OrderbookSnapshot:
    token_id: str
    bids: dict[str, float] = field(default_factory=dict)
    asks: dict[str, float] = field(default_factory=dict)


@dataclass
class TokenMarketData:
    token_id: str
    mid_price: float = 0.0
    best_bid: float = 0.0
    best_ask: float = 0.0
    spread: float = 0.0
    anchor_price: float = 0.0
    anchor_source: str = ""
    last_trade_price: float = 0.0
    bid_levels: list[tuple[float, float]] = field(default_factory=list)
    ask_levels: list[tuple[float, float]] = field(default_factory=list)


@dataclass
class LiveMarketContext:
    timestamp: str
    session: SessionInfo
    time_remaining_s: float
    tokens: dict[str, TokenMarketData] = field(default_factory=dict)
    balance: float = 0.0
    positions: dict[str, float] = field(default_factory=dict)
    btc_trend: dict = field(default_factory=dict)


@dataclass
class LiveSignal:
    token_id: str
    side: str
    amount_usdc: float
    limit_price: float | None = None
    reason: str = ""


@dataclass
class LiveFill:
    order_id: str
    token_id: str
    side: str
    filled_shares: float
    avg_price: float
    total_cost: float
    timestamp: str
    session_slug: str = ""
    fees: float = 0.0


@dataclass
class SessionResult:
    session: SessionInfo
    state: SessionState
    trades: list[LiveFill] = field(default_factory=list)
    trade_pnl: float = 0.0
    settlement_pnl: float = 0.0
    total_pnl: float = 0.0
    settlement_outcome: str = ""
    error: str = ""
