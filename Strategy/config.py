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
    slug_timeout: int = 600  # per-slug timeout in seconds (10 min)
    batch_chunk_size: int = 20  # max slugs to gather concurrently at once

    # Strategy loading
    strategies_dir: Path = _STRATEGY_DIR / "strategies"

    # HTTP server
    server_port: int = 8072
    server_host: str = "0.0.0.0"

    # Backend API (for data deletion — data volume is read-only)
    backend_url: str = "http://localhost:8071"

    # LLM (DeepSeek / OpenAI-compatible)
    llm_api_url: str = "https://api.deepseek.com/v1/chat/completions"
    llm_api_key: str = ""
    llm_default_model: str = "deepseek-chat"
    llm_available_models: list[str] = [
        "deepseek-chat",
        "deepseek-reasoner",
    ]

    model_config = {"env_prefix": "STRATEGY_", "env_file": _STRATEGY_DIR / ".env"}


config = StrategyEngineConfig()
