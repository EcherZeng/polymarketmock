"""FastAPI application — Strategy Backtest Engine."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

import api.state as state
from api.result_store import BatchStore, ResultStore
from config import config
from core.data_scanner import load_token_map
from core.batch_runner import BatchRunner, BatchTask
from core.types import BacktestSession

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")

    # Load token map
    load_token_map(config.data_dir)

    # Scan strategies
    state.registry.scan(config.strategies_dir)
    logger.info("Loaded %d strategies", len(state.registry.list_strategies()))

    # ── Init persistent stores ───────────────────────────────────────────
    state.result_store = ResultStore(config.results_dir)
    state.result_store.load()

    state.batch_store = BatchStore(config.results_dir / "batches")
    state.batch_store.load()

    # ── Init batch runner with persistence callbacks ─────────────────────
    from api.execution import store_session, _serialize_workflow, _build_result_summary

    def _on_result(session: BacktestSession) -> None:
        """Persist individual results immediately when a slug completes."""
        store_session(session)

    def _on_batch_complete(task: BatchTask) -> None:
        """Persist batch summary when the entire batch finishes."""
        if state.batch_store is None:
            return
        results_summary: dict[str, dict] = {}
        for slug, session in task.results.items():
            results_summary[slug] = _build_result_summary(session)
        workflows: dict[str, dict] = {}
        for slug, wf in task.workflows.items():
            workflows[slug] = _serialize_workflow(wf)
        state.batch_store.put(task.batch_id, {
            "batch_id": task.batch_id,
            "strategy": task.strategy,
            "slugs": task.slugs,
            "status": task.status,
            "total": task.total,
            "completed": task.completed_count,
            "created_at": task.created_at,
            "results": results_summary,
            "errors": task.errors,
            "workflows": workflows,
        })

    state.batch_runner = BatchRunner(
        state.registry,
        on_result=_on_result,
        on_batch_complete=_on_batch_complete,
    )

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
