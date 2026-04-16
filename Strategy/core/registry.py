"""Strategy registry — loads presets and registers strategy classes.

Preset persistence uses a two-file overlay model:
  - strategy_presets.json       (git-tracked, read-only defaults)
  - strategy_presets_user.json  (git-ignored, user overrides)

On load the user file is deep-merged on top of defaults so that:
  - git pull updates built-in presets / schema without losing user changes
  - user customisations (unified_rules tweaks, new presets) survive restarts
On save only the user file is written.
"""

from __future__ import annotations

import copy
import importlib.util
import inspect
import json
import logging
from pathlib import Path

from core.base_strategy import BaseStrategy

logger = logging.getLogger(__name__)

_STRATEGY_DIR = Path(__file__).resolve().parent.parent
_PRESETS_DEFAULT_PATH = _STRATEGY_DIR / "strategy_presets.json"

# User overrides: prefer /app/user_config (Docker volume) → fallback to local dir
_USER_CONFIG_DIR = Path("/app/user_config")
if not _USER_CONFIG_DIR.exists():
    _USER_CONFIG_DIR = _STRATEGY_DIR
_PRESETS_USER_PATH = _USER_CONFIG_DIR / "strategy_presets_user.json"


def _load_json(path: Path) -> dict:
    if path.exists():
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def _deep_merge(base: dict, override: dict) -> dict:
    """Recursively merge *override* into a copy of *base*."""
    result = copy.deepcopy(base)
    for key, val in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(val, dict):
            result[key] = _deep_merge(result[key], val)
        else:
            result[key] = copy.deepcopy(val)
    return result


def _load_presets_merged() -> tuple[dict, dict]:
    """Return (merged_presets, user_overrides).

    merged = defaults ← user overlay.  user_overrides is kept separately so
    we know what to persist back to the user file.
    """
    defaults = _load_json(_PRESETS_DEFAULT_PATH)
    user = _load_json(_PRESETS_USER_PATH)
    merged = _deep_merge(defaults, user)
    return merged, user


def _save_user_file(user_data: dict) -> None:
    with open(_PRESETS_USER_PATH, "w", encoding="utf-8") as f:
        json.dump(user_data, f, indent=2, ensure_ascii=False)


