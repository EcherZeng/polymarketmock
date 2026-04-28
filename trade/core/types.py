"""Core data types for the live trading engine."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum

# ── Slug parsing ─────────────────────────────────────────────────────────────

_BTC_SLUG_RE = re.compile(r"^btc-updown-(\d+)m-(\d{10})$")


def parse_slug_window(slug: str) -> tuple[int, int, int] | None:
    """Extract (start_epoch, end_epoch, interval_min) from a BTC slug.

    Returns None if the slug doesn't match the expected format.
    """
    m = _BTC_SLUG_RE.match(slug)
    if not m:
        return None
    interval_min = int(m.group(1))
    epoch = int(m.group(2))
    return epoch, epoch + interval_min * 60, interval_min


def slug_to_iso(slug: str) -> tuple[str, str] | None:
    """Extract (start_iso, end_iso) from a BTC slug."""
    parsed = parse_slug_window(slug)
    if not parsed:
        return None
    start_epoch, end_epoch, _ = parsed
    start_dt = datetime.fromtimestamp(start_epoch, tz=timezone.utc)
    end_dt = datetime.fromtimestamp(end_epoch, tz=timezone.utc)
    return start_dt.isoformat(), end_dt.isoformat()


# ── Enums ────────────────────────────────────────────────────────────────────


class SessionState(str, Enum):
    """Lifecycle state for a trading session (one market round)."""
    DISCOVERED = "discovered"   # Scanner found upcoming market
    PREPARING = "preparing"     # WS pre-connected, collecting initial data
    ACTIVE = "active"           # Within trading window
    CLOSING = "closing"         # Near expiry, evaluating close
    SETTLED = "settled"         # Market resolved, PnL finalised
    SKIPPED = "skipped"         # Strategy decided to skip this session
    ERROR = "error"             # Unrecoverable error during session


class ErrorAction(str, Enum):
    """Strategy decision on how to handle an error."""
    RETRY = "retry"
    CANCEL = "cancel"       # Cancel current action, keep session alive
    STOP = "stop"           # Stop trading for this session


# ── Data classes ─────────────────────────────────────────────────────────────


@dataclass
class SessionInfo:
    """Metadata for one BTC market session (e.g. one 15-minute round)."""
    slug: str
    token_ids: list[str]            # [up_token, down_token]
    outcomes: list[str]             # ["Up", "Down"]
    start_epoch: int
    end_epoch: int
    duration_s: int                 # e.g. 900 for 15m
    condition_id: str = ""          # Polymarket condition ID
    question: str = ""              # e.g. "Will BTC go up or down?"


@dataclass
class OrderbookSnapshot:
    """Lightweight orderbook state for one token."""
    token_id: str
    bids: dict[str, float] = field(default_factory=dict)   # price_str → size
    asks: dict[str, float] = field(default_factory=dict)


@dataclass
class TokenMarketData:
    """Live market data for a single token."""
    token_id: str
    mid_price: float = 0.0
    best_bid: float = 0.0
    best_ask: float = 0.0
    spread: float = 0.0
    anchor_price: float = 0.0
    anchor_source: str = ""         # "micro" | "mid" | "last_trade" | "none"
    last_trade_price: float = 0.0
    bid_levels: list[tuple[float, float]] = field(default_factory=list)
    ask_levels: list[tuple[float, float]] = field(default_factory=list)


@dataclass
class LiveMarketContext:
    """Full context delivered to strategy on each market update."""
    timestamp: str                  # ISO 8601 UTC
    session: SessionInfo
    time_remaining_s: float         # seconds until session end

    # Per-token market data
    tokens: dict[str, TokenMarketData] = field(default_factory=dict)

    # Account state
    balance: float = 0.0            # available USDC
    positions: dict[str, float] = field(default_factory=dict)  # token_id → shares
    equity: float = 0.0
    initial_balance: float = 0.0

    # Accumulated history (within this session)
    price_history: dict[str, list[float]] = field(default_factory=dict)
    trade_history: list[dict] = field(default_factory=list)

    # Computed
    session_pnl: float = 0.0
    unrealized_pnl: float = 0.0


@dataclass
class LiveSignal:
    """Trading signal produced by a live strategy."""
    token_id: str
    side: str                       # "BUY" | "SELL"
    amount_usdc: float              # USDC amount to spend (BUY) or shares to sell (SELL)
    limit_price: float | None = None  # if None, use best available price
    reason: str = ""                # human-readable signal reason


@dataclass
class LiveFill:
    """Execution report for a real order."""
    order_id: str
    token_id: str
    side: str                       # "BUY" | "SELL"
    filled_shares: float
    avg_price: float
    total_cost: float               # USDC spent (BUY) or received (SELL)
    timestamp: str                  # ISO 8601 UTC
    session_slug: str = ""
    fees: float = 0.0


@dataclass
class TradeError:
    """Structured error info for strategy error handler."""
    error_type: str                 # "ws_disconnect" | "order_failed" | "api_timeout" | "sdk_error"
    message: str
    has_position: bool              # whether we hold tokens in this session
    context: dict = field(default_factory=dict)


@dataclass
class SessionResult:
    """Final result of one trading session."""
    session: SessionInfo
    state: SessionState
    trades: list[LiveFill] = field(default_factory=list)
    trade_pnl: float = 0.0         # PnL from trades (sell - buy cost)
    settlement_pnl: float = 0.0    # PnL from settlement (winning_shares * $1 - cost)
    total_pnl: float = 0.0
    settlement_outcome: str = ""    # "Up" | "Down" | "" (not yet settled)
    error: str = ""
    start_time: str = ""
    end_time: str = ""
