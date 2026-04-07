"""Result digest — extracts compact summaries from BacktestSession for AI consumption.

Full BacktestSession contains ~200KB of time-series data (equity_curve, price_curve, etc.).
AI only needs config + metrics + trade summary (~2KB), achieving ~100:1 compression.
"""

from __future__ import annotations

from dataclasses import asdict

from core.types import BacktestSession, EvaluationMetrics


def digest_session(session: BacktestSession) -> dict:
    """Extract a compact AI-friendly summary from a BacktestSession.

    Returns ~2KB dict with: config, metrics, trade_summary, drawdown_summary.
    All time-series curves are discarded.
    """
    metrics = session.metrics
    metrics_dict = asdict(metrics) if isinstance(metrics, EvaluationMetrics) else metrics

    # Trade summary (compact, no per-trade details)
    trade_summary = {
        "total_trades": metrics_dict.get("total_trades", 0),
        "buy_count": metrics_dict.get("buy_count", 0),
        "sell_count": metrics_dict.get("sell_count", 0),
        "win_rate": metrics_dict.get("win_rate", 0.0),
        "avg_slippage": metrics_dict.get("avg_slippage", 0.0),
    }

    # Drawdown summary (only event count + worst)
    drawdown_summary = {
        "event_count": len(session.drawdown_events),
        "max_drawdown_pct": metrics_dict.get("max_drawdown", 0.0),
        "max_drawdown_duration_s": metrics_dict.get("max_drawdown_duration", 0.0),
    }

    return {
        "session_id": session.session_id,
        "slug": session.slug,
        "status": session.status,
        "initial_balance": session.initial_balance,
        "final_equity": session.final_equity,
        "duration_seconds": session.duration_seconds,
        "config": session.config,
        "metrics": metrics_dict,
        "trade_summary": trade_summary,
        "drawdown_summary": drawdown_summary,
        "settlement_result": session.settlement_result,
    }


def digest_for_ai_table(sessions: list[dict], param_keys: list[str]) -> list[dict]:
    """Build a flat table of {params + key metrics} for AI analysis.

    Each row contains only the varied parameter values + core metrics.
    This is the most compact representation for LLM context.
    """
    rows: list[dict] = []
    for d in sessions:
        row: dict = {}
        # Selected config params
        config = d.get("config", {})
        for key in param_keys:
            if key in config:
                row[key] = config[key]
        # Core metrics
        m = d.get("metrics", {})
        row["total_return_pct"] = m.get("total_return_pct", 0.0)
        row["sharpe_ratio"] = m.get("sharpe_ratio", 0.0)
        row["win_rate"] = m.get("win_rate", 0.0)
        row["max_drawdown"] = m.get("max_drawdown", 0.0)
        row["profit_factor"] = m.get("profit_factor", 0.0)
        row["total_trades"] = m.get("total_trades", 0)
        row["avg_slippage"] = m.get("avg_slippage", 0.0)
        row["total_pnl"] = m.get("total_pnl", 0.0)
        rows.append(row)
    return rows
