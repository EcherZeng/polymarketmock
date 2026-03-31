"""Strategy Backtest Engine configuration."""

from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings

_STRATEGY_DIR = Path(__file__).resolve().parent


class StrategyEngineConfig(BaseSettings):
    # Data directory — points to backend/data (read-only via filesystem)
    data_dir: Path = _STRATEGY_DIR.parent / "backend" / "data"

    # Results persistence
    results_dir: Path = _STRATEGY_DIR / "results"

    # Parallel backtest
    max_concurrency: int = 4
    tick_batch_size: int = 1000

    # Strategy loading
    strategies_dir: Path = _STRATEGY_DIR / "strategies"
    price_history_window: int = 60

    # HTTP server
    server_port: int = 8072
    server_host: str = "0.0.0.0"

    model_config = {"env_prefix": "STRATEGY_"}


config = StrategyEngineConfig()
