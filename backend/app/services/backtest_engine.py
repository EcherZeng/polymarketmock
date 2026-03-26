"""Backtest engine — replays historical orderbook data to simulate trades."""

from __future__ import annotations

import asyncio
import json
import uuid
from collections.abc import AsyncGenerator
from datetime import datetime

from app.models.backtest import BacktestRequest, BacktestResult, BacktestTradeResult
from app.storage.duckdb_store import (
    list_available_markets,
    query_archive_live_trades,
    query_archive_orderbooks,
    query_archive_prices,
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

        bids_raw = nearest_ob.get("bid_prices", [])
        bid_sizes = nearest_ob.get("bid_sizes", [])
        asks_raw = nearest_ob.get("ask_prices", [])
        ask_sizes = nearest_ob.get("ask_sizes", [])

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
    live_trades = query_archive_live_trades(slug)

    all_ts: list[str] = []
    seen: set[str] = set()
    token_id_set: set[str] = set()
    for row in prices:
        ts = row.get("timestamp", "")
        if ts and ts not in seen:
            all_ts.append(ts)
            seen.add(ts)
        tid = row.get("token_id", "")
        if tid:
            token_id_set.add(tid)
    for row in orderbooks:
        ts = row.get("timestamp", "")
        if ts and ts not in seen:
            all_ts.append(ts)
            seen.add(ts)
        tid = row.get("token_id", "")
        if tid:
            token_id_set.add(tid)
    for row in live_trades:
        ts = row.get("timestamp", "")
        if ts and ts not in seen:
            all_ts.append(ts)
            seen.add(ts)
        tid = row.get("token_id", "")
        if tid:
            token_id_set.add(tid)

    all_ts.sort()

    # Price range stats
    mid_prices = [r["mid_price"] for r in prices if r.get("mid_price")]
    price_range = {
        "min": round(min(mid_prices), 6) if mid_prices else 0,
        "max": round(max(mid_prices), 6) if mid_prices else 0,
    }

    # Data summary — describe what data is available and its time range
    def _time_range(rows: list[dict]) -> dict:
        ts_list = [r.get("timestamp", "") for r in rows if r.get("timestamp")]
        if not ts_list:
            return {"count": 0, "start": "", "end": ""}
        ts_list.sort()
        return {"count": len(ts_list), "start": ts_list[0], "end": ts_list[-1]}

    data_summary = {
        "prices": _time_range(prices),
        "orderbooks": _time_range(orderbooks),
        "live_trades": _time_range(live_trades),
    }

    return {
        "slug": slug,
        "start_time": all_ts[0] if all_ts else "",
        "end_time": all_ts[-1] if all_ts else "",
        "total_snapshots": len(all_ts),
        "total_trades": len(live_trades),
        "price_range": price_range,
        "data_summary": data_summary,
        "token_ids": sorted(token_id_set),
        "timestamps": all_ts,
    }


def _find_nearest_price_for_token(
    prices: list[dict], target_ts: str, token_id: str,
) -> dict | None:
    """Find nearest price row for a specific token_id."""
    best = None
    for p in prices:
        if p.get("token_id") != token_id:
            continue
        if p["timestamp"] <= target_ts:
            best = p
    return best


def _find_nearest_orderbook_for_token(
    ob_list: list[tuple[str, dict]], target_ts: str, token_id: str,
) -> dict | None:
    """Find nearest orderbook row for a specific token_id."""
    best: tuple[str, dict] | None = None
    for ts, ob in ob_list:
        if ob.get("token_id") != token_id:
            continue
        if ts <= target_ts:
            if best is None or ts > best[0]:
                best = (ts, ob)
    return best[1] if best else None


def _collect_token_ids(prices: list[dict], orderbooks: list[dict]) -> list[str]:
    """Extract unique token_ids from prices and orderbooks."""
    ids: set[str] = set()
    for row in prices:
        tid = row.get("token_id", "")
        if tid:
            ids.add(tid)
    for row in orderbooks:
        tid = row.get("token_id", "")
        if tid:
            ids.add(tid)
    return sorted(ids)


async def get_replay_snapshot(slug: str, timestamp: str) -> dict:
    """Return the full state at a given timestamp from archived data.

    Returns per-token price + orderbook in `tokens` dict.
    """
    prices = query_archive_prices(slug)
    orderbooks = query_archive_orderbooks(slug)
    live_trades = query_archive_live_trades(slug)

    ob_indexed = [(ob["timestamp"], ob) for ob in orderbooks]
    token_ids = _collect_token_ids(prices, orderbooks)

    tokens_data: dict[str, dict] = {}
    for tid in token_ids:
        p = _find_nearest_price_for_token(prices, timestamp, tid) or {}
        ob = _find_nearest_orderbook_for_token(ob_indexed, timestamp, tid) or {}
        tokens_data[tid] = {
            "mid_price": p.get("mid_price", 0),
            "best_bid": p.get("best_bid", 0),
            "best_ask": p.get("best_ask", 0),
            "spread": p.get("spread", 0),
            "bid_prices": ob.get("bid_prices", []),
            "bid_sizes": ob.get("bid_sizes", []),
            "ask_prices": ob.get("ask_prices", []),
            "ask_sizes": ob.get("ask_sizes", []),
        }

    # Find live trades up to this timestamp
    snapshot_trades = []
    for t in live_trades:
        tts = t.get("timestamp", "")
        if not tts:
            continue
        if tts <= timestamp:
            snapshot_trades.append({
                "timestamp": tts,
                "token_id": t.get("token_id", ""),
                "side": t.get("side", "UNKNOWN"),
                "price": t.get("price", 0),
                "size": t.get("size", 0),
                "transaction_hash": t.get("transaction_hash", ""),
            })

    return {
        "timestamp": timestamp,
        "token_ids": token_ids,
        "tokens": tokens_data,
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

    # Extract per-token data from snapshot
    token_data = snapshot.get("tokens", {}).get(token_id, {})

    if side == "BUY":
        levels = [
            {"price": str(p), "size": str(s)}
            for p, s in zip(token_data.get("ask_prices", []), token_data.get("ask_sizes", []))
        ]
    else:
        levels = [
            {"price": str(p), "size": str(s)}
            for p, s in zip(token_data.get("bid_prices", []), token_data.get("bid_sizes", []))
        ]

    filled, avg_price, total_cost = calculate_vwap_from_levels(levels, amount)
    if filled <= 0:
        return {"error": "No depth available", "filled": 0}

    mid = token_data.get("mid_price", avg_price)
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


# ── SSE replay stream ────────────────────────────────────────────────────────


def _iso_diff_seconds(ts1: str, ts2: str) -> float:
    """Return seconds between two ISO timestamps."""
    try:
        dt1 = datetime.fromisoformat(ts1)
        dt2 = datetime.fromisoformat(ts2)
        return max(0.0, (dt2 - dt1).total_seconds())
    except (ValueError, TypeError):
        return 0.1


async def generate_replay_stream(
    slug: str,
    start_index: int,
    speed: float,
) -> AsyncGenerator[dict, None]:
    """Yield replay snapshots for SSE streaming.

    Data is loaded once; snapshots are paced by real timestamp deltas / speed.
    Trades are sent incrementally (only new trades per event).
    """
    prices = query_archive_prices(slug)
    orderbooks = query_archive_orderbooks(slug)
    live_trades = query_archive_live_trades(slug)

    # Collect token IDs
    token_ids = _collect_token_ids(prices, orderbooks)

    # Build sorted unique timestamps
    all_ts_set: set[str] = set()
    for row in prices:
        ts = row.get("timestamp", "")
        if ts:
            all_ts_set.add(ts)
    for row in orderbooks:
        ts = row.get("timestamp", "")
        if ts:
            all_ts_set.add(ts)
    for row in live_trades:
        ts = row.get("timestamp", "")
        if ts:
            all_ts_set.add(ts)
    sorted_ts = sorted(all_ts_set)

    if not sorted_ts or start_index >= len(sorted_ts):
        return

    # Pre-sort trades for pointer-based traversal
    sorted_trades = sorted(live_trades, key=lambda t: t.get("timestamp", ""))

    # Orderbook index list
    ob_indexed = [(ob["timestamp"], ob) for ob in orderbooks]

    # Advance trade pointer past start_index boundary
    trade_ptr = 0
    if start_index > 0:
        boundary_ts = sorted_ts[start_index - 1]
        while trade_ptr < len(sorted_trades) and sorted_trades[trade_ptr].get("timestamp", "") <= boundary_ts:
            trade_ptr += 1

    prev_iso: str | None = None

    for i in range(start_index, len(sorted_ts)):
        ts = sorted_ts[i]

        # Pace by real timestamp delta / speed
        if prev_iso is not None:
            delta = _iso_diff_seconds(prev_iso, ts)
            delay = delta / speed
            delay = max(0.02, min(delay, 2.0))  # 20ms min, 2s max
            await asyncio.sleep(delay)

        # Per-token nearest price & orderbook
        tokens_data: dict[str, dict] = {}
        for tid in token_ids:
            p = _find_nearest_price_for_token(prices, ts, tid) or {}
            ob = _find_nearest_orderbook_for_token(ob_indexed, ts, tid) or {}
            tokens_data[tid] = {
                "mid_price": p.get("mid_price", 0),
                "best_bid": p.get("best_bid", 0),
                "best_ask": p.get("best_ask", 0),
                "spread": p.get("spread", 0),
                "bid_prices": ob.get("bid_prices", []),
                "bid_sizes": ob.get("bid_sizes", []),
                "ask_prices": ob.get("ask_prices", []),
                "ask_sizes": ob.get("ask_sizes", []),
            }

        # Incremental trades
        new_trades: list[dict] = []
        while trade_ptr < len(sorted_trades):
            t_ts = sorted_trades[trade_ptr].get("timestamp", "")
            if t_ts and t_ts <= ts:
                t = sorted_trades[trade_ptr]
                new_trades.append({
                    "timestamp": t_ts,
                    "token_id": t.get("token_id", ""),
                    "side": t.get("side", "UNKNOWN"),
                    "price": t.get("price", 0),
                    "size": t.get("size", 0),
                    "transaction_hash": t.get("transaction_hash", ""),
                })
                trade_ptr += 1
            else:
                break

        yield {
            "index": i,
            "timestamp": ts,
            "token_ids": token_ids,
            "tokens": tokens_data,
            "new_trades": new_trades,
            "total_trades": trade_ptr,
        }

        prev_iso = ts
