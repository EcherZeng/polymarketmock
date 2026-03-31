"""Evaluator — computes all backtest metrics from trades and equity curve."""

from __future__ import annotations

import math
from datetime import datetime

from core.types import BacktestSession, DrawdownEvent, EvaluationMetrics, FillInfo


def evaluate(session: BacktestSession) -> EvaluationMetrics:
    """Compute full evaluation metrics for a completed backtest session."""
    trades = session.trades
    equity_curve = session.equity_curve
    initial = session.initial_balance
    final = session.final_equity

    m = EvaluationMetrics()

    # ── Returns ──────────────────────────────────────────────────────────────

    m.total_pnl = round(final - initial, 6)
    m.total_return_pct = round((final - initial) / initial * 100, 4) if initial else 0.0

    # Duration for annualization
    duration_secs = _duration_seconds(equity_curve)
    if duration_secs > 0:
        annual_factor = 365 * 24 * 3600 / duration_secs
        m.annualized_return = round(m.total_return_pct * annual_factor, 4)
    else:
        m.annualized_return = 0.0

    # ── Trade stats ──────────────────────────────────────────────────────────

    m.total_trades = len(trades)
    m.buy_count = sum(1 for t in trades if t.side == "BUY")
    m.sell_count = sum(1 for t in trades if t.side == "SELL")

    # PnL per round trip (simplified: each SELL after BUY)
    trade_pnls = _compute_trade_pnls(trades)

    winners = [p for p in trade_pnls if p > 0]
    losers = [p for p in trade_pnls if p < 0]

    if trade_pnls:
        m.win_rate = round(len(winners) / len(trade_pnls) * 100, 2)
        m.best_trade = round(max(trade_pnls), 6) if trade_pnls else 0.0
        m.worst_trade = round(min(trade_pnls), 6) if trade_pnls else 0.0
    if winners:
        m.avg_win = round(sum(winners) / len(winners), 6)
    if losers:
        m.avg_loss = round(sum(losers) / len(losers), 6)

    # Profit factor
    total_wins = sum(winners)
    total_losses = abs(sum(losers))
    m.profit_factor = round(total_wins / total_losses, 4) if total_losses > 0 else (
        9999.0 if total_wins > 0 else 0.0
    )

    # Average slippage
    slippages = [t.slippage_pct for t in trades if t.slippage_pct != 0]
    m.avg_slippage = round(sum(slippages) / len(slippages), 4) if slippages else 0.0

    # ── Risk ─────────────────────────────────────────────────────────────────

    equities = [pt["equity"] for pt in equity_curve] if equity_curve else [initial]

    # Max drawdown
    dd_result = _max_drawdown(equities)
    m.max_drawdown = dd_result[0]
    m.max_drawdown_duration = dd_result[1]

    # Returns series for Sharpe/Sortino
    returns = _compute_returns(equities)

    if len(returns) > 1:
        mean_r = sum(returns) / len(returns)
        std_r = _std(returns)
        m.volatility = round(std_r, 6)

        # Annualization factor — assume each sample is 1 second
        N = 365 * 24 * 3600  # annualize from per-second
        if std_r > 0:
            m.sharpe_ratio = round(mean_r / std_r * math.sqrt(N), 4)
        else:
            m.sharpe_ratio = 0.0

        # Sortino
        downside = [r for r in returns if r < 0]
        downside_std = _std(downside) if downside else 0.0
        m.downside_deviation = round(downside_std, 6)
        if downside_std > 0:
            m.sortino_ratio = round(mean_r / downside_std * math.sqrt(N), 4)
        else:
            m.sortino_ratio = 0.0

        # Calmar
        if m.max_drawdown > 0:
            m.calmar_ratio = round(m.annualized_return / m.max_drawdown, 4)
        else:
            m.calmar_ratio = 0.0

    # ── BTC prediction market metrics ─────────────────────────────────────────

    settlement_result = session.settlement_result
    if settlement_result:
        # Settlement PnL: (settlement_price - avg_cost) * held_amount for positions still held
        cost_basis_map, held_map = _compute_cost_basis(trades)
        settlement_pnl = 0.0
        total_bought = 0.0
        total_held_at_end = 0.0

        for tid, qty in session.final_positions.items():
            if qty > 0:
                settle_price = settlement_result.get(tid, 0.0)
                avg_cost = cost_basis_map.get(tid, 0.0)
                settlement_pnl += (settle_price - avg_cost) * qty
                total_held_at_end += qty

        # Trade PnL: sum of realised PnL from sells during backtest
        m.trade_pnl = round(sum(trade_pnls), 6) if trade_pnls else 0.0
        m.settlement_pnl = round(settlement_pnl, 6)

        # Total bought across all trades
        for t in trades:
            if t.side == "BUY":
                total_bought += t.filled_amount

        # Hold-to-settlement ratio
        if total_bought > 0:
            m.hold_to_settlement_ratio = round(total_held_at_end / total_bought * 100, 2)
        else:
            m.hold_to_settlement_ratio = 0.0

        # Average entry price (weighted across all BUY trades)
        total_cost_all = sum(t.avg_price * t.filled_amount for t in trades if t.side == "BUY")
        total_qty_all = sum(t.filled_amount for t in trades if t.side == "BUY")
        m.avg_entry_price = round(total_cost_all / total_qty_all, 6) if total_qty_all > 0 else 0.0

        # Expected value per share: P(win) * (1 - entry_price) - P(lose) * entry_price
        # In binary market: if entry_price < 1.0, EV = settle_price - entry_price (per share)
        if m.avg_entry_price > 0:
            # Weighted average settlement price across held tokens
            if total_held_at_end > 0:
                w_settle = sum(
                    settlement_result.get(tid, 0.0) * qty
                    for tid, qty in session.final_positions.items()
                    if qty > 0
                ) / total_held_at_end
            else:
                w_settle = 0.0
            m.expected_value = round(w_settle - m.avg_entry_price, 6)
        else:
            m.expected_value = 0.0

    return m


