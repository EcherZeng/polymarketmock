from pathlib import Path

from pydantic_settings import BaseSettings

# Resolve data_dir relative to the backend package, not cwd
_BACKEND_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    # Polymarket API URLs
    gamma_api_url: str = "https://gamma-api.polymarket.com"
    clob_api_url: str = "https://clob.polymarket.com"
    data_api_url: str = "https://data-api.polymarket.com"

    # Redis
    redis_url: str = "redis://localhost:6379"

    # Data storage path for Parquet files
    data_dir: str = str(_BACKEND_DIR / "data")

    # Cache TTL (seconds)
    cache_ttl_markets: int = 60
    cache_ttl_orderbook: int = 5
    cache_ttl_midpoint: int = 1
    cache_ttl_data_trades: int = 3

    # Data collector intervals (seconds)
    collector_orderbook_interval: int = 2
    collector_price_interval: int = 5

    # Limit order check interval (seconds)
    limit_order_check_interval: int = 5

    # Live event: faster orderbook polling (seconds)
    collector_live_interval: int = 1

    # Data API live trades collection interval (seconds)
    collector_live_trades_interval: int = 5

    # Max realtime trades per token kept in Redis
    realtime_trades_max: int = 500

    # Max live trades per market kept in Redis
    live_trades_max: int = 500

    # WebSocket — Polymarket Market Channel
    ws_url: str = "wss://ws-subscriptions-clob.polymarket.com/ws/market"
    ws_ping_interval: int = 10
    ws_reconnect_max: int = 30

    # Parquet buffer — batched writes
    parquet_flush_interval: int = 60   # seconds between auto-flushes
    parquet_flush_threshold: int = 2000  # rows before forced flush

    # Logging
    log_level: str = "INFO"

    model_config = {"env_prefix": "PM_"}


settings = Settings()
