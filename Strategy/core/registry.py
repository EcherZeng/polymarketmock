"""Strategy registry — scans and loads strategy classes at startup."""

from __future__ import annotations

import importlib.util
import logging
from pathlib import Path

from core.base_strategy import BaseStrategy

logger = logging.getLogger(__name__)


class StrategyRegistry:
    """Discovers and registers all BaseStrategy subclasses from a directory."""

    def __init__(self) -> None:
        self._strategies: dict[str, type[BaseStrategy]] = {}

    def scan(self, directory: Path) -> None:
        """Scan a directory for .py files containing BaseStrategy subclasses."""
        if not directory.exists():
            logger.warning("Strategies directory not found: %s", directory)
            return

        for py_file in sorted(directory.glob("*.py")):
            if py_file.name.startswith("_"):
                continue
            try:
                spec = importlib.util.spec_from_file_location(py_file.stem, py_file)
                if spec is None or spec.loader is None:
                    continue
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)

                for attr_name in dir(module):
                    cls = getattr(module, attr_name)
                    if (
                        isinstance(cls, type)
                        and issubclass(cls, BaseStrategy)
                        and cls is not BaseStrategy
                    ):
                        self._strategies[cls.name] = cls
                        logger.info("Registered strategy: %s (%s)", cls.name, py_file.name)
            except Exception as e:
                logger.warning("Failed to load strategy from %s: %s", py_file.name, e)

    def list_strategies(self) -> list[dict]:
        """Return metadata for all registered strategies."""
        return [
            {
                "name": cls.name,
                "description": cls.description,
                "version": cls.version,
                "default_config": cls.default_config,
            }
            for cls in self._strategies.values()
        ]

    def get(self, name: str) -> type[BaseStrategy] | None:
        """Get a strategy class by name."""
        return self._strategies.get(name)

    def has(self, name: str) -> bool:
        return name in self._strategies
