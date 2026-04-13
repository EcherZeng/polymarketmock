"""Single backtest runner — delta-driven orderbook reconstruction and tick-by-tick execution.

Sub-modules (split for maintainability):
  core/orderbook_state.py  — OB init, delta application, snapshot derivation
  core/anchor_pricing.py   — Tiered anchor price (mid / micro / last_trade)
"""

from __future__ import annotations

import logging
import time
import uuid
from collections import defaultdict
from datetime import datetime, timedelta, timezone

from config import config
from core.anchor_pricing import SPREAD_WIDE, compute_anchor_price
from core.base_strategy import BaseStrategy
from core.btc_data import compute_btc_trend
from core.data_loader import load_archive
from core.matching import execute_signal
from core.orderbook_state import apply_delta, derive_snapshot_from_ob, init_working_ob
from core.registry import StrategyRegistry
from core.types import (
    ArchiveData,
    BacktestSession,
    FillInfo,
    TickContext,
    TokenSnapshot,
    param_active,
)

logger = logging.getLogger(__name__)


# ── Time grid ────────────────────────────────────────────────────────────────


def _build_time_grid(all_ts: list[str]) -> list[str]:
    """Build a 1-second interval time grid from min to max."""
    if not all_ts:
        return []
    sorted_ts = sorted(all_ts)
    dt_start = datetime.fromisoformat(sorted_ts[0])
    dt_end = datetime.fromisoformat(sorted_ts[-1])
    dt_cur = dt_start.replace(microsecond=0)
    grid: list[str] = []
    while dt_cur <= dt_end:
        grid.append(dt_cur.isoformat())
        dt_cur += timedelta(seconds=1)
    if not grid:
        grid.append(dt_start.isoformat())
    return grid


def _collect_timestamps(data: ArchiveData) -> list[str]:
    """Collect all unique timestamps from all data sources."""
    seen: set[str] = set()
    for row in (*data.prices, *data.orderbooks, *data.live_trades, *data.ob_deltas):
        ts = row.get("timestamp", "")
        if ts:
            seen.add(ts)
    return sorted(seen)


def _collect_token_ids(data: ArchiveData) -> list[str]:
    """Extract all unique token_ids from data."""
    ids: set[str] = set()
    for row in (*data.prices, *data.orderbooks, *data.ob_deltas):
        tid = row.get("token_id", "")
        if tid:
            ids.add(tid)
    return sorted(ids)


# ── Index builders for efficient lookup ──────────────────────────────────────


def _build_index(rows: list[dict], key: str = "token_id") -> dict[str, list[dict]]:
    """Build a dict grouping rows by key value, each group sorted by timestamp."""
    index: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        k = row.get(key, "")
        if k:
            index[k].append(row)
    return dict(index)


class _Pointer:
    """Tracks current position in a sorted list for sequential access."""

    def __init__(self, items: list[dict]) -> None:
        self.items = items
        self.pos = 0

    def advance_to(self, target_ts: str) -> list[dict]:
        """Return all items with timestamp <= target_ts, advancing pointer."""
        consumed: list[dict] = []
        while self.pos < len(self.items):
            ts = self.items[self.pos].get("timestamp", "")
            if ts <= target_ts:
                consumed.append(self.items[self.pos])
                self.pos += 1
            else:
                break
        return consumed


# ── Runner ───────────────────────────────────────────────────────────────────


