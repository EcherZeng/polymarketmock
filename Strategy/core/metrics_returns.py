"""Returns metrics — total return, annualized return, duration helper."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


# ── Result container ─────────────────────────────────────────────────────────


@dataclass
class ReturnsMetrics:
    """Intermediate results from returns analysis."""

    total_pnl: float = 0.0
    total_return_pct: float = 0.0
    annualized_return: float = 0.0
    duration_secs: float = 0.0


# ── Helpers ──────────────────────────────────────────────────────────────────


def duration_seconds(equity_curve: list[dict]) -> float:
    """Compute duration in seconds from equity curve timestamps."""
    if len(equity_curve) < 2:
        return 0.0
    try:
        t0 = datetime.fromisoformat(equity_curve[0]["timestamp"])
        t1 = datetime.fromisoformat(equity_curve[-1]["timestamp"])
        return (t1 - t0).total_seconds()
    except Exception:
        return 0.0


# ── Main computation ─────────────────────────────────────────────────────────


def compute_returns_metrics(
    initial_balance: float,
    final_equity: float,
    equity_curve: list[dict],
) -> ReturnsMetrics:
    """Compute return-level metrics."""
    rm = ReturnsMetrics()
    rm.total_pnl = round(final_equity - initial_balance, 6)
    rm.total_return_pct = round((final_equity - initial_balance) / initial_balance, 6) if initial_balance else 0.0

    rm.duration_secs = duration_seconds(equity_curve)
    if rm.duration_secs > 0:
        annual_factor = 365 * 24 * 3600 / rm.duration_secs
        rm.annualized_return = round(rm.total_return_pct * annual_factor, 4)
    else:
        rm.annualized_return = 0.0

    return rm
