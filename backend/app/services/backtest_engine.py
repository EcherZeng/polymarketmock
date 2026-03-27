"""Backtest engine — replays historical orderbook data to simulate trades."""

from __future__ import annotations

import asyncio
import json
import uuid
from collections.abc import AsyncGenerator
from datetime import datetime, timedelta, timezone

from app.models.backtest import BacktestRequest, BacktestResult, BacktestTradeResult
from app.storage.duckdb_store import (
    list_available_markets,
    query_archive_live_trades,
    query_archive_ob_deltas,
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


def _build_time_grid(all_ts: list[str]) -> list[str]:
    """Build a 1-second interval time grid from min to max of *all_ts*.

    Returns ISO-formatted timestamps at every whole second between the
    earliest and latest timestamps (inclusive).
    """
    if not all_ts:
        return []
    sorted_ts = sorted(all_ts)
    dt_start = datetime.fromisoformat(sorted_ts[0])
    dt_end = datetime.fromisoformat(sorted_ts[-1])
    # Truncate start to whole second
    dt_cur = dt_start.replace(microsecond=0)
    grid: list[str] = []
    while dt_cur <= dt_end:
        grid.append(dt_cur.isoformat())
        dt_cur += timedelta(seconds=1)
    # Ensure at least one entry
    if not grid:
        grid.append(dt_start.isoformat())
    return grid


def _collect_all_data_ts(
    prices: list[dict],
    orderbooks: list[dict],
    live_trades: list[dict],
    ob_deltas: list[dict],
) -> tuple[list[str], set[str]]:
    """Collect unique timestamps and token IDs from all data sources."""
    all_ts: list[str] = []
    seen: set[str] = set()
    token_id_set: set[str] = set()
    for row in (*prices, *orderbooks, *live_trades, *ob_deltas):
        ts = row.get("timestamp", "")
        if ts and ts not in seen:
            all_ts.append(ts)
            seen.add(ts)
        tid = row.get("token_id", "")
        if tid:
            token_id_set.add(tid)
    all_ts.sort()
    return all_ts, token_id_set


async def get_replay_timeline(slug: str) -> dict:
    """Return the list of available timestamps for an archived event."""
    prices = query_archive_prices(slug)
    orderbooks = query_archive_orderbooks(slug)
    live_trades = query_archive_live_trades(slug)
    ob_deltas = query_archive_ob_deltas(slug)

    all_ts, token_id_set = _collect_all_data_ts(prices, orderbooks, live_trades, ob_deltas)

    # Build 1-second time grid for smooth replay
    time_grid = _build_time_grid(all_ts)

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
        "ob_deltas": _time_range(ob_deltas),
    }

    return {
        "slug": slug,
        "start_time": time_grid[0] if time_grid else "",
        "end_time": time_grid[-1] if time_grid else "",
        "total_snapshots": len(time_grid),
        "total_trades": len(live_trades),
        "price_range": price_range,
        "data_summary": data_summary,
        "token_ids": sorted(token_id_set),
        "timestamps": time_grid,
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


# ── Working-orderbook helpers ────────────────────────────────────────────────


def _init_working_ob(snapshot: dict) -> dict:
    """Initialise a working orderbook from a full book snapshot.

    Returns ``{"bids": {price_str: size_float}, "asks": {...}}``.
    """
    bids: dict[str, float] = {}
    asks: dict[str, float] = {}
    for p, s in zip(snapshot.get("bid_prices", []), snapshot.get("bid_sizes", [])):
        bids[str(p)] = float(s)
    for p, s in zip(snapshot.get("ask_prices", []), snapshot.get("ask_sizes", [])):
        asks[str(p)] = float(s)
    return {"bids": bids, "asks": asks}


def _apply_delta_to_ob(working_ob: dict, delta: dict) -> None:
    """Apply a single orderbook delta (from ``price_change``) in-place."""
    side = delta.get("side", "")
    key = "bids" if side == "BUY" else "asks"
    levels: dict[str, float] = working_ob.setdefault(key, {})
    price = str(delta.get("price", "0"))
    size = float(delta.get("size", 0))
    if size == 0:
        levels.pop(price, None)
    else:
        levels[price] = size


def _derive_price_from_ob(working_ob: dict) -> dict:
    """Derive mid_price / best_bid / best_ask / spread from a working orderbook."""
    bids = working_ob.get("bids", {})
    asks = working_ob.get("asks", {})
    best_bid = max((float(p) for p in bids), default=0.0)
    best_ask = min((float(p) for p in asks), default=0.0)
    mid = (best_bid + best_ask) / 2 if (best_bid and best_ask) else best_bid or best_ask
    spread = (best_ask - best_bid) if (best_bid and best_ask) else 0.0
    return {
        "mid_price": round(mid, 6),
        "best_bid": round(best_bid, 6),
        "best_ask": round(best_ask, 6),
        "spread": round(spread, 6),
    }


def _ob_to_levels(working_ob: dict) -> dict:
    """Convert working orderbook to sorted price/size arrays for the SSE payload."""
    bids = working_ob.get("bids", {})
    asks = working_ob.get("asks", {})
    sorted_bids = sorted(bids.items(), key=lambda x: float(x[0]), reverse=True)
    sorted_asks = sorted(asks.items(), key=lambda x: float(x[0]))
    return {
        "bid_prices": [float(p) for p, _ in sorted_bids],
        "bid_sizes": [float(s) for _, s in sorted_bids],
        "ask_prices": [float(p) for p, _ in sorted_asks],
        "ask_sizes": [float(s) for _, s in sorted_asks],
    }


def _rebuild_ob_at(
    orderbooks: list[dict],
    ob_deltas: list[dict],
    target_ts: str,
    token_id: str,
) -> dict:
    """Rebuild a working orderbook at *target_ts* for one token.

    1. Start from the nearest ``book`` snapshot ≤ target_ts.
    2. Apply all ``ob_deltas`` between the snapshot ts and target_ts.
    """
    # Find nearest full snapshot
    best_ts = ""
    best_ob: dict | None = None
    for ob in orderbooks:
        if ob.get("token_id") != token_id:
            continue
        ts = ob.get("timestamp", "")
        if ts <= target_ts and ts > best_ts:
            best_ts = ts
            best_ob = ob
    working = _init_working_ob(best_ob) if best_ob else {"bids": {}, "asks": {}}

    # Apply deltas between snapshot and target
    for d in ob_deltas:
        if d.get("token_id") != token_id:
            continue
        dts = d.get("timestamp", "")
        if best_ts and dts <= best_ts:
            continue
        if dts > target_ts:
            break
        _apply_delta_to_ob(working, d)

    return working


async def get_replay_snapshot(slug: str, timestamp: str) -> dict:
    """Return the full state at a given timestamp from archived data.

    Returns per-token price + orderbook in ``tokens`` dict.
    Uses ob_deltas (if available) to reconstruct the precise orderbook state.
    """
    prices = query_archive_prices(slug)
    orderbooks = query_archive_orderbooks(slug)
    live_trades = query_archive_live_trades(slug)
    ob_deltas = query_archive_ob_deltas(slug)

    token_ids = _collect_token_ids(prices, orderbooks)

    tokens_data: dict[str, dict] = {}
    for tid in token_ids:
        if ob_deltas:
            working = _rebuild_ob_at(orderbooks, ob_deltas, timestamp, tid)
            levels = _ob_to_levels(working)
            derived = _derive_price_from_ob(working)
            tokens_data[tid] = {**derived, **levels}
        else:
            # Fallback for old archives without ob_deltas
            ob_indexed = [(ob["timestamp"], ob) for ob in orderbooks]
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

    Snapshots are emitted on a 1-second time grid (matching the timeline),
    paced at ``1.0 / speed`` real seconds per tick.  Each tick applies all
    orderbook snapshots, ob_deltas, and trades whose timestamps fall within
    the current grid second, then derives per-token price/OB data.
    """
    prices = query_archive_prices(slug)
    orderbooks = query_archive_orderbooks(slug)
    live_trades = query_archive_live_trades(slug)
    ob_deltas = query_archive_ob_deltas(slug)

    has_deltas = bool(ob_deltas)

    # Collect token IDs
    token_ids = _collect_token_ids(prices, orderbooks)

    # Build the same 1-second time grid used by get_replay_timeline
    all_data_ts, _ = _collect_all_data_ts(prices, orderbooks, live_trades, ob_deltas)
    time_grid = _build_time_grid(all_data_ts)

    if not time_grid or start_index >= len(time_grid):
        return

    # Pre-sort trades for pointer-based traversal
    sorted_trades = sorted(live_trades, key=lambda t: t.get("timestamp", ""))

    # Advance trade pointer past start_index boundary
    trade_ptr = 0
    if start_index > 0:
        boundary_ts = time_grid[start_index - 1]
        while trade_ptr < len(sorted_trades) and sorted_trades[trade_ptr].get("timestamp", "") <= boundary_ts:
            trade_ptr += 1

    if has_deltas:
        # ── Delta-driven path ────────────────────────────────────
        ob_snap_map: dict[str, dict[str, dict]] = {}
        for ob in orderbooks:
            ts = ob.get("timestamp", "")
            tid = ob.get("token_id", "")
            ob_snap_map.setdefault(ts, {})[tid] = ob

        # Pre-sort deltas for pointer-based traversal
        sorted_deltas = sorted(ob_deltas, key=lambda d: d.get("timestamp", ""))
        delta_ptr = 0

        # Collect sorted unique orderbook snapshot timestamps for range lookup
        ob_snap_ts_sorted = sorted(ob_snap_map.keys())
        ob_snap_ptr = 0

        # Initialise per-token working orderbooks up to start_index boundary
        working_obs: dict[str, dict] = {tid: {"bids": {}, "asks": {}} for tid in token_ids}
        if start_index > 0:
            boundary_ts = time_grid[start_index - 1]
            for ob in orderbooks:
                if ob.get("timestamp", "") <= boundary_ts:
                    tid = ob.get("token_id", "")
                    if tid in working_obs:
                        working_obs[tid] = _init_working_ob(ob)
            while delta_ptr < len(sorted_deltas) and sorted_deltas[delta_ptr].get("timestamp", "") <= boundary_ts:
                d = sorted_deltas[delta_ptr]
                tid = d.get("token_id", "")
                if tid in working_obs:
                    _apply_delta_to_ob(working_obs[tid], d)
                delta_ptr += 1
            # Advance ob_snap_ptr past boundary
            while ob_snap_ptr < len(ob_snap_ts_sorted) and ob_snap_ts_sorted[ob_snap_ptr] <= boundary_ts:
                ob_snap_ptr += 1

        for i in range(start_index, len(time_grid)):
            ts = time_grid[i]

            # Pace: 1 real second / speed per grid tick
            if i > start_index:
                await asyncio.sleep(1.0 / speed)

            # Apply any full book snapshots with timestamp <= ts
            while ob_snap_ptr < len(ob_snap_ts_sorted) and ob_snap_ts_sorted[ob_snap_ptr] <= ts:
                snap_ts = ob_snap_ts_sorted[ob_snap_ptr]
                for tid, ob in ob_snap_map[snap_ts].items():
                    if tid in working_obs:
                        working_obs[tid] = _init_working_ob(ob)
                ob_snap_ptr += 1

            # Apply deltas up to this timestamp
            while delta_ptr < len(sorted_deltas):
                d_ts = sorted_deltas[delta_ptr].get("timestamp", "")
                if d_ts and d_ts <= ts:
                    d = sorted_deltas[delta_ptr]
                    tid = d.get("token_id", "")
                    if tid in working_obs:
                        _apply_delta_to_ob(working_obs[tid], d)
                    delta_ptr += 1
                else:
                    break

            # Build per-token data from working orderbooks
            tokens_data: dict[str, dict] = {}
            for tid in token_ids:
                levels = _ob_to_levels(working_obs.get(tid, {"bids": {}, "asks": {}}))
                derived = _derive_price_from_ob(working_obs.get(tid, {"bids": {}, "asks": {}}))
                tokens_data[tid] = {**derived, **levels}

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
    else:
        # ── Fallback: nearest-snapshot path (old archives) ────
        ob_indexed = [(ob["timestamp"], ob) for ob in orderbooks]

        for i in range(start_index, len(time_grid)):
            ts = time_grid[i]

            if i > start_index:
                await asyncio.sleep(1.0 / speed)

            tokens_data = {}
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
