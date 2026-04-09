"""Tests for evaluator settlement PnL split logic (P0-3.2).

Covers:
- Pure hold to settlement (no SELL trades)
- Partial sell + settlement of remaining
- Full sell (no settlement entries)
- Zero trades
- Multi-token mixed positions
- Edge: buy_count == sell_count but qty > 0 (rounding residual)
"""

from __future__ import annotations

import pytest

from core.evaluator import evaluate
from core.types import BacktestSession, FillInfo


def _make_session(
    trades: list[FillInfo],
    final_positions: dict[str, float],
    settlement_result: dict[str, float],
    initial_balance: float = 100.0,
    final_equity: float = 100.0,
    equity_curve: list[dict] | None = None,
) -> BacktestSession:
    if equity_curve is None:
        equity_curve = [
            {"timestamp": "2025-01-01T00:00:00Z", "equity": initial_balance},
            {"timestamp": "2025-01-01T01:00:00Z", "equity": final_equity},
        ]
    return BacktestSession(
        session_id="test",
        strategy="test",
        slug="test-slug",
        initial_balance=initial_balance,
        final_equity=final_equity,
        trades=trades,
        equity_curve=equity_curve,
        final_positions=final_positions,
        settlement_result=settlement_result,
    )


def _make_fill(
    token_id: str,
    side: str,
    amount: float,
    price: float,
    cost: float | None = None,
) -> FillInfo:
    if cost is None:
        cost = price * amount
    return FillInfo(
        timestamp="2025-01-01T00:30:00Z",
        token_id=token_id,
        side=side,
        requested_amount=amount,
        filled_amount=amount,
        avg_price=price,
        total_cost=cost,
        slippage_pct=0.0,
        balance_after=0.0,
        position_after=0.0,
    )


