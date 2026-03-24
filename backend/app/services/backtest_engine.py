"""Backtest engine — replays historical orderbook data to simulate trades."""

from __future__ import annotations

import json

from app.models.backtest import BacktestRequest, BacktestResult, BacktestTradeResult
from app.storage.duckdb_store import list_available_markets, query_orderbooks, query_prices
from app.utils.price_impact import calculate_slippage, calculate_vwap_from_levels


async def run_backtest(req: BacktestRequest) -> BacktestResult:
    """Run a backtest by replaying historical data."""
    # Load historical orderbook snapshots
    orderbooks = query_orderbooks(req.market_id, req.start_time, req.end_time)
    prices = query_prices(req.market_id, req.start_time, req.end_time)

    balance = req.initial_balance
    shares_held = 0.0
    avg_cost = 0.0
    trade_results: list[BacktestTradeResult] = []
    equity_curve: list[dict] = []

    # Index orderbooks by timestamp (use closest one)
    ob_by_ts: list[tuple[str, dict]] = []
    for ob in orderbooks:
        ob_by_ts.append((ob["timestamp"], ob))

    for instruction in req.trades:
        # Find nearest orderbook snapshot
        nearest_ob = _find_nearest_orderbook(ob_by_ts, instruction.timestamp)
        if not nearest_ob:
            continue

        bids_raw = json.loads(nearest_ob.get("bid_prices", "[]"))
        bid_sizes = json.loads(nearest_ob.get("bid_sizes", "[]"))
        asks_raw = json.loads(nearest_ob.get("ask_prices", "[]"))
        ask_sizes = json.loads(nearest_ob.get("ask_sizes", "[]"))

        if instruction.side == "BUY":
            levels = [{"price": str(p), "size": str(s)} for p, s in zip(asks_raw, ask_sizes)]
        else:
            levels = [{"price": str(p), "size": str(s)} for p, s in zip(bids_raw, bid_sizes)]

        filled, avg_price, total_cost = calculate_vwap_from_levels(levels, instruction.amount)

        if filled <= 0:
            continue

        # Find nearest price for mid
        nearest_price = _find_nearest_price(prices, instruction.timestamp)
        mid = nearest_price.get("mid_price", avg_price) if nearest_price else avg_price
        slippage = calculate_slippage(mid, avg_price, instruction.side)

        if instruction.side == "BUY":
            if balance < total_cost:
                filled = balance / avg_price if avg_price > 0 else 0
                total_cost = balance
            balance -= total_cost
            if shares_held > 0:
                avg_cost = (avg_cost * shares_held + avg_price * filled) / (shares_held + filled)
            else:
                avg_cost = avg_price
            shares_held += filled
        else:
            if shares_held < filled:
                filled = shares_held
                total_cost = filled * avg_price
            balance += total_cost
            shares_held -= filled

        trade_results.append(BacktestTradeResult(
            timestamp=instruction.timestamp,
            side=instruction.side,
            requested_amount=instruction.amount,
            filled_amount=round(filled, 6),
            avg_price=round(avg_price, 6),
            total_cost=round(total_cost, 6),
            slippage_pct=round(slippage, 4),
            balance_after=round(balance, 6),
        ))

        equity_curve.append({
            "timestamp": instruction.timestamp,
            "balance": round(balance, 6),
            "positions_value": round(shares_held * mid, 6),
            "total_equity": round(balance + shares_held * mid, 6),
        })

    # Final equity
    final_mid = prices[-1]["mid_price"] if prices else 0
    final_positions_value = shares_held * final_mid
    final_equity = balance + final_positions_value

    return BacktestResult(
        market_id=req.market_id,
        token_id=req.token_id,
        initial_balance=req.initial_balance,
        final_balance=round(final_equity, 6),
        total_pnl=round(final_equity - req.initial_balance, 6),
        total_trades=len(trade_results),
        trade_results=trade_results,
        equity_curve=equity_curve,
    )


def _find_nearest_orderbook(ob_list: list[tuple[str, dict]], target_ts: str) -> dict | None:
    if not ob_list:
        return None
    best = None
    best_diff = float("inf")
    for ts, ob in ob_list:
        if ts <= target_ts:
            diff = len(target_ts) - len(ts)  # simplified proximity
            if best is None or ts > best[0]:
                best = (ts, ob)
    return best[1] if best else ob_list[0][1]


def _find_nearest_price(prices: list[dict], target_ts: str) -> dict | None:
    if not prices:
        return None
    best = None
    for p in prices:
        if p["timestamp"] <= target_ts:
            best = p
    return best or prices[0]


def get_backtest_markets() -> list[dict]:
    return list_available_markets()
