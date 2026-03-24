from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers import account, backtest, markets, trading
from app.storage.data_collector import start_collector, stop_collector
from app.storage.redis_store import close_redis, init_redis


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_redis()
    collector_task = await start_collector()
    yield
    await stop_collector(collector_task)
    await close_redis()


app = FastAPI(
    title="Polymarket Mock Trading API",
    description="模拟交易平台 — 代理 Polymarket 真实数据，提供模拟买卖/限价单/结算/回测",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(markets.router, prefix="/api", tags=["Markets"])
app.include_router(trading.router, prefix="/api/trading", tags=["Trading"])
app.include_router(account.router, prefix="/api/account", tags=["Account"])
app.include_router(backtest.router, prefix="/api/backtest", tags=["Backtest"])


@app.get("/api/health")
async def health():
    return {"status": "ok"}
