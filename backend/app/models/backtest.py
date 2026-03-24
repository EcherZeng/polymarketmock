"""Pydantic models for backtest API."""

from __future__ import annotations

from pydantic import BaseModel, Field


class BacktestTradeInstruction(BaseModel):
    timestamp: str
    side: str  # BUY or SELL
    amount: float = Field(gt=0)


class BacktestRequest(BaseModel):
    market_id: str
    token_id: str
    start_time: str
    end_time: str
    initial_balance: float = Field(gt=0, default=10000)
    trades: list[BacktestTradeInstruction] = []


class BacktestTradeResult(BaseModel):
    timestamp: str
    side: str
    requested_amount: float
    filled_amount: float
    avg_price: float
    total_cost: float
    slippage_pct: float
    balance_after: float


class BacktestResult(BaseModel):
    market_id: str
    token_id: str
    initial_balance: float
    final_balance: float
    total_pnl: float
    total_trades: int
    trade_results: list[BacktestTradeResult] = []
    equity_curve: list[dict] = []


class BacktestMarketInfo(BaseModel):
    market_id: str
    token_id: str
    earliest_data: str
    latest_data: str
    data_points: int