class TestSettlementPnlSplit:
    """Test settlement_pnls computation and its effect on win_rate."""

    def test_pure_hold_single_buy_win(self):
        """1 BUY, hold to settlement, token wins (settle=1.0)."""
        trades = [_make_fill("T1", "BUY", 10.0, 0.6)]
        session = _make_session(
            trades=trades,
            final_positions={"T1": 10.0},
            settlement_result={"T1": 1.0},
            final_equity=104.0,
        )
        m = evaluate(session)
        # 1 outstanding BUY → 1 settlement entry → PnL = (1.0 - 0.6) * 10 = 4.0
        assert m.win_rate == 1.0
        assert len([p for p in [4.0] if p > 0]) == 1  # sanity

    def test_pure_hold_single_buy_lose(self):
        """1 BUY, hold to settlement, token loses (settle=0.0)."""
        trades = [_make_fill("T1", "BUY", 10.0, 0.6)]
        session = _make_session(
            trades=trades,
            final_positions={"T1": 10.0},
            settlement_result={"T1": 0.0},
            final_equity=94.0,
        )
        m = evaluate(session)
        # PnL = (0.0 - 0.6) * 10 = -6.0 → 0 winners / 1 total
        assert m.win_rate == 0.0

    def test_pure_hold_multiple_buys(self):
        """3 BUYs same token, hold all to settlement."""
        trades = [
            _make_fill("T1", "BUY", 5.0, 0.5),
            _make_fill("T1", "BUY", 5.0, 0.6),
            _make_fill("T1", "BUY", 5.0, 0.7),
        ]
        # avg_cost = (0.5*5 + 0.6*5 + 0.7*5) / 15 = 9.0/15 = 0.6
        session = _make_session(
            trades=trades,
            final_positions={"T1": 15.0},
            settlement_result={"T1": 1.0},
            final_equity=106.0,
        )
        m = evaluate(session)
        # 3 outstanding BUYs, 0 SELLs → 3 settlement entries
        # total_pnl = (1.0 - 0.6) * 15 = 6.0, each entry = 2.0 → all winners
        assert m.win_rate == 1.0

    def test_partial_sell_plus_settlement(self):
        """3 BUYs, 1 SELL, remaining 2 settle."""
        trades = [
            _make_fill("T1", "BUY", 5.0, 0.5),
            _make_fill("T1", "BUY", 5.0, 0.6),
            _make_fill("T1", "BUY", 5.0, 0.7),
            _make_fill("T1", "SELL", 5.0, 0.8),  # sell 5 @ 0.8
        ]
        # After trades: held = 10.0, avg_cost still ~0.6 (weighted avg)
        # trade_pnls from SELL: (0.8 - 0.6) * 5 = 1.0
        # outstanding = 3 - 1 = 2
        # settlement: (1.0 - 0.6) * 10 / 2 = 2.0 each → 2 entries
        # all_pnls = [1.0, 2.0, 2.0] → 3 winners
        session = _make_session(
            trades=trades,
            final_positions={"T1": 10.0},
            settlement_result={"T1": 1.0},
            final_equity=111.0,
        )
        m = evaluate(session)
        assert m.win_rate == 1.0

    def test_full_sell_no_settlement(self):
        """All bought shares sold — no settlement entries."""
        trades = [
            _make_fill("T1", "BUY", 10.0, 0.5),
            _make_fill("T1", "SELL", 10.0, 0.8),
        ]
        session = _make_session(
            trades=trades,
            final_positions={"T1": 0.0},
            settlement_result={"T1": 1.0},
            final_equity=103.0,
        )
        m = evaluate(session)
        # Only 1 trade_pnl: (0.8 - 0.5) * 10 = 3.0
        assert m.win_rate == 1.0
        assert m.total_trades == 2

    def test_zero_trades(self):
        """No trades at all — win_rate stays at default 0."""
        session = _make_session(
            trades=[],
            final_positions={},
            settlement_result={},
            final_equity=100.0,
        )
        m = evaluate(session)
        assert m.win_rate == 0.0
        assert m.total_trades == 0

    def test_zero_trades_with_settlement(self):
        """No trades but has positions (external) and settlement."""
        session = _make_session(
            trades=[],
            final_positions={"T1": 10.0},
            settlement_result={"T1": 1.0},
            final_equity=110.0,
        )
        m = evaluate(session)
        # No BUY trades → buy_counts["T1"] = 0, outstanding = 0 → fallback to 1
        # cost_basis = 0.0, settle PnL = (1.0 - 0.0) * 10 = 10.0, 1 entry
        assert m.win_rate == 1.0

    def test_multi_token_mixed(self):
        """Two tokens: one wins, one loses at settlement."""
        trades = [
            _make_fill("T1", "BUY", 10.0, 0.4),
            _make_fill("T2", "BUY", 10.0, 0.7),
        ]
        session = _make_session(
            trades=trades,
            final_positions={"T1": 10.0, "T2": 10.0},
            settlement_result={"T1": 1.0, "T2": 0.0},
            final_equity=103.0,
        )
        m = evaluate(session)
        # T1: (1.0 - 0.4) * 10 = 6.0 → win
        # T2: (0.0 - 0.7) * 10 = -7.0 → loss
        # all_pnls = [6.0, -7.0] → 1 winner / 2 total
        assert m.win_rate == 0.5

    def test_buy_count_equals_sell_count_residual_qty(self):
        """Edge: buys == sells in count, but qty > 0 (rounding residual)."""
        trades = [
            _make_fill("T1", "BUY", 10.0, 0.5),
            _make_fill("T1", "SELL", 9.5, 0.8),  # sold slightly less
        ]
        session = _make_session(
            trades=trades,
            final_positions={"T1": 0.5},  # small residual
            settlement_result={"T1": 1.0},
            final_equity=103.0,
        )
        m = evaluate(session)
        # outstanding = 1 - 1 = 0 → fallback to 1
        # trade_pnl from SELL: (0.8 - 0.5) * 9.5 = 2.85
        # settlement: (1.0 - 0.5) * 0.5 = 0.25, 1 entry
        # all_pnls = [2.85, 0.25] → 2 winners
        assert m.win_rate == 1.0

    def test_only_sell_trades_with_position(self):
        """Only SELL trades (no BUY), but has remaining position."""
        trades = [
            _make_fill("T1", "SELL", 5.0, 0.8),
        ]
        session = _make_session(
            trades=trades,
            final_positions={"T1": 5.0},
            settlement_result={"T1": 0.0},
            final_equity=96.0,
        )
        m = evaluate(session)
        # buy_counts["T1"] = 0, sell_counts["T1"] = 1
        # outstanding = 0 - 1 = -1 → fallback to 1
        # cost_basis = 0.0, settle PnL = (0.0 - 0.0) * 5 = 0.0
        # trade_pnl from SELL: (0.8 - 0) * 5 = 4.0 (no cost basis for pure sells)
        # all_pnls = [4.0, 0.0] → 1 winner, 1 neutral
        assert m.total_trades == 1