def compute_drawdown_curve(equity_curve: list[dict]) -> list[dict]:
    """Compute drawdown percentage at each equity curve point."""
    result: list[dict] = []
    peak = 0.0
    for pt in equity_curve:
        eq = pt["equity"]
        if eq > peak:
            peak = eq
        dd_pct = round((peak - eq) / peak * 100, 4) if peak > 0 else 0.0
        result.append({"timestamp": pt["timestamp"], "drawdown_pct": dd_pct})
    return result


# ── Helpers ──────────────────────────────────────────────────────────────────


def _compute_cost_basis(trades: list[FillInfo]) -> tuple[dict[str, float], dict[str, float]]:
    """Compute cost basis and held quantity per token from trade history.

    Returns (cost_basis_map, held_map).
    """
    cost_basis: dict[str, float] = {}
    held: dict[str, float] = {}

    for t in trades:
        tid = t.token_id
        if t.side == "BUY":
            prev_held = held.get(tid, 0)
            prev_cost = cost_basis.get(tid, 0)
            total_held = prev_held + t.filled_amount
            if total_held > 0:
                cost_basis[tid] = (prev_cost * prev_held + t.avg_price * t.filled_amount) / total_held
            held[tid] = total_held
        elif t.side == "SELL":
            prev_held = held.get(tid, 0)
            held[tid] = max(0, prev_held - t.filled_amount)

    return cost_basis, held


def _duration_seconds(equity_curve: list[dict]) -> float:
    """Compute duration in seconds from equity curve timestamps."""
    if len(equity_curve) < 2:
        return 0.0
    try:
        t0 = datetime.fromisoformat(equity_curve[0]["timestamp"])
        t1 = datetime.fromisoformat(equity_curve[-1]["timestamp"])
        return (t1 - t0).total_seconds()
    except Exception:
        return 0.0


def _compute_trade_pnls(trades: list[FillInfo]) -> list[float]:
    """Compute PnL for each sell trade (cost basis from preceding buys).

    Uses weighted average cost basis per token.
    """
    cost_basis: dict[str, float] = {}  # token_id → avg cost per share
    held: dict[str, float] = {}  # token_id → shares
    pnls: list[float] = []

    for t in trades:
        tid = t.token_id
        if t.side == "BUY":
            prev_held = held.get(tid, 0)
            prev_cost = cost_basis.get(tid, 0)
            total_held = prev_held + t.filled_amount
            if total_held > 0:
                cost_basis[tid] = (prev_cost * prev_held + t.avg_price * t.filled_amount) / total_held
            held[tid] = total_held
        elif t.side == "SELL":
            avg_cost = cost_basis.get(tid, 0)
            pnl = (t.avg_price - avg_cost) * t.filled_amount
            pnls.append(round(pnl, 6))
            prev_held = held.get(tid, 0)
            held[tid] = max(0, prev_held - t.filled_amount)

    return pnls


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
        dd = (peak - eq) / peak * 100 if peak > 0 else 0.0
        if dd > max_dd:
            max_dd = dd
            max_dd_dur = float(i - dd_start)

    return round(max_dd, 4), max_dd_dur


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
    """Standard deviation."""
    if len(values) < 2:
        return 0.0
    mean = sum(values) / len(values)
    variance = sum((v - mean) ** 2 for v in values) / (len(values) - 1)
    return math.sqrt(variance)


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
                dd_pct = round((peak - trough) / peak * 100, 4) if peak > 0 else 0.0
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
        dd_pct = round((peak - trough) / peak * 100, 4) if peak > 0 else 0.0
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