def run_backtest(
    registry: StrategyRegistry,
    strategy_name: str,
    slug: str,
    user_config: dict,
    initial_balance: float,
    data: ArchiveData | None = None,
    settlement_result: dict[str, float] | None = None,
    btc_klines: list[dict] | None = None,
) -> BacktestSession:
    """Execute a single backtest synchronously.

    This runs in a thread pool when called from async context.
    """
    t_start = time.monotonic()
    session_id = uuid.uuid4().hex[:12]

    # Resolve strategy
    strategy_cls = registry.get(strategy_name)
    if strategy_cls is None:
        logger.error("Strategy '%s' not found in registry", strategy_name)
        raise ValueError(f"Strategy '{strategy_name}' not found in registry")

    strategy: BaseStrategy = strategy_cls()

    # Load data
    if data is None:
        data = load_archive(config.data_dir, slug)

    if not data.prices and not data.orderbooks:
        logger.error("Slug '%s' has no prices and no orderbooks", slug)
        raise ValueError(f"Slug '{slug}' archive is empty — no prices and no orderbooks")

    # Token IDs
    token_ids = _collect_token_ids(data)
    if not token_ids:
        raise ValueError(f"Slug '{slug}' has no token_ids in data")

    logger.info(
        "Backtest %s [%s/%s]: %d tokens, data=%d prices + %d orderbooks + %d deltas",
        session_id, strategy_name, slug, len(token_ids),
        len(data.prices), len(data.orderbooks), len(data.ob_deltas),
    )

    # Build time grid
    all_ts = _collect_timestamps(data)
    time_grid = _build_time_grid(all_ts)
    total_ticks = len(time_grid)
    if total_ticks == 0:
        raise ValueError(f"Slug '{slug}' produced an empty time grid (no timestamps)")

    logger.info("Backtest %s: time grid %d ticks (%s → %s)", session_id, total_ticks, time_grid[0], time_grid[-1])

    # ── Merge config (must happen before any param_active checks) ────────
    default_config = registry.get_default_config(strategy_name)
    if user_config:
        merged_config = {k: user_config.get(k, default_config.get(k)) for k in user_config}
    else:
        merged_config = dict(default_config)
    merged_config = registry.normalize_config(merged_config)

    # ── BTC trend filter ─────────────────────────────────────────────────
    btc_trend_info: dict | None = None
    btc_trend_pass = True  # default: allow entry
    if param_active(merged_config, "btc_trend_enabled") and merged_config.get("btc_trend_enabled"):
        w1 = merged_config.get("btc_trend_window_1", 5)
        w2 = merged_config.get("btc_trend_window_2", 5)
        min_mom = merged_config.get("btc_min_momentum", 0.001)
        if btc_klines:
            btc_trend_info = compute_btc_trend(btc_klines, time_grid[0], w1, w2, min_mom)
            btc_trend_pass = btc_trend_info["passed"]
            logger.info(
                "Backtest %s BTC trend: a1=%.6f a2=%.6f |a1+a2|=%.6f pass=%s",
                session_id, btc_trend_info["a1"], btc_trend_info["a2"],
                abs(btc_trend_info["a1"] + btc_trend_info["a2"]), btc_trend_pass,
            )
        else:
            btc_trend_info = {"a1": 0.0, "a2": 0.0, "passed": True, "p0": 0.0, "p_w1": 0.0, "p_w2": 0.0, "error": "no_klines_provided"}
            logger.warning("Backtest %s: btc_trend_enabled but no klines provided, allowing entry", session_id)

    # Build indexed data per token for efficient lookup
    ob_by_token = _build_index(data.orderbooks)
    delta_by_token = _build_index(data.ob_deltas)
    price_by_token = _build_index(data.prices)
    trade_by_token = _build_index(data.live_trades)

    # Pointers for sequential advancement
    ob_ptrs: dict[str, _Pointer] = {
        tid: _Pointer(ob_by_token.get(tid, [])) for tid in token_ids
    }
    delta_ptrs: dict[str, _Pointer] = {
        tid: _Pointer(delta_by_token.get(tid, [])) for tid in token_ids
    }
    price_ptrs: dict[str, _Pointer] = {
        tid: _Pointer(price_by_token.get(tid, [])) for tid in token_ids
    }
    trade_ptrs: dict[str, _Pointer] = {
        tid: _Pointer(trade_by_token.get(tid, [])) for tid in token_ids
    }

    # Working orderbooks per token
    working_obs: dict[str, dict] = {tid: {"bids": {}, "asks": {}} for tid in token_ids}

    # Account state
    balance = initial_balance
    positions: dict[str, float] = {tid: 0.0 for tid in token_ids}

    recent_trades: list[dict] = []

    # Results
    trades: list[FillInfo] = []
    equity_curve: list[dict] = []
    position_curve: list[dict] = []
    price_curve: list[dict] = []

    # Last known prices per token
    last_mid: dict[str, float] = {tid: 0.0 for tid in token_ids}
    last_trade_prices: dict[str, float] = {tid: 0.0 for tid in token_ids}

    # Init strategy
    try:
        strategy.on_init(merged_config)
    except Exception as e:
        raise ValueError(f"Strategy '{strategy_name}' on_init failed: {e}") from e

    # ── Tick loop ────────────────────────────────────────────────────────────

    for tick_idx, grid_ts in enumerate(time_grid):
        # 1) Advance orderbook snapshots and deltas
        for tid in token_ids:
            new_obs = ob_ptrs[tid].advance_to(grid_ts)
            for ob in new_obs:
                working_obs[tid] = init_working_ob(ob)

            new_deltas = delta_ptrs[tid].advance_to(grid_ts)
            for delta in new_deltas:
                apply_delta(working_obs[tid], delta)

        # 2) Advance prices to update last_mid
        for tid in token_ids:
            new_prices = price_ptrs[tid].advance_to(grid_ts)
            for p in new_prices:
                mid = float(p.get("mid_price", 0))
                if mid > 0:
                    last_mid[tid] = mid

        # 3) Advance live trades
        for tid in token_ids:
            new_trades = trade_ptrs[tid].advance_to(grid_ts)
            for t in new_trades:
                recent_trades.append(t)
                tp = float(t.get("price", 0))
                if tp > 0:
                    last_trade_prices[tid] = tp
        # Trim recent trades
        if len(recent_trades) > 200:
            recent_trades = recent_trades[-200:]

        # 4) Build token snapshots
        token_snapshots: dict[str, TokenSnapshot] = {}
        for tid in token_ids:
            snap = derive_snapshot_from_ob(tid, working_obs[tid])

            # Recompute anchor with last_trade_price context
            if snap.anchor_source == "none" or (snap.spread >= SPREAD_WIDE and last_trade_prices[tid] > 0):
                anchor, src = compute_anchor_price(
                    snap.best_bid, snap.best_ask, snap.mid_price, snap.spread,
                    snap.bid_levels, snap.ask_levels, last_trade_prices[tid],
                )
                snap.anchor_price = round(anchor, 6)
                snap.anchor_source = src

            # If no orderbook data yet, use last_mid from prices
            if snap.mid_price == 0 and last_mid[tid] > 0:
                anchor = last_trade_prices[tid] if last_trade_prices[tid] > 0 else last_mid[tid]
                snap = TokenSnapshot(
                    token_id=tid,
                    mid_price=last_mid[tid],
                    best_bid=last_mid[tid],
                    best_ask=last_mid[tid],
                    spread=0.0,
                    anchor_price=round(anchor, 6),
                    anchor_source="last_trade" if last_trade_prices[tid] > 0 else "mid",
                    bid_levels=snap.bid_levels,
                    ask_levels=snap.ask_levels,
                )
            elif snap.mid_price > 0:
                last_mid[tid] = snap.mid_price
            token_snapshots[tid] = snap

        # 5) Compute equity
        positions_value = sum(
            positions.get(tid, 0) * last_mid.get(tid, 0) for tid in token_ids
        )
        equity = balance + positions_value

        # 6) Build TickContext
        ctx = TickContext(
            timestamp=grid_ts,
            index=tick_idx,
            total_ticks=total_ticks,
            tokens=token_snapshots,
            balance=round(balance, 6),
            positions=dict(positions),
            equity=round(equity, 6),
            initial_balance=initial_balance,
            trade_history=recent_trades[-50:],
        )

        # 7) Call strategy
        signals = strategy.on_tick(ctx)

        # 8) Execute signals (filter BUY if BTC trend did not pass)
        for signal in signals:
            if not btc_trend_pass and signal.side == "BUY":
                continue
            snap = token_snapshots.get(signal.token_id)
            if snap is None:
                continue

            fill = execute_signal(
                signal=signal,
                token_snapshot_bid_levels=snap.bid_levels,
                token_snapshot_ask_levels=snap.ask_levels,
                mid_price=snap.mid_price,
                balance=balance,
                positions=positions,
                timestamp=grid_ts,
            )
            if fill is not None:
                balance = fill.balance_after
                trades.append(fill)
                strategy.on_fill(fill)

        # 9) Record equity curve (sample every tick or every N ticks)
        if tick_idx % max(1, total_ticks // 1000) == 0 or tick_idx == total_ticks - 1:
            positions_value = sum(
                positions.get(tid, 0) * last_mid.get(tid, 0) for tid in token_ids
            )
            equity = balance + positions_value
            equity_curve.append({
                "timestamp": grid_ts,
                "equity": round(equity, 6),
                "balance": round(balance, 6),
                "positions_value": round(positions_value, 6),
            })

            # Record price curve at same sampling rate
            for tid in token_ids:
                if last_mid.get(tid, 0) > 0:
                    snap = token_snapshots.get(tid)
                    price_curve.append({
                        "timestamp": grid_ts,
                        "token_id": tid,
                        "mid_price": round(last_mid[tid], 6),
                        "anchor_price": round(snap.anchor_price, 6) if snap else round(last_mid[tid], 6),
                        "anchor_source": snap.anchor_source if snap else "mid",
                        "best_bid": round(snap.best_bid, 6) if snap else 0.0,
                        "best_ask": round(snap.best_ask, 6) if snap else 0.0,
                        "spread": round(snap.spread, 6) if snap else 0.0,
                        "last_trade_price": round(last_trade_prices.get(tid, 0), 6),
                    })

        # 10) Record position curve (on trade or periodically)
        if trades and trades[-1].timestamp == grid_ts:
            for tid in token_ids:
                position_curve.append({
                    "timestamp": grid_ts,
                    "token_id": tid,
                    "quantity": round(positions.get(tid, 0), 6),
                })

    # ── Finalize ─────────────────────────────────────────────────────────────

    strategy_summary = strategy.on_end()

    # ── Settlement inference ─────────────────────────────────────────────────
    # Binary prediction markets settle at 1.0 (YES) or 0.0 (NO).
    # User-specified result takes priority; otherwise infer from final price.
    resolved_settlement: dict[str, float] = {}
    if settlement_result:
        resolved_settlement = dict(settlement_result)
    else:
        for tid in token_ids:
            price = last_mid.get(tid, 0.0)
            if price >= 0.95:
                resolved_settlement[tid] = 1.0
            elif price <= 0.05:
                resolved_settlement[tid] = 0.0
            else:
                resolved_settlement[tid] = round(price, 6)

    # Final equity uses settlement prices instead of last mid
    final_positions_value = sum(
        positions.get(tid, 0) * resolved_settlement.get(tid, last_mid.get(tid, 0))
        for tid in token_ids
    )
    final_equity = balance + final_positions_value

    duration = time.monotonic() - t_start

    session = BacktestSession(
        session_id=session_id,
        strategy=strategy_name,
        slug=slug,
        initial_balance=initial_balance,
        status="completed",
        created_at=datetime.now(timezone.utc).isoformat(),
        duration_seconds=round(duration, 3),
        trades=trades,
        equity_curve=equity_curve,
        position_curve=position_curve,
        price_curve=price_curve,
        strategy_summary=strategy_summary,
        config=merged_config,
        final_equity=round(final_equity, 6),
        final_positions=dict(positions),
        settlement_result=resolved_settlement,
        btc_trend_info=btc_trend_info,
    )
    return session
