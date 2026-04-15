"""FastAPI application — Strategy Backtest Engine."""

from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware

import api.state as state
from api.result_store import BatchStore, PortfolioStore, ResultStore
from config import config
from core.data_scanner import load_token_map
from core.batch_runner import BatchRunner, BatchTask
from core.backtest_executor import BacktestExecutor
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

    # Reconcile tasks that were "running" when the server last shut down.
    # They can never complete now (asyncio tasks are gone), so mark them interrupted.
    # values() returns lightweight summaries; only load full data for running tasks.
    interrupted_count = 0
    for summary in state.batch_store.values():
        if summary.get("status") == "running":
            bid = summary.get("batch_id")
            full = state.batch_store.get(bid) if bid else None
            if full:
                full["status"] = "interrupted"
                state.batch_store.put(bid, full)
                interrupted_count += 1
    if interrupted_count:
        logger.warning("Marked %d orphaned batch tasks as 'interrupted' after restart", interrupted_count)

    state.portfolio_store = PortfolioStore(config.results_dir / "portfolios")
    state.portfolio_store.load()

    # ── Init batch runner with persistence callbacks ─────────────────────
    from api.execution import store_session, _serialize_workflow, _build_result_summary

    def _on_result(session: BacktestSession) -> None:
        """Persist individual results immediately when a slug completes.

        cache=False: during batch runs we persist hundreds of sessions;
        keeping them all in the LRU cache would defeat lazy-loading.
        """
        store_session(session, cache=False)

    def _on_batch_complete(task: BatchTask) -> None:
        """Persist batch summary when the entire batch finishes."""
        if state.batch_store is None:
            return
        results_summary: dict[str, dict] = {}
        # Use full sessions if still in memory
        for slug, session in task.results.items():
            results_summary[slug] = _build_result_summary(session)
        # Fill in from lightweight summaries (sessions already released)
        for slug, summary in task.results_summary.items():
            if slug not in results_summary:
                from dataclasses import asdict
                results_summary[slug] = asdict(summary)
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

    # ── Service-level backtest pool ─────────────────────────────────
    # cpu_sem:     limits concurrent run_backtest threads (= max_concurrency).
    # archive_sem: limits concurrent ArchiveData objects in memory (= max_concurrency).
    # Both are shared by BacktestExecutor so the total memory/CPU cost is
    # bounded regardless of how many callers (BatchRunner, AIOptimizer,
    # SensitivityAnalyzer) run simultaneously.
    state.backtest_semaphore = asyncio.Semaphore(config.max_concurrency)  # cpu_sem
    archive_sem = asyncio.Semaphore(config.max_concurrency)

    executor = BacktestExecutor(
        state.registry,
        cpu_sem=state.backtest_semaphore,
        archive_sem=archive_sem,
        on_result=_on_result,
    )

    state.batch_runner = BatchRunner(
        state.registry,
        executor=executor,
        on_batch_complete=_on_batch_complete,
    )

    # ── Init AI optimizer ────────────────────────────────────────────
    if not config.llm_api_key:
        logger.warning(
            "STRATEGY_LLM_API_KEY is not set — AI optimization will fail. "
            "Set it in .env or as an environment variable."
        )
    else:
        logger.info("LLM API key configured (model: %s)", config.llm_default_model)

    from core.ai_optimizer import AIOptimizer
    ai_tasks_dir = config.results_dir / "ai_tasks"
    state.ai_optimizer = AIOptimizer(
        state.registry,
        executor=executor,
        tasks_dir=ai_tasks_dir,
    )
    state.ai_optimizer.load_tasks()

    # Reconcile AI tasks that were "running" when the server last shut down.
    ai_interrupted = 0
    for task in state.ai_optimizer.list_tasks():
        if task.status == "running":
            task.status = "interrupted"
            state.ai_optimizer._persist_task(task)
            ai_interrupted += 1
    if ai_interrupted:
        logger.warning("Marked %d orphaned AI optimize tasks as 'interrupted' after restart", ai_interrupted)

    # ── Init sensitivity analyzer ────────────────────────────────────
    from core.sensitivity import SensitivityAnalyzer
    state.sensitivity_analyzer = SensitivityAnalyzer(state.registry, semaphore=state.backtest_semaphore)

    yield

    logger.info("Strategy engine shutting down")
    executor.close()


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

# Compress large JSON responses (batch task details can be several MB)
app.add_middleware(GZipMiddleware, minimum_size=1000)

# Import routers after app is created to avoid circular imports
from api.strategies import router as strategies_router
from api.data import router as data_router
from api.execution import router as execution_router
from api.results import router as results_router
from api.presets import router as presets_router
from api.portfolios import router as portfolios_router
from api.ai_optimize import router as ai_optimize_router
from api.sensitivity import router as sensitivity_router

app.include_router(strategies_router, tags=["Strategies"])
app.include_router(data_router, tags=["Data"])
app.include_router(execution_router, tags=["Execution"])
app.include_router(results_router, tags=["Results"])
app.include_router(presets_router, tags=["Presets"])
app.include_router(portfolios_router, tags=["Portfolios"])
app.include_router(ai_optimize_router)
app.include_router(sensitivity_router)


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "strategies": len(state.registry.list_strategies()),
        "data_dir": str(config.data_dir),
    }
