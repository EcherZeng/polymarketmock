"""Real-time trade inference — detects trades by comparing consecutive orderbook snapshots."""

from __future__ import annotations

from datetime import datetime, timezone


def detect_trades(
    token_id: str,
    prev_book: dict,
    curr_book: dict,
) -> list[dict]:
    """Compare two orderbook snapshots and infer trades that occurred between them.

    Heuristics:
    1. If last_trade_price changed → a trade happened at that price.
    2. Consumed ask levels → BUY trades; consumed bid levels → SELL trades.
    3. Size reductions on existing levels → partial fills.
    """
    trades: list[dict] = []
    now = datetime.now(timezone.utc).isoformat()
    ts = datetime.now(timezone.utc).timestamp()

    prev_ltp = float(prev_book.get("last_trade_price", "0") or "0")
    curr_ltp = float(curr_book.get("last_trade_price", "0") or "0")

    # Build level maps: price → size
    prev_asks = _level_map(prev_book.get("asks", []))
    curr_asks = _level_map(curr_book.get("asks", []))
    prev_bids = _level_map(prev_book.get("bids", []))
    curr_bids = _level_map(curr_book.get("bids", []))

    # Detect consumed/reduced ask levels → implies BUY
    buy_volume = 0.0
    buy_cost = 0.0
    for price_str, prev_size in prev_asks.items():
        curr_size = curr_asks.get(price_str, 0.0)
        if curr_size < prev_size:
            consumed = prev_size - curr_size
            buy_volume += consumed
            buy_cost += consumed * float(price_str)

    # Detect consumed/reduced bid levels → implies SELL
    sell_volume = 0.0
    sell_cost = 0.0
    for price_str, prev_size in prev_bids.items():
        curr_size = curr_bids.get(price_str, 0.0)
        if curr_size < prev_size:
            consumed = prev_size - curr_size
            sell_volume += consumed
            sell_cost += consumed * float(price_str)

    if buy_volume > 0.5:
        avg_price = buy_cost / buy_volume
        trades.append({
            "timestamp": now,
            "ts": ts,
            "token_id": token_id,
            "side": "BUY",
            "price": round(avg_price, 6),
            "size": round(buy_volume, 2),
            "inferred": True,
        })

    if sell_volume > 0.5:
        avg_price = sell_cost / sell_volume
        trades.append({
            "timestamp": now,
            "ts": ts,
            "token_id": token_id,
            "side": "SELL",
            "price": round(avg_price, 6),
            "size": round(sell_volume, 2),
            "inferred": True,
        })

    # If no volume change detected but last_trade_price changed → small trade
    if not trades and curr_ltp > 0 and abs(curr_ltp - prev_ltp) > 0.0001:
        side = "BUY" if curr_ltp > prev_ltp else "SELL"
        trades.append({
            "timestamp": now,
            "ts": ts,
            "token_id": token_id,
            "side": side,
            "price": round(curr_ltp, 6),
            "size": 0,
            "inferred": True,
        })

    return trades


def _level_map(levels: list[dict]) -> dict[str, float]:
    """Convert list of {price, size} dicts to price→size map."""
    result: dict[str, float] = {}
    for lv in levels:
        p = str(lv.get("price", "0"))
        s = float(lv.get("size", "0") or "0")
        result[p] = result.get(p, 0.0) + s
    return result


def ws_trade_to_record(data: dict) -> dict:
    """Convert a WS last_trade_price event to the standard realtime trade format."""
    ts_ms = data.get("timestamp", "0")
    ts = float(ts_ms) / 1000 if ts_ms else 0
    return {
        "timestamp": datetime.fromtimestamp(ts, tz=timezone.utc).isoformat() if ts else "",
        "ts": ts,
        "token_id": data.get("asset_id", ""),
        "side": data.get("side", "UNKNOWN"),
        "price": round(float(data.get("price", "0")), 6),
        "size": round(float(data.get("size", "0")), 2),
        "inferred": False,
        "transaction_hash": data.get("transaction_hash", ""),
    }