class StrategyRegistry:
    """Loads UnifiedStrategy class, then registers one entry per preset config."""

    def __init__(self) -> None:
        self._strategy_cls: type[BaseStrategy] | None = None
        self._presets: dict = {}  # merged presets (defaults + user)
        self._user_overrides: dict = {}  # user-only delta (persisted separately)
        self._configs: dict[str, dict] = {}  # name → merged default_config

    def scan(self, directory: Path) -> None:
        """Scan strategies/ for the concrete strategy class, then register presets."""
        self._presets, self._user_overrides = _load_presets_merged()
        unified_rules = self._presets.get("unified_rules", {})
        strategies_map = self._presets.get("strategies", {})

        # Find the concrete strategy class
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
                        and not inspect.isabstract(cls)
                    ):
                        self._strategy_cls = cls
                        logger.info("Loaded strategy class: %s (%s)", cls.name, py_file.name)
            except Exception as e:
                logger.warning("Failed to load strategy from %s: %s", py_file.name, e)

        if self._strategy_cls is None:
            logger.error("No concrete strategy class found in %s", directory)
            return

        # Non-value keys to exclude when merging config
        self._meta_keys = ("builtin", "description")

        # Register one entry per preset
        for preset_name, preset_params in strategies_map.items():
            params = {k: v for k, v in preset_params.items() if k not in self._meta_keys}
            merged = {**unified_rules, **params}
            self._configs[preset_name] = merged
            logger.info("Registered preset: %s", preset_name)

    # ── Query ────────────────────────────────────────────────────────────────

    def normalize_config(self, config: dict) -> dict:
        """Enforce disable_value for dependent params when their toggle is OFF.

        Scans param_schema for params with ``depends_on``.  If the toggle key
        is falsy in *config*, the dependent param is forced to its
        ``disable_value`` (when defined).  Only applies to keys already present
        in *config* — never injects new keys.  Returns a **new** dict.
        """
        schema = self.get_param_schema()
        result = dict(config)
        for key, meta in schema.items():
            if key not in result:
                continue  # param not active — don't inject
            raw_dep = meta.get("depends_on")
            if not raw_dep:
                continue
            toggle_keys = raw_dep if isinstance(raw_dep, list) else [raw_dep]
            # Toggle is OFF → force disable_value (all deps must be present and truthy)
            if not all(result.get(tk) for tk in toggle_keys):
                disable_val = meta.get("disable_value")
                if disable_val is not None:
                    result[key] = disable_val
        return result

    def list_strategies(self) -> list[dict]:
        strategies_map = self._presets.get("strategies", {})
        result = []
        for name, cfg in self._configs.items():
            raw_desc = strategies_map.get(name, {}).get("description", "")
            # description can be i18n dict or plain string
            desc = raw_desc if isinstance(raw_desc, dict) else {"zh": raw_desc, "en": raw_desc}
            builtin = strategies_map.get(name, {}).get("builtin", False)
            result.append({
                "name": name,
                "description": desc,
                "version": self._strategy_cls.version if self._strategy_cls else "0.0.0",
                "default_config": cfg,
                "builtin": builtin,
            })
        return result

    def get_param_schema(self) -> dict:
        """Return parameter schema for frontend form rendering."""
        return self._presets.get("param_schema", {})

    def get_param_groups(self) -> dict:
        """Return parameter group definitions for frontend."""
        return self._presets.get("param_groups", {})

    def get(self, name: str) -> type[BaseStrategy] | None:
        if name in self._configs:
            return self._strategy_cls
        return None

    def get_default_config(self, name: str) -> dict:
        return dict(self._configs.get(name, {}))

    def has(self, name: str) -> bool:
        return name in self._configs

    # ── Preset CRUD ──────────────────────────────────────────────────────────

    def get_presets_data(self) -> dict:
        return dict(self._presets)

    def get_preset(self, name: str) -> dict | None:
        strategies = self._presets.get("strategies", {})
        return strategies.get(name)

    def save_preset(self, name: str, params: dict) -> None:
        """Create or update a preset. Rebuilds merged config. Persists to user file."""
        # Normalize: force disable_value for toggled-off dependent params
        params = self.normalize_config(params)
        strategies = self._presets.setdefault("strategies", {})
        strategies[name] = params
        # Rebuild merged config
        unified_rules = self._presets.get("unified_rules", {})
        clean = {k: v for k, v in params.items() if k not in self._meta_keys}
        self._configs[name] = {**unified_rules, **clean}
        # Persist to user overlay only
        self._user_overrides.setdefault("strategies", {})[name] = params
        _save_user_file(self._user_overrides)
        logger.info("Saved preset: %s", name)

    def delete_preset(self, name: str) -> bool:
        """Delete a user-defined preset. Returns False if builtin or not found."""
        strategies = self._presets.get("strategies", {})
        preset = strategies.get(name)
        if preset is None:
            return False
        if preset.get("builtin", False):
            return False
        del strategies[name]
        self._configs.pop(name, None)
        # Also remove from user overlay
        user_strategies = self._user_overrides.get("strategies", {})
        user_strategies.pop(name, None)
        _save_user_file(self._user_overrides)
        logger.info("Deleted preset: %s", name)
        return True

    def rename_preset(self, old_name: str, new_name: str) -> bool:
        """Rename a preset. Returns False if old not found, is builtin, or new name conflicts."""
        strategies = self._presets.get("strategies", {})
        preset = strategies.get(old_name)
        if preset is None:
            return False
        if preset.get("builtin", False):
            return False
        if new_name in strategies:
            return False
        # Move in merged presets
        strategies[new_name] = strategies.pop(old_name)
        self._configs[new_name] = self._configs.pop(old_name)
        # Move in user overlay
        user_strategies = self._user_overrides.get("strategies", {})
        if old_name in user_strategies:
            user_strategies[new_name] = user_strategies.pop(old_name)
        _save_user_file(self._user_overrides)
        logger.info("Renamed preset: %s -> %s", old_name, new_name)
        return True

    def update_unified_rules(self, rules: dict) -> None:
        """Update the unified rules and rebuild all merged configs."""
        self._presets["unified_rules"] = rules
        unified_rules = rules
        strategies = self._presets.get("strategies", {})
        for preset_name, preset_params in strategies.items():
            clean = {k: v for k, v in preset_params.items() if k not in self._meta_keys}
            self._configs[preset_name] = {**unified_rules, **clean}
        # Persist to user overlay only
        self._user_overrides["unified_rules"] = rules
        _save_user_file(self._user_overrides)
