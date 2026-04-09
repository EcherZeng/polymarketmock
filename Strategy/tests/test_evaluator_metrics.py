"""End-to-end evaluator metrics tests (P0-3.3).

Three mock sessions with hand-computed expected values:
1. Simple profitable session (BUY low, SELL high)
2. Losing session with drawdown
3. Mixed session with settlement
"""

from __future__ import annotations

import math

import pytest

from core.evaluator import evaluate
from core.types import BacktestSession, FillInfo


def _fill(
    ts: str, token: str, side: str, amount: float, price: float, slippage: float = 0.0,
) -> FillInfo:
    return FillInfo(
        timestamp=ts,
        token_id=token,
        side=side,
        requested_amount=amount,
        filled_amount=amount,
        avg_price=price,
        total_cost=price * amount,
        slippage_pct=slippage,
        balance_after=0.0,
        position_after=0.0,
    )


def _eq_pt(ts: str, equity: float) -> dict:
    return {"timestamp": ts, "equity": equity}


class TestSession1SimpleProfitable:
    """BUY 10 @ 0.50, SELL 10 @ 0.80.
    initial_balance=100, final_equity=103.
    Duration: 1 hour (3600s), 4 equity samples.
    """

    @pytest.fixture()
    def metrics(self):
        trades = [
            _fill("2025-01-01T00:10:00Z", "T1", "BUY", 10.0, 0.50),
            _fill("2025-01-01T00:50:00Z", "T1", "SELL", 10.0, 0.80),
        ]
        equity_curve = [
            _eq_pt("2025-01-01T00:00:00Z", 100.0),
            _eq_pt("2025-01-01T00:20:00Z", 100.0),  # after buy, equity ~ same
            _eq_pt("2025-01-01T00:40:00Z", 101.5),
            _eq_pt("2025-01-01T01:00:00Z", 103.0),
        ]
        session = BacktestSession(
            session_id="s1", strategy="test", slug="slug1",
            initial_balance=100.0, final_equity=103.0,
            trades=trades, equity_curve=equity_curve,
            final_positions={"T1": 0.0},
            settlement_result={},
        )
        return evaluate(session)

    def test_returns(self, metrics):
        assert metrics.total_pnl == pytest.approx(3.0, abs=1e-4)
        assert metrics.total_return_pct == pytest.approx(0.03, abs=1e-4)

    def test_trade_stats(self, metrics):
        assert metrics.total_trades == 2
        assert metrics.buy_count == 1
        assert metrics.sell_count == 1
        # trade_pnl: (0.80 - 0.50) * 10 = 3.0
        assert metrics.win_rate == 1.0
        assert metrics.avg_win == pytest.approx(3.0, abs=1e-4)
        assert metrics.avg_loss == 0.0  # no losers

    def test_profit_factor(self, metrics):
        # total_wins=3.0, total_losses=0 → capped at 999
        assert metrics.profit_factor == 999.0

    def test_risk(self, metrics):
        # Equity only goes up: 100 → 100 → 101.5 → 103
        assert metrics.max_drawdown == 0.0
        assert metrics.max_drawdown_duration == 0.0

    def test_sharpe_finite(self, metrics):
        # With positive returns and no drawdown, sharpe should be positive
        assert metrics.sharpe_ratio > 0
        assert math.isfinite(metrics.sharpe_ratio)

    def test_annualized_return(self, metrics):
        # duration=3600s, return=0.03
        # annual_factor = 365*24*3600 / 3600 = 8760
        # annualized = 0.03 * 8760 = 262.8
        assert metrics.annualized_return == pytest.approx(262.8, abs=0.1)


