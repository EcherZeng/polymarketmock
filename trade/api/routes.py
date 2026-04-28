"""Trade service API — aggregates all route modules."""

from __future__ import annotations

from fastapi import APIRouter

from api.config_routes import init_config
from api.config_routes import router as config_router
from api.control_routes import init_control
from api.control_routes import router as control_router
from api.monitor_routes import init_monitor
from api.monitor_routes import router as monitor_router

router = APIRouter()
router.include_router(monitor_router)
router.include_router(config_router)
router.include_router(control_router)


def init_routes(session_manager, tracker, store, btc_streamer=None) -> None:
    """Inject dependencies into all route modules."""
    init_monitor(session_manager, tracker, store, btc_streamer)
    init_config(session_manager)
    init_control(session_manager)

