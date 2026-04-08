"""Risk metrics — drawdown, volatility, Sharpe/Sortino/Calmar ratios."""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime


# ── Result container ─────────────────────────────────────────────────────────


@dataclass
class RiskMetrics:
    """Intermediate results from risk analysis."""

    max_drawdown: float = 0.0
    max_drawdown_duration: float = 0.0
    volatility: float = 0.0
    downside_deviation: float = 0.0
    sharpe_ratio: float = 0.0
    sortino_ratio: float = 0.0
    calmar_ratio: float = 0.0


# ── Helpers ──────────────────────────────────────────────────────────────────


def _max_drawdown(equities: list[float]) -> tuple[float, float]:
    """Return (max_drawdown_pct, max_drawdown_duration_in_ticks)."""
    if not equities:
        return 0.0, 0.0

    peak = equities[0]
    max_dd = 0.0
    max_dd_dur = 0.0
    dd_start = 0

    for i, eq in enumerate(equities):
        if eq > peak:
            peak = eq
            dd_start = i
        dd = (peak - eq) / peak if peak > 0 else 0.0
        if dd > max_dd:
            max_dd = dd
            max_dd_dur = float(i - dd_start)

    return round(max_dd, 6), max_dd_dur


def _compute_returns(equities: list[float]) -> list[float]:
    """Compute simple returns from equity series."""
    if len(equities) < 2:
        return []
    returns: list[float] = []
    for i in range(1, len(equities)):
        if equities[i - 1] != 0:
            returns.append((equities[i] - equities[i - 1]) / equities[i - 1])
        else:
            returns.append(0.0)
    return returns


def _std(values: list[float]) -> float:
    """Standard deviation (sample)."""
    if len(values) < 2:
        return 0.0
    mean = sum(values) / len(values)
    variance = sum((v - mean) ** 2 for v in values) / (len(values) - 1)
    return math.sqrt(variance)


# ── Drawdown curve & events (public API) ─────────────────────────────────────


def compute_drawdown_curve(equity_curve: list[dict]) -> list[dict]:
    """Compute drawdown percentage at each equity curve point."""
    result: list[dict] = []
    peak = 0.0
    for pt in equity_curve:
        eq = pt["equity"]
        if eq > peak:
            peak = eq
        dd_pct = round((peak - eq) / peak, 6) if peak > 0 else 0.0
        result.append({"timestamp": pt["timestamp"], "drawdown_pct": dd_pct})
    return result


def compute_drawdown_events(equity_curve: list[dict]) -> list[dict]:
    """Extract individual drawdown episodes from equity curve.

    Each event captures: peak → trough → recovery.
    Returns list of dicts (JSON-serialisable).
    """
    if len(equity_curve) < 2:
        return []

    events: list[dict] = []
    peak = equity_curve[0]["equity"]
    peak_ts = equity_curve[0]["timestamp"]
    trough = peak
    trough_ts = peak_ts
    in_drawdown = False

    for pt in equity_curve[1:]:
        eq = pt["equity"]
        ts = pt["timestamp"]

        if eq >= peak:
            # Recovery or new high
            if in_drawdown and trough < peak:
                dd_pct = round((peak - trough) / peak, 6) if peak > 0 else 0.0
                start_dt = datetime.fromisoformat(peak_ts)
                trough_dt = datetime.fromisoformat(trough_ts)
                recovery_dt = datetime.fromisoformat(ts)
                events.append({
                    "start_time": peak_ts,
                    "trough_time": trough_ts,
                    "recovery_time": ts,
                    "peak_equity": round(peak, 6),
                    "trough_equity": round(trough, 6),
                    "drawdown_pct": dd_pct,
                    "duration_seconds": (recovery_dt - start_dt).total_seconds(),
                    "recovery_seconds": (recovery_dt - trough_dt).total_seconds(),
                })
            peak = eq
            peak_ts = ts
            trough = eq
            trough_ts = ts
            in_drawdown = False
        else:
            in_drawdown = True
            if eq < trough:
                trough = eq
                trough_ts = ts

    # Handle unrecovered drawdown at end
    if in_drawdown and trough < peak:
        dd_pct = round((peak - trough) / peak, 6) if peak > 0 else 0.0
        start_dt = datetime.fromisoformat(peak_ts)
        trough_dt = datetime.fromisoformat(trough_ts)
        end_dt = datetime.fromisoformat(equity_curve[-1]["timestamp"])
        events.append({
            "start_time": peak_ts,
            "trough_time": trough_ts,
            "recovery_time": None,
            "peak_equity": round(peak, 6),
            "trough_equity": round(trough, 6),
            "drawdown_pct": dd_pct,
            "duration_seconds": (end_dt - start_dt).total_seconds(),
            "recovery_seconds": None,
        })

    # Sort by drawdown magnitude descending
    events.sort(key=lambda e: e["drawdown_pct"], reverse=True)
    return events


# ── Main computation ─────────────────────────────────────────────────────────


def compute_risk_metrics(
    equity_curve: list[dict],
    initial_balance: float,
    duration_secs: float,
    annualized_return: float,
) -> RiskMetrics:
    """Compute all risk-related metrics from equity curve."""
    rm = RiskMetrics()
    equities = [pt["equity"] for pt in equity_curve] if equity_curve else [initial_balance]

    # Max drawdown
    dd_result = _max_drawdown(equities)
    rm.max_drawdown = dd_result[0]
    rm.max_drawdown_duration = dd_result[1]

    # Returns series for Sharpe/Sortino
    returns = _compute_returns(equities)

    if len(returns) > 1:
        mean_r = sum(returns) / len(returns)
        std_r = _std(returns)
        rm.volatility = round(std_r, 6)

        # Annualization factor based on actual sampling frequency
        if duration_secs > 0:
            samples_per_year = len(returns) * (365 * 24 * 3600 / duration_secs)
        else:
            samples_per_year = 365 * 24 * 3600  # fallback: 1s per sample

        if std_r > 0:
            rm.sharpe_ratio = round(mean_r / std_r * math.sqrt(samples_per_year), 4)
        else:
            rm.sharpe_ratio = 0.0

        # Sortino
        downside = [r for r in returns if r < 0]
        downside_std = _std(downside) if downside else 0.0
        rm.downside_deviation = round(downside_std, 6)
        if downside_std > 0:
            rm.sortino_ratio = round(mean_r / downside_std * math.sqrt(samples_per_year), 4)
        else:
            rm.sortino_ratio = 0.0

        # Calmar
        if rm.max_drawdown > 0:
            rm.calmar_ratio = round(annualized_return / rm.max_drawdown, 4)
        else:
            rm.calmar_ratio = 0.0

    return rm
