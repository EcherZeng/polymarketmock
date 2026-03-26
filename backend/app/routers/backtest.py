"""Backtest API routes."""

from __future__ import annotations

import json

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from starlette.responses import StreamingResponse

from app.models.backtest import BacktestRequest, BacktestResult
from app.services.backtest_engine import (
    create_replay_session,
    execute_replay_trade,
    generate_replay_stream,
    get_backtest_markets,
    get_replay_snapshot,
    get_replay_timeline,
    run_backtest,
)
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


# ── Replay endpoints ─────────────────────────────────────────────────────────


@router.get("/replay/{slug:path}/timeline")
async def replay_timeline(slug: str):
    """获取归档场次的时间轴（所有可用时间点）。"""
    timeline = await get_replay_timeline(slug)
    if not timeline.get("timestamps"):
        raise HTTPException(status_code=404, detail=f"No archived data for {slug}")
    return timeline


@router.get("/replay/{slug:path}/snapshot")
async def replay_snapshot(
    slug: str,
    t: str = Query(..., description="Timestamp ISO"),
):
    """获取指定时间点的完整快照（orderbook + price）。"""
    return await get_replay_snapshot(slug, t)


@router.get("/replay/{slug:path}/stream")
async def replay_stream(
    slug: str,
    start_index: int = Query(0, ge=0),
    speed: float = Query(1.0, gt=0, le=20),
):
    """SSE 流式推送回放快照，按真实时间戳间隔 / speed 倍率控速。"""

    async def event_generator():
        async for snapshot in generate_replay_stream(slug, start_index, speed):
            data = json.dumps(snapshot, ensure_ascii=False)
            yield f"data: {data}\n\n"
        yield "event: end\ndata: {}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


class CreateReplaySessionReq(BaseModel):
    initial_balance: float = Field(10000, gt=0)


@router.post("/replay/{slug:path}/session")
async def create_session(slug: str, req: CreateReplaySessionReq):
    """创建回放交易会话（独立上下文）。"""
    return await create_replay_session(slug, req.initial_balance)


class ReplayTradeReq(BaseModel):
    session_id: str
    timestamp: str
    token_id: str
    side: str  # BUY or SELL
    amount: float = Field(gt=0)


@router.post("/replay/{slug:path}/trade")
async def replay_trade(slug: str, req: ReplayTradeReq):
    """在回放上下文中执行模拟交易。"""
    result = await execute_replay_trade(
        session_id=req.session_id,
        slug=slug,
        timestamp=req.timestamp,
        token_id=req.token_id,
        side=req.side,
        amount=req.amount,
    )
    if result.get("error"):
        raise HTTPException(status_code=400, detail=result["error"])
    return result
