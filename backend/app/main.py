from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers import account, backtest, markets, trading, ws
from app.services.auto_recorder import start_auto_recorder, stop_auto_recorder
from app.services.ws_manager import start_ws_manager, stop_ws_manager
from app.storage.data_collector import start_collector, stop_collector
from app.storage.duckdb_store import init_parquet_buffer, shutdown_parquet_buffer
from app.storage.redis_store import close_redis, init_redis


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_parquet_buffer()
    await init_redis()
    ws_mgr = await start_ws_manager()
    collector_task = await start_collector()
    auto_rec = await start_auto_recorder()
    yield
    await stop_auto_recorder()
    await stop_collector(collector_task)
    await stop_ws_manager()
    shutdown_parquet_buffer()
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
app.include_router(ws.router, tags=["WebSocket"])


@app.get("/api/health")
async def health():
    import os
    from app.config import settings
    data_dir = settings.data_dir
    archive_dir = os.path.join(data_dir, "archives")
    archives_exist = os.path.isdir(archive_dir)
    archive_slugs = os.listdir(archive_dir) if archives_exist else []
    slug_files = {}
    for s in archive_slugs[:5]:
        sp = os.path.join(archive_dir, s)
        slug_files[s] = os.listdir(sp) if os.path.isdir(sp) else []
    return {
        "status": "ok",
        "cwd": os.getcwd(),
        "data_dir": data_dir,
        "data_dir_abs": os.path.abspath(data_dir),
        "data_dir_exists": os.path.isdir(data_dir),
        "archives_dir_exists": archives_exist,
        "archive_slugs": archive_slugs,
        "slug_files": slug_files,
    }
