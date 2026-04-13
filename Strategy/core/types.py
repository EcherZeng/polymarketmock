"""Core data types for the Strategy Backtest Engine."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone


# ── Slug time window ─────────────────────────────────────────────────────────

_BTC_SLUG_RE = re.compile(r"^btc-updown-(\d+)m-(\d+)$")


def parse_slug_window(slug: str) -> tuple[str, str] | None:
    """Extract (start_iso, end_iso) from a slug like ``btc-updown-15m-1775532600``.

    Returns ISO 8601 UTC strings, or *None* if the slug doesn't match the
    expected format.
    """
    m = _BTC_SLUG_RE.match(slug)
    if not m:
        return None
    interval_min = int(m.group(1))
    epoch = int(m.group(2))
    start_dt = datetime.fromtimestamp(epoch, tz=timezone.utc)
    end_dt = datetime.fromtimestamp(epoch + interval_min * 60, tz=timezone.utc)
    return start_dt.isoformat(), end_dt.isoformat()


# ── Param guard ──────────────────────────────────────────────────────────────

def param_active(config: dict, key: str) -> bool:
    """Return True if *key* is present in config (i.e. the user activated it)."""
    return key in config


def btc_trend_enabled(config: dict) -> bool:
    """Return True if BTC trend / momentum filter params are valid.

    Checks:
      - btc_min_momentum is present and > 0
      - btc_trend_window_1 is present and >= 1
      - btc_trend_window_2 is present and >= btc_trend_window_1

    Extensible: add future momentum-related validations here
    (e.g. volume confirmation, slope threshold).
    """
    if not param_active(config, "btc_min_momentum"):
        return False
    min_mom = config.get("btc_min_momentum")
    if min_mom is None or min_mom < 0:
        return False
    w1 = config.get("btc_trend_window_1")
    w2 = config.get("btc_trend_window_2")
    if w1 is None or w2 is None:
        return False
    if w1 < 1 or w2 < 1:
        return False
    if w2 < w1:
        return False
    return True


@dataclass
class Signal:
    """Trading signal produced by a strategy."""

    token_id: str
    side: str  # "BUY" | "SELL"
    amount: float  # target shares
    order_type: str = "MARKET"  # "MARKET" | "LIMIT"
    limit_price: float | None = None
    max_cost: float | None = None  # BUY only: hard cap on total spend (USDC)
    sell_mode: str = "market"  # "market" | "ideal" | "orderbook"
    min_sell_price: float | None = None  # orderbook mode: skip bids below this price


@dataclass
class TokenSnapshot:
    """Market snapshot for a single token at one tick."""

    token_id: str
    mid_price: float
    best_bid: float
    best_ask: float
    spread: float
    anchor_price: float = 0.0  # tiered reference price (micro-price / mid / last_trade)
    anchor_source: str = ""    # "micro" | "mid" | "last_trade" | "none"
    bid_levels: list[tuple[float, float]] = field(default_factory=list)  # [(price, size)]
    ask_levels: list[tuple[float, float]] = field(default_factory=list)


@dataclass
class TickContext:
    """Full market context pushed to the strategy at each tick."""

    timestamp: str  # ISO 8601 UTC
    index: int
    total_ticks: int

    tokens: dict[str, TokenSnapshot] = field(default_factory=dict)

    balance: float = 0.0
    positions: dict[str, float] = field(default_factory=dict)
    equity: float = 0.0
    initial_balance: float = 0.0

    price_history: dict[str, list[float]] = field(default_factory=dict)
    trade_history: list[dict] = field(default_factory=list)


@dataclass
class FillInfo:
    """Fill report after order execution."""

    timestamp: str
    token_id: str
    side: str
    requested_amount: float
    filled_amount: float
    avg_price: float
    total_cost: float
    slippage_pct: float
    balance_after: float
    position_after: float


@dataclass
class ArchiveInfo:
    """Metadata for one archived event."""

    slug: str
    path: str
    files: list[str] = field(default_factory=list)
    size_bytes: int = 0
    time_range: dict = field(default_factory=dict)
    token_ids: list[str] = field(default_factory=list)
    prices_count: int = 0
    orderbooks_count: int = 0
    live_trades_count: int = 0
    source: str = "archive"  # "archive" | "live"


@dataclass
class ArchiveData:
    """All loaded data for one archived event."""

    prices: list[dict] = field(default_factory=list)
    orderbooks: list[dict] = field(default_factory=list)
    ob_deltas: list[dict] = field(default_factory=list)
    live_trades: list[dict] = field(default_factory=list)


@dataclass
class DrawdownEvent:
    """A single drawdown episode (peak → trough → recovery)."""

    start_time: str
    trough_time: str
    recovery_time: str | None = None
    peak_equity: float = 0.0
    trough_equity: float = 0.0
    drawdown_pct: float = 0.0
    duration_seconds: float = 0.0
    recovery_seconds: float | None = None


@dataclass
class EvaluationMetrics:
    """Computed evaluation metrics for a backtest session."""

    # Returns
    total_pnl: float = 0.0
    total_return_pct: float = 0.0
    annualized_return: float = 0.0
    profit_factor: float = 0.0

    # Risk
    max_drawdown: float = 0.0
    max_drawdown_duration: float = 0.0  # ticks (equity curve sample points)
    volatility: float = 0.0
    downside_deviation: float = 0.0

    # Risk-adjusted
    sharpe_ratio: float = 0.0
    sortino_ratio: float = 0.0
    calmar_ratio: float = 0.0

    # Trade stats
    total_trades: int = 0
    win_rate: float = 0.0
    avg_win: float = 0.0
    avg_loss: float = 0.0
    best_trade: float = 0.0
    worst_trade: float = 0.0
    avg_holding_period: float = 0.0
    buy_count: int = 0
    sell_count: int = 0
    avg_slippage: float = 0.0

    # BTC prediction market metrics
    settlement_pnl: float = 0.0
    trade_pnl: float = 0.0
    hold_to_settlement_ratio: float = 0.0
    avg_entry_price: float = 0.0
    expected_value: float = 0.0


@dataclass
class BacktestSession:
    """Result of a single backtest run."""

    session_id: str
    strategy: str
    slug: str
    initial_balance: float
    status: str = "completed"  # "running" | "completed" | "failed"
    created_at: str = ""
    duration_seconds: float = 0.0

    trades: list[FillInfo] = field(default_factory=list)
    equity_curve: list[dict] = field(default_factory=list)  # [{timestamp, equity}]
    drawdown_curve: list[dict] = field(default_factory=list)
    position_curve: list[dict] = field(default_factory=list)
    price_curve: list[dict] = field(default_factory=list)  # [{timestamp, token_id, mid_price, anchor_price, anchor_source}]
    drawdown_events: list[DrawdownEvent] = field(default_factory=list)
    metrics: EvaluationMetrics = field(default_factory=EvaluationMetrics)
    strategy_summary: dict = field(default_factory=dict)
    config: dict = field(default_factory=dict)
    final_equity: float = 0.0
    final_positions: dict[str, float] = field(default_factory=dict)

    # Settlement
    settlement_mode: str = "binary"
    settlement_result: dict[str, float] = field(default_factory=dict)

    # Capital mode
    capital_mode: str = "fixed"  # "fixed" | "cumulative"

    # BTC trend filter result
    btc_trend_info: dict | None = None

    # Slug-derived session window (ISO UTC)
    slug_start: str = ""
    slug_end: str = ""
