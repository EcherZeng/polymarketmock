"""Trade service configuration — env-driven via pydantic-settings."""

from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings

_TRADE_DIR = Path(__file__).resolve().parent


class TradeSettings(BaseSettings):
    # ── Polymarket credentials ────────────────────────────────────────────────
    poly_private_key: str = ""
    poly_funder_address: str = ""
    poly_signature_type: int = 1        # 0=EOA, 1=POLY_PROXY (Google/Email), 2=GNOSIS_SAFE
    poly_api_key: str = ""
    poly_api_secret: str = ""
    poly_api_passphrase: str = ""

    # ── Polymarket API URLs ───────────────────────────────────────────────────
    gamma_api_url: str = "https://gamma-api.polymarket.com"
    clob_api_url: str = "https://clob.polymarket.com"
    ws_url: str = "wss://ws-subscriptions-clob.polymarket.com/ws/market"

    # ── Service ───────────────────────────────────────────────────────────────
    port: int = 8073
    host: str = "0.0.0.0"
    data_dir: Path = _TRADE_DIR / "data"
    log_level: str = "INFO"

    # ── API Authentication ────────────────────────────────────────────────────
    api_key: str = ""                   # Bearer token for API access; empty = no auth

    # ── Execution mode ────────────────────────────────────────────────────────
    executor_mode: str = "mock"         # "real" | "mock"

    # ── Market scanning ───────────────────────────────────────────────────────
    scan_interval_s: int = 120          # Gamma API poll interval (2 min, 15-min sessions)
    scan_slug_prefix: str = "btc-updown-15m"
    scan_duration_s: int = 900          # 15 minutes
    scan_slots_before: int = 1          # past sessions to keep
    scan_slots_after: int = 2           # future sessions to discover

    # ── WebSocket ─────────────────────────────────────────────────────────────
    ws_ping_interval: int = 10          # app-level PING every N seconds
    ws_reconnect_max: int = 30          # exponential backoff cap (seconds)

    # ── Session management ────────────────────────────────────────────────────
    session_prepare_ahead_s: int = 60   # pre-connect WS N seconds before start

    # ── Order execution ───────────────────────────────────────────────────────
    min_trade_usdc: float = 10.0        # Polymarket minimum
    order_timeout_s: int = 30           # cancel unfilled order after N seconds
    order_max_retries: int = 3          # retry failed orders (when holding position)
    chain_id: int = 137                 # Polygon mainnet

    # ── Settlement ────────────────────────────────────────────────────────────
    settlement_poll_interval_s: int = 60  # poll Gamma for resolution (1 min)
    settlement_poll_max_s: int = 600      # give up after 10 min

    # ── Strategy defaults ─────────────────────────────────────────────────────
    initial_balance: float = 0.0        # for PnL tracking (0 = auto-detect from API)

    # ── Strategy service ──────────────────────────────────────────────────────
    strategy_service_url: str = "http://localhost:8072"  # Strategy backtest engine

    model_config = {"env_prefix": "TRADE_", "env_file": _TRADE_DIR / ".env"}


settings = TradeSettings()
