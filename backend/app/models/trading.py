"""Pydantic models for mock trading: orders, positions, trades, account."""

from __future__ import annotations

import enum
from datetime import datetime

from pydantic import BaseModel, Field


class OrderSide(str, enum.Enum):
    BUY = "BUY"
    SELL = "SELL"


class OrderType(str, enum.Enum):
    MARKET = "MARKET"
    LIMIT = "LIMIT"


class OrderStatus(str, enum.Enum):
    PENDING = "PENDING"
    FILLED = "FILLED"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    CANCELLED = "CANCELLED"


# --- Requests ---


class OrderRequest(BaseModel):
    token_id: str
    side: OrderSide
    type: OrderType = OrderType.MARKET
    amount: float = Field(gt=0, description="Number of shares")
    price: float | None = Field(None, ge=0, le=1, description="Limit price (0-1), required for LIMIT orders")


class EstimateRequest(BaseModel):
    token_id: str
    side: OrderSide
    type: OrderType = OrderType.MARKET
    amount: float = Field(gt=0)
    price: float | None = Field(None, ge=0, le=1)


class InitAccountRequest(BaseModel):
    balance: float = Field(gt=0, description="Initial USDC balance")


class SettleRequest(BaseModel):
    winning_outcome: str = Field(description="Winning outcome, e.g. 'Yes' or 'No'")


# --- Responses ---


class OrderResult(BaseModel):
    order_id: str
    token_id: str
    side: OrderSide
    type: OrderType
    status: OrderStatus
    requested_amount: float
    filled_amount: float
    avg_price: float
    total_cost: float
    slippage_pct: float
    created_at: str
    filled_at: str | None = None


class EstimateResult(BaseModel):
    token_id: str
    side: OrderSide
    estimated_avg_price: float
    estimated_slippage_pct: float
    estimated_total_cost: float
    orderbook_depth_available: float
    # Phase 2: Polymarket-aligned fields
    probability_price: float = 0
    potential_profit_per_share: float = 0
    potential_loss_per_share: float = 0
    complementary_price: float = 0
    complementary_token_id: str = ""


class Position(BaseModel):
    token_id: str
    market_question: str = ""
    outcome: str = ""
    side: OrderSide
    shares: float
    avg_cost: float
    current_price: float = 0
    unrealized_pnl: float = 0
    market_value: float = 0


class AccountOverview(BaseModel):
    balance: float
    initial_balance: float
    total_positions_value: float
    total_unrealized_pnl: float
    total_realized_pnl: float
    total_pnl: float
    positions: list[Position] = []


class TradeRecord(BaseModel):
    order_id: str
    token_id: str
    side: OrderSide
    type: OrderType
    amount: float
    avg_price: float
    total_cost: float
    slippage_pct: float
    timestamp: str


# ── Polymarket Data API trades (real on-chain trades) ────────────────────────


class PolymarketTrade(BaseModel):
    proxy_wallet: str = Field(default="", alias="proxyWallet")
    side: str
    asset: str = ""
    condition_id: str = Field(default="", alias="conditionId")
    size: float = 0
    price: float = 0
    timestamp: int = 0
    title: str = ""
    slug: str = ""
    icon: str = ""
    event_slug: str = Field(default="", alias="eventSlug")
    outcome: str = ""
    outcome_index: int = Field(default=0, alias="outcomeIndex")
    name: str = ""
    pseudonym: str = ""
    transaction_hash: str = Field(default="", alias="transactionHash")

    model_config = {"populate_by_name": True}


class PolymarketTradesResponse(BaseModel):
    trades: list[PolymarketTrade] = []
    count: int = 0
