"""Evaluator — computes all backtest metrics from trades and equity curve.

Sub-modules (split for maintainability):
  core/metrics_returns.py — total_return, annualized_return, duration
  core/metrics_risk.py    — drawdown, volatility, sharpe/sortino/calmar
  core/metrics_trade.py   — win_rate, cost_basis, settlement split, profit_factor
"""

from __future__ import annotations

from core.metrics_returns import compute_returns_metrics
from core.metrics_risk import (
    compute_drawdown_curve,
    compute_drawdown_events,
    compute_risk_metrics,
)
from core.metrics_trade import compute_trade_metrics
from core.types import BacktestSession, EvaluationMetrics


def evaluate(session: BacktestSession) -> EvaluationMetrics:
    """Compute full evaluation metrics for a completed backtest session."""
    m = EvaluationMetrics()

    # ── Returns ──────────────────────────────────────────────────────────────
    ret = compute_returns_metrics(
        initial_balance=session.initial_balance,
        final_equity=session.final_equity,
        equity_curve=session.equity_curve,
    )
    m.total_pnl = ret.total_pnl
    m.total_return_pct = ret.total_return_pct
    m.annualized_return = ret.annualized_return

    # ── Trade stats ──────────────────────────────────────────────────────────
    tm = compute_trade_metrics(
        trades=session.trades,
        final_positions=session.final_positions,
        settlement_result=session.settlement_result,
    )
    m.total_trades = tm.total_trades
    m.buy_count = tm.buy_count
    m.sell_count = tm.sell_count
    m.win_rate = tm.win_rate
    m.best_trade = tm.best_trade
    m.worst_trade = tm.worst_trade
    m.avg_win = tm.avg_win
    m.avg_loss = tm.avg_loss
    m.profit_factor = tm.profit_factor
    m.avg_slippage = tm.avg_slippage
    m.trade_pnl = tm.trade_pnl_total
    m.settlement_pnl = tm.settlement_pnl_total
    m.hold_to_settlement_ratio = tm.hold_to_settlement_ratio
    m.avg_entry_price = tm.avg_entry_price
    m.expected_value = tm.expected_value

    # ── Risk ─────────────────────────────────────────────────────────────────
    risk = compute_risk_metrics(
        equity_curve=session.equity_curve,
        initial_balance=session.initial_balance,
        duration_secs=ret.duration_secs,
        annualized_return=ret.annualized_return,
    )
    m.max_drawdown = risk.max_drawdown
    m.max_drawdown_duration = risk.max_drawdown_duration
    m.volatility = risk.volatility
    m.downside_deviation = risk.downside_deviation
    m.sharpe_ratio = risk.sharpe_ratio
    m.sortino_ratio = risk.sortino_ratio
    m.calmar_ratio = risk.calmar_ratio

    return m


# Re-export public API so existing imports keep working:
#   from core.evaluator import evaluate, compute_drawdown_curve, compute_drawdown_events
__all__ = ["evaluate", "compute_drawdown_curve", "compute_drawdown_events"]
