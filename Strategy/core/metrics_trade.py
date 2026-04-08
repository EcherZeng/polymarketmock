"""Trade metrics — win_rate, cost_basis, settlement split, trade PnL."""

from __future__ import annotations

from dataclasses import dataclass

from core.types import FillInfo


# ── Result containers ────────────────────────────────────────────────────────


@dataclass
class TradeMetrics:
    """Intermediate results from trade-level analysis."""

    total_trades: int = 0
    buy_count: int = 0
    sell_count: int = 0
    trade_pnls: list[float] | None = None
    settlement_pnls: list[float] | None = None
    all_pnls: list[float] | None = None
    win_rate: float = 0.0
    best_trade: float = 0.0
    worst_trade: float = 0.0
    avg_win: float = 0.0
    avg_loss: float = 0.0
    avg_slippage: float = 0.0
    profit_factor: float = 0.0
    # Settlement-specific
    trade_pnl_total: float = 0.0
    settlement_pnl_total: float = 0.0
    hold_to_settlement_ratio: float = 0.0
    avg_entry_price: float = 0.0
    expected_value: float = 0.0
    cost_basis_map: dict[str, float] | None = None


# ── Helpers ──────────────────────────────────────────────────────────────────


def compute_cost_basis(trades: list[FillInfo]) -> tuple[dict[str, float], dict[str, float]]:
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


def compute_trade_pnls(trades: list[FillInfo]) -> list[float]:
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


# ── Main computation ─────────────────────────────────────────────────────────


def compute_trade_metrics(
    trades: list[FillInfo],
    final_positions: dict[str, float] | None,
    settlement_result: dict[str, float] | None,
) -> TradeMetrics:
    """Compute all trade-level metrics including settlement split."""
    tm = TradeMetrics()
    tm.total_trades = len(trades)
    tm.buy_count = sum(1 for t in trades if t.side == "BUY")
    tm.sell_count = sum(1 for t in trades if t.side == "SELL")

    # PnL per round trip
    trade_pnls = compute_trade_pnls(trades)
    tm.trade_pnls = trade_pnls

    # Settlement PnLs for held positions
    settlement_pnls: list[float] = []
    cost_basis_map: dict[str, float] = {}
    if settlement_result and final_positions:
        cost_basis_map, _ = compute_cost_basis(trades)
        buy_counts: dict[str, int] = {}
        sell_counts: dict[str, int] = {}
        for t in trades:
            if t.side == "BUY":
                buy_counts[t.token_id] = buy_counts.get(t.token_id, 0) + 1
            elif t.side == "SELL":
                sell_counts[t.token_id] = sell_counts.get(t.token_id, 0) + 1
        for tid, qty in final_positions.items():
            if qty > 0:
                settle_price = settlement_result.get(tid, 0.0)
                avg_cost = cost_basis_map.get(tid, 0.0)
                total_settle_pnl = round((settle_price - avg_cost) * qty, 6)
                buys = buy_counts.get(tid, 0)
                sells = sell_counts.get(tid, 0)
                outstanding = buys - sells
                if outstanding <= 0:
                    outstanding = 1
                per_entry = round(total_settle_pnl / outstanding, 6)
                settlement_pnls.extend([per_entry] * outstanding)

    tm.settlement_pnls = settlement_pnls
    tm.cost_basis_map = cost_basis_map

    all_pnls = trade_pnls + settlement_pnls
    tm.all_pnls = all_pnls

    # Win/loss stats
    winners = [p for p in all_pnls if p > 0]
    losers = [p for p in all_pnls if p < 0]

    if all_pnls:
        tm.win_rate = round(len(winners) / len(all_pnls), 4)
        tm.best_trade = round(max(all_pnls), 6)
        tm.worst_trade = round(min(all_pnls), 6)
    if winners:
        tm.avg_win = round(sum(winners) / len(winners), 6)
    if losers:
        tm.avg_loss = round(sum(losers) / len(losers), 6)

    # Profit factor (capped at 999)
    total_wins = sum(winners)
    total_losses = abs(sum(losers))
    if total_losses > 0:
        tm.profit_factor = round(min(total_wins / total_losses, 999.0), 4)
    elif total_wins > 0:
        tm.profit_factor = 999.0
    else:
        tm.profit_factor = 0.0

    # Average slippage
    slippages = [t.slippage_pct for t in trades if t.slippage_pct != 0]
    tm.avg_slippage = round(sum(slippages) / len(slippages), 4) if slippages else 0.0

    # Settlement-specific metrics
    if settlement_result and final_positions:
        if not cost_basis_map:
            cost_basis_map, _ = compute_cost_basis(trades)
        settlement_pnl_val = 0.0
        total_bought = 0.0
        total_held_at_end = 0.0

        for tid, qty in final_positions.items():
            if qty > 0:
                settle_price = settlement_result.get(tid, 0.0)
                avg_cost = cost_basis_map.get(tid, 0.0)
                settlement_pnl_val += (settle_price - avg_cost) * qty
                total_held_at_end += qty

        tm.trade_pnl_total = round(sum(trade_pnls), 6) if trade_pnls else 0.0
        tm.settlement_pnl_total = round(settlement_pnl_val, 6)

        for t in trades:
            if t.side == "BUY":
                total_bought += t.filled_amount

        if total_bought > 0:
            tm.hold_to_settlement_ratio = round(total_held_at_end / total_bought, 4)

        total_cost_all = sum(t.avg_price * t.filled_amount for t in trades if t.side == "BUY")
        total_qty_all = sum(t.filled_amount for t in trades if t.side == "BUY")
        tm.avg_entry_price = round(total_cost_all / total_qty_all, 6) if total_qty_all > 0 else 0.0

        if tm.avg_entry_price > 0 and total_held_at_end > 0:
            w_settle = sum(
                settlement_result.get(tid, 0.0) * qty
                for tid, qty in final_positions.items()
                if qty > 0
            ) / total_held_at_end
            tm.expected_value = round(w_settle - tm.avg_entry_price, 6)

    return tm
