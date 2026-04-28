"""Orderbook builder — maintains live orderbook state from WS events.

Mirrors the logic from Strategy/core/orderbook_state.py and
Strategy/core/anchor_pricing.py but adapted for live trading context.
"""

from __future__ import annotations

from models.types import TokenMarketData

# ── Anchor pricing thresholds ────────────────────────────────────────────────

SPREAD_TIGHT = 0.05
SPREAD_WIDE = 0.15
MICRO_DEPTH = 3


def weighted_micro_price(
    bid_levels: list[tuple[float, float]],
    ask_levels: list[tuple[float, float]],
    depth: int = MICRO_DEPTH,
) -> float | None:
    """Depth-weighted micro-price using top N levels from each side."""
    top_bids = bid_levels[:depth]
    top_asks = ask_levels[:depth]
    if not top_bids or not top_asks:
        return None

    sum_bid_vol = sum(v for _, v in top_bids)
    sum_ask_vol = sum(v for _, v in top_asks)
    denominator = len(top_bids) * sum_ask_vol + len(top_asks) * sum_bid_vol
    if denominator <= 0:
        return None

    micro = (
        sum(p * sum_ask_vol for p, _ in top_bids)
        + sum(p * sum_bid_vol for p, _ in top_asks)
    )
    return round(micro / denominator, 6)


def compute_anchor_price(
    best_bid: float,
    best_ask: float,
    mid: float,
    spread: float,
    bid_levels: list[tuple[float, float]],
    ask_levels: list[tuple[float, float]],
    last_trade_price: float = 0.0,
) -> tuple[float, str]:
    """Compute tiered anchor price based on orderbook conditions."""
    if not best_bid and not best_ask:
        if last_trade_price > 0:
            return last_trade_price, "last_trade"
        return 0.0, "none"

    if not best_bid or not best_ask:
        if last_trade_price > 0:
            return last_trade_price, "last_trade"
        return mid, "mid"

    if spread < SPREAD_TIGHT:
        return mid, "mid"
    elif spread < SPREAD_WIDE:
        micro = weighted_micro_price(bid_levels, ask_levels)
        return (micro, "micro") if micro is not None else (mid, "mid")
    else:
        if last_trade_price > 0:
            return last_trade_price, "last_trade"
        micro = weighted_micro_price(bid_levels, ask_levels)
        return (micro, "micro") if micro is not None else (mid, "mid")


# ── Orderbook state ──────────────────────────────────────────────────────────


class OrderbookBuilder:
    """Maintains live orderbook state for multiple tokens."""

    def __init__(self) -> None:
        # token_id → {"bids": {price_str: size}, "asks": {price_str: size}}
        self._books: dict[str, dict[str, dict[str, float]]] = {}
        # token_id → last trade price
        self._last_trade: dict[str, float] = {}
        # token_id → price history (append only within session)
        self._price_history: dict[str, list[float]] = {}

    def reset(self) -> None:
        """Clear all state for a new session."""
        self._books.clear()
        self._last_trade.clear()
        self._price_history.clear()

    # ── WS event handlers ─────────────────────────────────────

    def handle_book(self, asset_id: str, data: dict) -> None:
        """Handle full orderbook snapshot ('book' event)."""
        market = data.get("market", asset_id)
        bids: dict[str, float] = {}
        asks: dict[str, float] = {}

        for entry in data.get("bids", []):
            price = str(round(float(entry.get("price", 0)), 6))
            size = float(entry.get("size", 0))
            if size > 0:
                bids[price] = size

        for entry in data.get("asks", []):
            price = str(round(float(entry.get("price", 0)), 6))
            size = float(entry.get("size", 0))
            if size > 0:
                asks[price] = size

        self._books[asset_id] = {"bids": bids, "asks": asks}

    def handle_price_change(self, asset_id: str, data: dict) -> None:
        """Handle orderbook delta ('price_change' event)."""
        book = self._books.get(asset_id)
        if not book:
            # No snapshot yet — skip delta
            return

        changes = data.get("changes", [])
        if not changes:
            # Single change format
            side = data.get("side", "")
            price = str(round(float(data.get("price", 0)), 6))
            size = float(data.get("size", 0))
            key = "bids" if side == "BUY" else "asks"
            if size == 0:
                book[key].pop(price, None)
            else:
                book[key][price] = size
            return

        for change in changes:
            side = change.get("side", "")
            price = str(round(float(change.get("price", 0)), 6))
            size = float(change.get("size", 0))
            key = "bids" if side == "BUY" else "asks"
            if size == 0:
                book[key].pop(price, None)
            else:
                book[key][price] = size

    def handle_last_trade_price(self, asset_id: str, data: dict) -> None:
        """Handle 'last_trade_price' event."""
        price = float(data.get("price", 0))
        if price > 0:
            self._last_trade[asset_id] = price
            hist = self._price_history.setdefault(asset_id, [])
            hist.append(price)
            # Cap history to prevent unbounded growth
            if len(hist) > 200:
                self._price_history[asset_id] = hist[-200:]

    def handle_best_bid_ask(self, asset_id: str, data: dict) -> None:
        """Handle 'best_bid_ask' event — update top-of-book if no full book."""
        # This is a lightweight update; full book events are preferred
        pass

    # ── Snapshot derivation ───────────────────────────────────

    def get_market_data(self, token_id: str) -> TokenMarketData:
        """Derive current TokenMarketData from orderbook state."""
        book = self._books.get(token_id, {"bids": {}, "asks": {}})
        bids = book.get("bids", {})
        asks = book.get("asks", {})

        best_bid = max((float(p) for p in bids if bids[p] > 0), default=0.0)
        best_ask = min((float(p) for p in asks if asks[p] > 0), default=0.0)
        mid = (best_bid + best_ask) / 2 if (best_bid and best_ask) else best_bid or best_ask
        spread = (best_ask - best_bid) if (best_bid and best_ask) else 0.0

        bid_levels = sorted(
            [(float(p), s) for p, s in bids.items() if s > 0],
            key=lambda x: x[0],
            reverse=True,
        )
        ask_levels = sorted(
            [(float(p), s) for p, s in asks.items() if s > 0],
            key=lambda x: x[0],
        )

        last_trade = self._last_trade.get(token_id, 0.0)

        anchor_price, anchor_source = compute_anchor_price(
            best_bid, best_ask, mid, spread, bid_levels, ask_levels, last_trade,
        )

        return TokenMarketData(
            token_id=token_id,
            mid_price=round(mid, 6),
            best_bid=round(best_bid, 6),
            best_ask=round(best_ask, 6),
            spread=round(spread, 6),
            anchor_price=round(anchor_price, 6),
            anchor_source=anchor_source,
            last_trade_price=last_trade,
            bid_levels=bid_levels,
            ask_levels=ask_levels,
        )

    def get_price_history(self, token_id: str) -> list[float]:
        return list(self._price_history.get(token_id, []))

    def has_book(self, token_id: str) -> bool:
        return token_id in self._books
