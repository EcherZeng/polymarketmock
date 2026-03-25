"""Backtest engine — replays historical orderbook data to simulate trades."""

from __future__ import annotations

import json
import uuid

from app.models.backtest import BacktestRequest, BacktestResult, BacktestTradeResult
from app.storage.duckdb_store import (
    list_available_markets,
    query_archive_orderbooks,
    query_archive_prices,
    query_archive_trades,
    query_orderbooks,
    query_prices,
)
from app.storage import redis_store
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
    for ts, ob in ob_list:
        if ts <= target_ts:
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


# ── Replay engine ────────────────────────────────────────────────────────────


async def get_replay_timeline(slug: str) -> dict:
    """Return the list of available timestamps for an archived event."""
    prices = query_archive_prices(slug)
    orderbooks = query_archive_orderbooks(slug)
    trades = query_archive_trades(slug)

    all_ts: list[str] = []
    seen: set[str] = set()
    for row in prices:
        ts = row.get("timestamp", "")
        if ts and ts not in seen:
            all_ts.append(ts)
            seen.add(ts)
    for row in orderbooks:
        ts = row.get("timestamp", "")
        if ts and ts not in seen:
            all_ts.append(ts)
            seen.add(ts)

    all_ts.sort()

    # Price range stats
    mid_prices = [r["mid_price"] for r in prices if r.get("mid_price")]
    price_range = {
        "min": round(min(mid_prices), 6) if mid_prices else 0,
        "max": round(max(mid_prices), 6) if mid_prices else 0,
    }

    return {
        "slug": slug,
        "start_time": all_ts[0] if all_ts else "",
        "end_time": all_ts[-1] if all_ts else "",
        "total_snapshots": len(all_ts),
        "total_trades": len(trades),
        "price_range": price_range,
        "timestamps": all_ts,
    }


async def get_replay_snapshot(slug: str, timestamp: str) -> dict:
    """Return the full state at a given timestamp from archived data."""
    prices = query_archive_prices(slug)
    orderbooks = query_archive_orderbooks(slug)
    trades = query_archive_trades(slug)

    # Find nearest price
    price_row = _find_nearest_price(prices, timestamp) or {}
    ob_row = _find_nearest_orderbook(
        [(ob["timestamp"], ob) for ob in orderbooks], timestamp
    ) or {}

    # Find trades within ±2s of this timestamp
    snapshot_trades = []
    for t in trades:
        tts = t.get("timestamp", "")
        if not tts:
            continue
        # ISO string comparison works for same-format timestamps
        if tts <= timestamp:
            snapshot_trades.append({
                "timestamp": tts,
                "side": t.get("side", "UNKNOWN"),
                "price": t.get("price", 0),
                "size": t.get("size", 0),
            })

    return {
        "timestamp": timestamp,
        "mid_price": price_row.get("mid_price", 0),
        "best_bid": price_row.get("best_bid", 0),
        "best_ask": price_row.get("best_ask", 0),
        "spread": price_row.get("spread", 0),
        "bid_prices": json.loads(ob_row.get("bid_prices", "[]")) if isinstance(ob_row.get("bid_prices"), str) else ob_row.get("bid_prices", []),
        "bid_sizes": json.loads(ob_row.get("bid_sizes", "[]")) if isinstance(ob_row.get("bid_sizes"), str) else ob_row.get("bid_sizes", []),
        "ask_prices": json.loads(ob_row.get("ask_prices", "[]")) if isinstance(ob_row.get("ask_prices"), str) else ob_row.get("ask_prices", []),
        "ask_sizes": json.loads(ob_row.get("ask_sizes", "[]")) if isinstance(ob_row.get("ask_sizes"), str) else ob_row.get("ask_sizes", []),
        "trades": snapshot_trades,
    }


async def create_replay_session(slug: str, initial_balance: float = 10000) -> dict:
    """Create a new replay trading session (independent context)."""
    session_id = str(uuid.uuid4())
    session = {
        "session_id": session_id,
        "slug": slug,
        "initial_balance": initial_balance,
        "balance": initial_balance,
        "positions": {},  # token_id → {shares, avg_cost, side}
        "trades": [],
    }
    await redis_store.set_replay_session(session_id, json.dumps(session))
    return session


async def execute_replay_trade(
    session_id: str,
    slug: str,
    timestamp: str,
    token_id: str,
    side: str,
    amount: float,
) -> dict:
    """Execute a trade within a replay session using historical orderbook."""
    session = await redis_store.get_replay_session(session_id)
    if not session:
        return {"error": "Session not found"}

    snapshot = await get_replay_snapshot(slug, timestamp)

    if side == "BUY":
        levels = [
            {"price": str(p), "size": str(s)}
            for p, s in zip(snapshot.get("ask_prices", []), snapshot.get("ask_sizes", []))
        ]
    else:
        levels = [
            {"price": str(p), "size": str(s)}
            for p, s in zip(snapshot.get("bid_prices", []), snapshot.get("bid_sizes", []))
        ]

    filled, avg_price, total_cost = calculate_vwap_from_levels(levels, amount)
    if filled <= 0:
        return {"error": "No depth available", "filled": 0}

    mid = snapshot.get("mid_price", avg_price)
    slippage = calculate_slippage(mid, avg_price, side) if avg_price > 0 else 0.0

    balance = session["balance"]
    positions = session["positions"]

    if side == "BUY":
        if balance < total_cost:
            filled = balance / avg_price if avg_price > 0 else 0
            total_cost = balance
        balance -= total_cost
        pos = positions.get(token_id, {"shares": 0, "avg_cost": 0, "side": side})
        old_shares = pos["shares"]
        old_avg = pos["avg_cost"]
        new_shares = old_shares + filled
        new_avg = (old_avg * old_shares + avg_price * filled) / new_shares if new_shares > 0 else 0
        positions[token_id] = {"shares": round(new_shares, 6), "avg_cost": round(new_avg, 6), "side": side}
    else:
        pos = positions.get(token_id)
        if not pos or pos["shares"] < filled:
            filled = pos["shares"] if pos else 0
            total_cost = filled * avg_price
        balance += total_cost
        if pos:
            new_shares = pos["shares"] - filled
            if new_shares <= 0.000001:
                positions.pop(token_id, None)
            else:
                pos["shares"] = round(new_shares, 6)

    trade = {
        "timestamp": timestamp,
        "token_id": token_id,
        "side": side,
        "amount": round(filled, 6),
        "avg_price": round(avg_price, 6),
        "total_cost": round(total_cost, 6),
        "slippage_pct": round(slippage, 4),
        "balance_after": round(balance, 6),
    }

    session["balance"] = round(balance, 6)
    session["positions"] = positions
    session["trades"].append(trade)
    await redis_store.set_replay_session(session_id, json.dumps(session))

    return trade