class TestSession2LosingWithDrawdown:
    """BUY 20 @ 0.60, SELL 20 @ 0.45.
    initial_balance=100, final_equity=97.
    Equity dips to 94 mid-session.
    Duration: 2 hours.
    """

    @pytest.fixture()
    def metrics(self):
        trades = [
            _fill("2025-01-01T00:15:00Z", "T1", "BUY", 20.0, 0.60),
            _fill("2025-01-01T01:45:00Z", "T1", "SELL", 20.0, 0.45),
        ]
        equity_curve = [
            _eq_pt("2025-01-01T00:00:00Z", 100.0),
            _eq_pt("2025-01-01T00:30:00Z", 99.0),
            _eq_pt("2025-01-01T01:00:00Z", 94.0),   # trough
            _eq_pt("2025-01-01T01:30:00Z", 96.0),
            _eq_pt("2025-01-01T02:00:00Z", 97.0),
        ]
        session = BacktestSession(
            session_id="s2", strategy="test", slug="slug2",
            initial_balance=100.0, final_equity=97.0,
            trades=trades, equity_curve=equity_curve,
            final_positions={"T1": 0.0},
            settlement_result={},
        )
        return evaluate(session)

    def test_returns(self, metrics):
        assert metrics.total_pnl == pytest.approx(-3.0, abs=1e-4)
        assert metrics.total_return_pct == pytest.approx(-0.03, abs=1e-4)

    def test_trade_stats(self, metrics):
        assert metrics.total_trades == 2
        # trade_pnl: (0.45 - 0.60) * 20 = -3.0
        assert metrics.win_rate == 0.0
        assert metrics.avg_loss == pytest.approx(-3.0, abs=1e-4)

    def test_profit_factor_zero(self, metrics):
        # No winners, profit_factor = 0
        assert metrics.profit_factor == 0.0

    def test_max_drawdown(self, metrics):
        # Peak=100, trough=94 → drawdown = 6/100 = 0.06
        assert metrics.max_drawdown == pytest.approx(0.06, abs=1e-4)
        # Duration: peak at index 0, trough at index 2 → 2 ticks
        assert metrics.max_drawdown_duration == 2.0

    def test_sharpe_negative(self, metrics):
        # Losing session → negative Sharpe
        assert metrics.sharpe_ratio < 0

    def test_sortino_negative(self, metrics):
        assert metrics.sortino_ratio < 0

    def test_calmar(self, metrics):
        # calmar = annualized_return / max_drawdown
        if metrics.max_drawdown > 0:
            expected = metrics.annualized_return / metrics.max_drawdown
            assert metrics.calmar_ratio == pytest.approx(expected, abs=0.1)


