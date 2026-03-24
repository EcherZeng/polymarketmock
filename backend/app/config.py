from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Polymarket API URLs
    gamma_api_url: str = "https://gamma-api.polymarket.com"
    clob_api_url: str = "https://clob.polymarket.com"

    # Redis
    redis_url: str = "redis://localhost:6379"

    # Data storage path for Parquet files
    data_dir: str = "./data"

    # Cache TTL (seconds)
    cache_ttl_markets: int = 60
    cache_ttl_orderbook: int = 5
    cache_ttl_midpoint: int = 3

    # Data collector intervals (seconds)
    collector_orderbook_interval: int = 15
    collector_price_interval: int = 60

    # Limit order check interval (seconds)
    limit_order_check_interval: int = 5

    # Live event: faster orderbook polling (seconds)
    collector_live_interval: int = 2

    # Max realtime trades per token kept in Redis
    realtime_trades_max: int = 500

    model_config = {"env_prefix": "PM_"}


settings = Settings()
