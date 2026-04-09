"""Sensitivity analysis — sweep a single parameter across N steps and measure impact."""

from __future__ import annotations

import asyncio
import logging
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone

from config import config
from core.data_loader import load_archive
from core.evaluator import evaluate
from core.registry import StrategyRegistry
from core.runner import run_backtest

logger = logging.getLogger(__name__)


# ── Types ────────────────────────────────────────────────────────────────────


@dataclass
class SweepPoint:
    """One data point in a sensitivity sweep."""

    param_value: float
    metrics: dict = field(default_factory=dict)
    total_trades: int = 0
    error: str | None = None


@dataclass
class SensitivityResult:
    """Result of a single-parameter sensitivity analysis."""

    task_id: str
    param_key: str
    slug: str
    strategy: str
    base_config: dict
    initial_balance: float
    steps: int
    param_min: float
    param_max: float
    points: list[SweepPoint] = field(default_factory=list)
    status: str = "running"  # "running" | "completed" | "failed"
    created_at: str = ""
    elapsed_seconds: float = 0.0
    error: str | None = None


# ── Engine ───────────────────────────────────────────────────────────────────


class SensitivityAnalyzer:
    """Run parameter sweep backtests for sensitivity analysis."""

    def __init__(self, registry: StrategyRegistry) -> None:
        self._registry = registry
        self._tasks: dict[str, SensitivityResult] = {}
        self._sem = asyncio.Semaphore(config.max_concurrency)

    async def submit(
        self,
        strategy: str,
        slug: str,
        base_config: dict,
        param_key: str,
        initial_balance: float = 100.0,
        steps: int = 10,
        param_min: float | None = None,
        param_max: float | None = None,
    ) -> SensitivityResult:
        """Submit a sensitivity sweep.  Returns the task immediately; runs in background."""
        schema = self._registry.get_param_schema()
        param_info = schema.get(param_key)
        if not param_info:
            raise ValueError(f"Unknown parameter: {param_key}")

        p_min = param_min if param_min is not None else param_info.get("min", 0)
        p_max = param_max if param_max is not None else param_info.get("max", 1)

        task_id = uuid.uuid4().hex[:12]
        result = SensitivityResult(
            task_id=task_id,
            param_key=param_key,
            slug=slug,
            strategy=strategy,
            base_config=base_config,
            initial_balance=initial_balance,
            steps=steps,
            param_min=p_min,
            param_max=p_max,
            created_at=datetime.now(timezone.utc).isoformat(),
        )
        self._tasks[task_id] = result
        asyncio.create_task(self._run_sweep(result))
        return result

    async def _run_sweep(self, result: SensitivityResult) -> None:
        """Execute the parameter sweep."""
        t0 = asyncio.get_event_loop().time()
        try:
            # Pre-load data once
            data = await asyncio.to_thread(load_archive, config.data_dir, result.slug)

            # Generate sweep values
            steps = max(result.steps, 2)
            step_size = (result.param_max - result.param_min) / (steps - 1)
            sweep_values = [result.param_min + i * step_size for i in range(steps)]

            # Run backtests concurrently
            async def _run_one(val: float) -> SweepPoint:
                async with self._sem:
                    cfg = {**result.base_config, result.param_key: val}
                    try:
                        session = await asyncio.to_thread(
                            run_backtest,
                            self._registry,
                            result.strategy,
                            result.slug,
                            cfg,
                            result.initial_balance,
                            data,
                        )
                        metrics = evaluate(session)
                        return SweepPoint(
                            param_value=round(val, 6),
                            metrics=asdict(metrics),
                            total_trades=metrics.total_trades,
                        )
                    except Exception as exc:
                        logger.warning("Sweep point %s=%s failed: %s", result.param_key, val, exc)
                        return SweepPoint(param_value=round(val, 6), error=str(exc))

            points = await asyncio.gather(*[_run_one(v) for v in sweep_values])
            result.points = list(points)
            result.status = "completed"
        except Exception as exc:
            logger.error("Sensitivity sweep %s failed: %s", result.task_id, exc)
            result.status = "failed"
            result.error = str(exc)
        finally:
            result.elapsed_seconds = round(asyncio.get_event_loop().time() - t0, 2)

    def get_task(self, task_id: str) -> SensitivityResult | None:
        return self._tasks.get(task_id)

    def list_tasks(self) -> list[SensitivityResult]:
        return list(self._tasks.values())
