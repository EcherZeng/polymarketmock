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
