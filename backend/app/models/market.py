"""Pydantic models for Polymarket market/event/orderbook data."""

from __future__ import annotations

from pydantic import BaseModel, Field


class PriceLevel(BaseModel):
    price: str
    size: str


class OrderbookSchema(BaseModel):
    market: str = ""
    asset_id: str = ""
    timestamp: str = ""
    hash: str = ""
    bids: list[PriceLevel] = []
    asks: list[PriceLevel] = []
    min_order_size: str = "0"
    tick_size: str = "0.01"
    neg_risk: bool = False
    last_trade_price: str = "0"


class MarketSchema(BaseModel):
    id: str = ""
    question: str = ""
    condition_id: str = Field("", alias="conditionId")
    slug: str = ""
    market_type: str = Field("", alias="marketType")
    active: bool = True
    closed: bool = False
    outcomes: list[str] = []
    outcome_prices: list[str] = Field([], alias="outcomePrices")
    liquidity: float = 0
    volume: float = 0
    volume_24hr: float = Field(0, alias="volume24hr")
    last_trade_price: float = Field(0, alias="lastTradePrice")
    best_bid: float = Field(0, alias="bestBid")
    best_ask: float = Field(0, alias="bestAsk")
    spread: float = 0
    clob_token_ids: str = Field("", alias="clobTokenIds")
    order_price_min_tick_size: float = Field(0.01, alias="orderPriceMinTickSize")
    order_min_size: float = Field(0, alias="orderMinSize")
    neg_risk: bool = Field(False, alias="negRisk")
    accepting_orders: bool = Field(True, alias="acceptingOrders")
    enable_order_book: bool = Field(True, alias="enableOrderBook")
    description: str = ""
    end_date: str = Field("", alias="endDate")
    start_date: str = Field("", alias="startDate")
    fee: str = "0"
    maker_base_fee: float = Field(0, alias="makerBaseFee")
    taker_base_fee: float = Field(0, alias="takerBaseFee")

    model_config = {"populate_by_name": True}


class TagSchema(BaseModel):
    id: str = ""
    label: str = ""
    slug: str = ""


class EventSchema(BaseModel):
    id: str = ""
    title: str = ""
    slug: str = ""
    ticker: str = ""
    description: str = ""
    active: bool = True
    closed: bool = False
    category: str = ""
    tags: list[TagSchema] = []
    markets: list[MarketSchema] = []
    liquidity: float = 0
    volume: float = 0
    open_interest: float = Field(0, alias="openInterest")
    start_date: str = Field("", alias="startDate")
    end_date: str = Field("", alias="endDate")
    enable_order_book: bool = Field(True, alias="enableOrderBook")
    neg_risk: bool = Field(False, alias="negRisk")

    model_config = {"populate_by_name": True}


# ── Realtime trade (inferred from orderbook diffs) ──────────────────────────


class RealtimeTrade(BaseModel):
    timestamp: str
    token_id: str
    side: str = ""  # BUY / SELL / UNKNOWN
    price: float = 0
    size: float = 0
    inferred: bool = True


class EventStatusResponse(BaseModel):
    slug: str
    status: str  # upcoming / live / ended / settled
    ended_at: str | None = None
    seconds_remaining: float | None = None
    next_slug: str | None = None


# ── WebSocket event models (Polymarket Market Channel) ──────────────────────


class WsBookEvent(BaseModel):
    event_type: str  # "book"
    asset_id: str
    market: str
    bids: list[PriceLevel]
    asks: list[PriceLevel]
    timestamp: str
    hash: str


class WsPriceChangeItem(BaseModel):
    asset_id: str
    price: str
    size: str
    side: str  # BUY / SELL
    hash: str
    best_bid: str | None = None
    best_ask: str | None = None


class WsPriceChangeEvent(BaseModel):
    event_type: str  # "price_change"
    market: str
    price_changes: list[WsPriceChangeItem]
    timestamp: str


class WsLastTradePriceEvent(BaseModel):
    event_type: str  # "last_trade_price"
    asset_id: str
    market: str
    price: str
    size: str
    side: str  # BUY / SELL
    timestamp: str
    fee_rate_bps: str | None = None
    transaction_hash: str | None = None


class WsBestBidAskEvent(BaseModel):
    event_type: str  # "best_bid_ask"
    asset_id: str
    market: str
    best_bid: str
    best_ask: str
    spread: str
    timestamp: str


class WsTickSizeChangeEvent(BaseModel):
    event_type: str  # "tick_size_change"
    asset_id: str
    market: str
    old_tick_size: str
    new_tick_size: str
    timestamp: str


class WsMarketResolvedEvent(BaseModel):
    event_type: str  # "market_resolved"
    id: str
    market: str
    assets_ids: list[str]
    winning_asset_id: str
    winning_outcome: str
    timestamp: str
    tags: list[str] = []
