"""FastAPI application — Strategy Backtest Engine."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.state import registry, batch_runner as _batch_runner_ref
import api.state as state
from config import config
from core.data_scanner import load_token_map
from core.batch_runner import BatchRunner

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")

    # Load token map
    load_token_map(config.data_dir)

    # Scan strategies
    state.registry.scan(config.strategies_dir)
    logger.info("Loaded %d strategies", len(state.registry.list_strategies()))

    # Init batch runner
    state.batch_runner = BatchRunner(state.registry)

    yield

    logger.info("Strategy engine shutting down")


app = FastAPI(
    title="Strategy Backtest Engine",
    description="独立策略回测引擎 — 历史数据回放 + 评估指标计算",
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

# Import routers after app is created to avoid circular imports
from api.strategies import router as strategies_router
from api.data import router as data_router
from api.execution import router as execution_router
from api.results import router as results_router

app.include_router(strategies_router, tags=["Strategies"])
app.include_router(data_router, tags=["Data"])
app.include_router(execution_router, tags=["Execution"])
app.include_router(results_router, tags=["Results"])


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "strategies": len(state.registry.list_strategies()),
        "data_dir": str(config.data_dir),
    }
