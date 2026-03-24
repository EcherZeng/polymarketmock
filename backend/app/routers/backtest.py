"""Backtest API routes."""

from __future__ import annotations

from fastapi import APIRouter, Query

from app.models.backtest import BacktestRequest, BacktestResult
from app.services.backtest_engine import get_backtest_markets, run_backtest
from app.storage.duckdb_store import query_prices

router = APIRouter()


@router.get("/markets")
async def list_backtest_markets():
    """List markets with available historical data for backtesting."""
    return get_backtest_markets()


@router.get("/data/{market_id}")
async def get_market_data(
    market_id: str,
    start: str = Query(None, description="Start time ISO"),
    end: str = Query(None, description="End time ISO"),
):
    """Get historical price data for a market."""
    return query_prices(market_id, start_time=start, end_time=end)


@router.post("/replay", response_model=BacktestResult)
async def replay_backtest(req: BacktestRequest):
    """Replay historical data with trade instructions."""
    return await run_backtest(req)
