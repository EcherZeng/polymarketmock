"""FastAPI application for the trade service."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.auth import ApiKeyMiddleware
from api.routes import init_routes, router
from api.ws_handler import init_ws, ws_router
from config import settings
from core.btc_price import BtcPriceStreamer
from core.data_store import DataStore
from core.executor_factory import create_executor
from core.live_hub import LiveHub
from core.market_scanner import MarketScanner
from core.position_tracker import PositionTracker
from core.session_manager import SessionManager
from core.settlement_tracker import SettlementTracker


@asynccontextmanager
async def lifespan(app: FastAPI):
    # ── Startup ───────────────────────────────────────────────
    scanner = MarketScanner()
    executor = create_executor(settings.executor_mode)
    tracker = PositionTracker(initial_balance=settings.initial_balance)
    settlement = SettlementTracker()
    store = DataStore()
    hub = LiveHub()
    btc_streamer = BtcPriceStreamer(hub)

    await store.start()
    await scanner.start()
    await executor.start()
    await btc_streamer.start()

    # ── P0-2: Sync balance from API (real mode only) ──────────
    if settings.executor_mode == "real" and executor.is_ready:
        real_balance = await executor.get_balance()
        if real_balance is not None:
            tracker.set_balance(real_balance)

    # ── P0-5: Verify allowance for SELL (real mode only) ──────
    if settings.executor_mode == "real" and executor.is_ready:
        await executor.check_allowance()

    # ── P0-3: Restore positions from DuckDB ───────────────────
    await store.restore_positions(tracker)

    manager = SessionManager(
        scanner=scanner,
        executor=executor,
        tracker=tracker,
        settlement=settlement,
        store=store,
        hub=hub,
        btc_streamer=btc_streamer,
    )
    await manager.start()

    # Inject into routes & ws handler
    init_routes(manager, tracker, store, btc_streamer)
    init_ws(hub, manager, tracker, store, btc_streamer)

    # Store refs on app for access
    app.state.scanner = scanner
    app.state.executor = executor
    app.state.tracker = tracker
    app.state.settlement = settlement
    app.state.store = store
    app.state.manager = manager
    app.state.hub = hub
    app.state.btc_streamer = btc_streamer

    yield

    # ── Shutdown ──────────────────────────────────────────────
    await btc_streamer.stop()
    await manager.stop()
    await scanner.stop()
    await executor.stop()
    await settlement.close()
    await store.stop()


app = FastAPI(
    title="Polymarket Live Trade Service",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(ApiKeyMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router, prefix="/trade-api")
app.include_router(ws_router, prefix="/trade-api")
