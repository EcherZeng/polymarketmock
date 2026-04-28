"""Composite strategy config — branch selection by BTC amplitude."""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


class CompositeConfig:
    """Branches sorted by min_momentum descending; select first match."""

    def __init__(self, detail: dict) -> None:
        self.name: str = detail.get("composite_name") or detail.get("name") or "unnamed"
        btc_windows = detail.get("btc_windows", {})
        self.window_1: int = btc_windows.get("btc_trend_window_1", 5)
        self.window_2: int = btc_windows.get("btc_trend_window_2", 10)
        self.branches: list[dict] = sorted(
            detail.get("branches", []),
            key=lambda b: b.get("min_momentum", 0),
            reverse=True,
        )

    def select_branch(self, amplitude: float) -> dict | None:
        for branch in self.branches:
            if amplitude >= branch.get("min_momentum", 0):
                logger.info(
                    "Branch matched: '%s' (amp=%.6f >= min=%.4f)",
                    branch.get("label", "?"), amplitude, branch.get("min_momentum", 0),
                )
                return branch
        return None

    @property
    def btc_min_momentum(self) -> float:
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
