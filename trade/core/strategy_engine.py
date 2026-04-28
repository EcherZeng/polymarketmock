"""Strategy engine — loads and manages live trading strategies with composite support.

Supports:
- Single strategy: one preset config for all sessions
- Composite strategy: multiple branches, select by BTC amplitude per session
"""

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


class CompositeConfig:
    """Composite strategy configuration — branches selected by BTC amplitude.

    Mirrors the backtest composite_presets structure:
    {
        "composite_name": "btc_adaptive",
        "btc_windows": {"btc_trend_window_1": 5, "btc_trend_window_2": 10},
        "branches": [
            {"label": "aggressive", "preset_name": "...", "min_momentum": 0.005, "config": {...}},
            {"label": "balanced", "preset_name": "...", "min_momentum": 0.002, "config": {...}},
            {"label": "conservative", "preset_name": "...", "min_momentum": 0.0, "config": {...}},
        ]
    }
    """

    def __init__(self, detail: dict) -> None:
        self.name: str = detail.get("composite_name", "unnamed_composite")
        btc_windows = detail.get("btc_windows", {})
        self.window_1: int = btc_windows.get("btc_trend_window_1", 5)
        self.window_2: int = btc_windows.get("btc_trend_window_2", 10)

        # Branches sorted descending by min_momentum (highest first)
        branches = detail.get("branches", [])
        self.branches: list[dict] = sorted(
            branches, key=lambda b: b.get("min_momentum", 0), reverse=True
        )

    def select_branch(self, amplitude: float) -> dict | None:
        """Select the first branch where amplitude >= min_momentum.

        Returns the branch dict (with 'config' key) or None if no match.
        """
        for branch in self.branches:
            min_mom = branch.get("min_momentum", 0)
            if amplitude >= min_mom:
                logger.info(
                    "Composite branch matched: '%s' (amp=%.6f >= min=%.4f)",
                    branch.get("label", "?"), amplitude, min_mom,
                )
                return branch
        return None

    @property
    def btc_min_momentum(self) -> float:
        """Lowest momentum threshold across all branches (for trend pass check)."""
        if not self.branches:
            return 0.0
        return min(b.get("min_momentum", 0) for b in self.branches)

    def to_dict(self) -> dict:
        return {
            "composite_name": self.name,
            "btc_windows": {
                "btc_trend_window_1": self.window_1,
                "btc_trend_window_2": self.window_2,
            },
            "branches": self.branches,
        }
