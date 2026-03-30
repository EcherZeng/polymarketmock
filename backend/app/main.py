import logging
import os
from contextlib import asynccontextmanager
from logging.handlers import RotatingFileHandler

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.routers import account, backtest, markets, trading, ws
from app.routers import monitor as monitor_router
from app.services.auto_recorder import start_auto_recorder, stop_auto_recorder
from app.services.event_registry import start_event_registry, stop_event_registry
from app.services.log_buffer import get_log_handler
from app.services.ws_manager import start_ws_manager, stop_ws_manager
from app.storage.data_collector import start_collector, stop_collector
from app.storage.duckdb_store import init_parquet_buffer, shutdown_parquet_buffer
from app.storage.redis_store import close_redis, init_redis

logger = logging.getLogger(__name__)


def _setup_logging() -> None:
    """Configure root logger with format and level from settings."""
    log_fmt = "%(asctime)s | %(levelname)-7s | %(name)s | %(message)s"
    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper(), logging.INFO),
        format=log_fmt,
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    # Attach in-memory buffer handler for dashboard
    buf_handler = get_log_handler()
    buf_handler.setLevel(getattr(logging, settings.log_level.upper(), logging.INFO))
    buf_handler.setFormatter(logging.Formatter(log_fmt, datefmt="%Y-%m-%d %H:%M:%S"))
    logging.getLogger().addHandler(buf_handler)
    # Rotating file handler for WARNING+ (persisted to disk)
    log_dir = os.path.join(settings.data_dir, "logs")
    os.makedirs(log_dir, exist_ok=True)
    file_handler = RotatingFileHandler(
        os.path.join(log_dir, "error.log"),
        maxBytes=settings.log_file_max_bytes,
        backupCount=settings.log_file_backup_count,
        encoding="utf-8",
    )
    file_handler.setLevel(getattr(logging, settings.log_file_level.upper(), logging.WARNING))
    file_handler.setFormatter(logging.Formatter(log_fmt, datefmt="%Y-%m-%d %H:%M:%S"))
    logging.getLogger().addHandler(file_handler)
    # Quieten noisy third-party loggers
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("websockets").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)


@asynccontextmanager
async def lifespan(app: FastAPI):
    _setup_logging()
    logger.info("=== Polymarket Mock Trading — starting ===")
    init_parquet_buffer()
    logger.info("Parquet buffer initialised")
    await init_redis()
    logger.info("Redis connected")
    registry = await start_event_registry()
    logger.info("Event registry started — %d events loaded",
                sum(len(d) for d in registry._windows.values()))
    ws_mgr = await start_ws_manager()
    logger.info("WebSocket manager started")
    collector_task = await start_collector()
    logger.info("Data collector started")
    auto_rec = await start_auto_recorder()
    logger.info("Auto recorder started")
    logger.info("=== All services ready ===")
    yield
    logger.info("=== Shutting down ===")
    await stop_auto_recorder()
    logger.info("Auto recorder stopped")
    await stop_collector(collector_task)
    logger.info("Data collector stopped")
    await stop_ws_manager()
    logger.info("WebSocket manager stopped")
    await stop_event_registry()
    logger.info("Event registry stopped")
    shutdown_parquet_buffer()
    logger.info("Parquet buffer flushed & closed")
    await close_redis()
    logger.info("Redis closed")
    logger.info("=== Shutdown complete ===")


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
app.include_router(monitor_router.router, prefix="/api", tags=["Monitor"])
app.include_router(ws.router, tags=["WebSocket"])


@app.get("/api/health")
async def health():
    import os
    from app.config import settings
    data_dir = settings.data_dir
    sessions_dir = os.path.join(data_dir, "sessions")
    sessions_exist = os.path.isdir(sessions_dir)
    session_slugs = os.listdir(sessions_dir) if sessions_exist else []
    slug_files = {}
    for s in session_slugs[:5]:
        sp = os.path.join(sessions_dir, s)
        if os.path.isdir(sp):
            contents = os.listdir(sp)
            slug_files[s] = contents
    return {
        "status": "ok",
        "cwd": os.getcwd(),
        "data_dir": data_dir,
        "data_dir_abs": os.path.abspath(data_dir),
        "data_dir_exists": os.path.isdir(data_dir),
        "sessions_dir_exists": sessions_exist,
        "session_slugs": session_slugs,
        "slug_files": slug_files,
    }
