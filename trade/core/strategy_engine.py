"""Strategy engine — loads and manages the active live trading strategy."""

from __future__ import annotations

import logging

from strategies.base_live import BaseLiveStrategy
from strategies.btc_15m_live import Btc15mLiveStrategy

logger = logging.getLogger(__name__)

# Strategy registry
_STRATEGIES: dict[str, type[BaseLiveStrategy]] = {
    "btc_15m_live": Btc15mLiveStrategy,
}


def get_strategy(name: str = "btc_15m_live") -> BaseLiveStrategy:
    """Instantiate a strategy by name."""
    cls = _STRATEGIES.get(name)
    if cls is None:
        raise ValueError(f"Unknown strategy: {name}. Available: {list(_STRATEGIES.keys())}")
    return cls()


def list_strategies() -> list[dict]:
    """List all available strategies with metadata."""
    return [
        {
            "name": cls.name,
            "description": cls.description,
            "version": cls.version,
            "default_config": cls.default_config,
        }
        for cls in _STRATEGIES.values()
    ]