class TestSession3MixedWithSettlement:
    """BUY 10 @ 0.40 T1, BUY 10 @ 0.70 T2.
    SELL 5 T1 @ 0.55.
    Hold remaining 5 T1 + 10 T2 to settlement.
    T1 settles at 1.0, T2 settles at 0.0.
    initial_balance=100, final_equity=99.
    """

    @pytest.fixture()
    def metrics(self):
        trades = [
            _fill("2025-01-01T00:10:00Z", "T1", "BUY", 10.0, 0.40),
            _fill("2025-01-01T00:20:00Z", "T2", "BUY", 10.0, 0.70),
            _fill("2025-01-01T00:40:00Z", "T1", "SELL", 5.0, 0.55),
        ]
        equity_curve = [
            _eq_pt("2025-01-01T00:00:00Z", 100.0),
            _eq_pt("2025-01-01T00:30:00Z", 100.5),
            _eq_pt("2025-01-01T01:00:00Z", 99.0),
        ]
        session = BacktestSession(
            session_id="s3", strategy="test", slug="slug3",
            initial_balance=100.0, final_equity=99.0,
            trades=trades, equity_curve=equity_curve,
            final_positions={"T1": 5.0, "T2": 10.0},
            settlement_result={"T1": 1.0, "T2": 0.0},
        )
        return evaluate(session)

    def test_returns(self, metrics):
        assert metrics.total_pnl == pytest.approx(-1.0, abs=1e-4)
        assert metrics.total_return_pct == pytest.approx(-0.01, abs=1e-4)

    def test_trade_pnl_breakdown(self, metrics):
        assert metrics.total_trades == 3
        assert metrics.buy_count == 2
        assert metrics.sell_count == 1

    def test_win_rate(self, metrics):
        # trade_pnls from SELL: (0.55 - 0.40) * 5 = 0.75 → win
        # settlement T1: avg_cost=0.40, outstanding=1-1=0? No: buys=1, sells=1 → 0 → fallback 1
        # Actually buys for T1 = 1, sells for T1 = 1, outstanding = 0 → fallback 1
        # settle PnL T1 = (1.0 - 0.40) * 5 / 1 = 3.0 → win
        # settlement T2: buys=1, sells=0, outstanding=1
        # settle PnL T2 = (0.0 - 0.70) * 10 / 1 = -7.0 → loss
        # all_pnls = [0.75, 3.0, -7.0] → 2 winners / 3 total
        assert metrics.win_rate == pytest.approx(2 / 3, abs=0.01)

    def test_profit_factor(self, metrics):
        # total_wins = 0.75 + 3.0 = 3.75
        # total_losses = | -7.0 | = 7.0
        # profit_factor = 3.75 / 7.0 ≈ 0.5357
        assert metrics.profit_factor == pytest.approx(3.75 / 7.0, abs=0.01)

    def test_settlement_metrics(self, metrics):
        # settlement_pnl = (1.0-0.40)*5 + (0.0-0.70)*10 = 3.0 + (-7.0) = -4.0
        assert metrics.settlement_pnl == pytest.approx(-4.0, abs=0.1)
        # trade_pnl from sells = 0.75
        assert metrics.trade_pnl == pytest.approx(0.75, abs=0.01)

    def test_hold_to_settlement_ratio(self, metrics):
        # total_held_at_end = 5+10 = 15, total_bought = 10+10 = 20
        assert metrics.hold_to_settlement_ratio == pytest.approx(15 / 20, abs=0.01)

    def test_avg_entry_price(self, metrics):
        # (0.40*10 + 0.70*10) / 20 = 11.0/20 = 0.55
        assert metrics.avg_entry_price == pytest.approx(0.55, abs=0.01)

    def test_sharpe_sortino_finite(self, metrics):
        assert math.isfinite(metrics.sharpe_ratio)
        assert math.isfinite(metrics.sortino_ratio)

    def test_volatility_positive(self, metrics):
        # Equity curve is not flat → volatility > 0
        assert metrics.volatility > 0


class TestAnnualizationSanity:
    """Verify samples_per_year doesn't overflow for extreme durations."""

    def test_very_short_duration(self):
        """10 second session with 3 equity points."""
        trades = [_fill("2025-01-01T00:00:05Z", "T1", "BUY", 1.0, 0.5)]
        equity_curve = [
            _eq_pt("2025-01-01T00:00:00Z", 100.0),
            _eq_pt("2025-01-01T00:00:05Z", 99.5),
            _eq_pt("2025-01-01T00:00:10Z", 100.2),
        ]
        session = BacktestSession(
            session_id="s4", strategy="test", slug="slug4",
            initial_balance=100.0, final_equity=100.2,
            trades=trades, equity_curve=equity_curve,
            final_positions={}, settlement_result={},
        )
        m = evaluate(session)
        assert math.isfinite(m.sharpe_ratio)
        assert math.isfinite(m.annualized_return)
        assert math.isfinite(m.sortino_ratio)

    def test_single_equity_point(self):
        """Edge: only 1 equity point → no returns, ratios = 0."""
        session = BacktestSession(
            session_id="s5", strategy="test", slug="slug5",
            initial_balance=100.0, final_equity=100.0,
            trades=[], equity_curve=[_eq_pt("2025-01-01T00:00:00Z", 100.0)],
            final_positions={}, settlement_result={},
        )
        m = evaluate(session)
        assert m.sharpe_ratio == 0.0
        assert m.sortino_ratio == 0.0
        assert m.volatility == 0.0
