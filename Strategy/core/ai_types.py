"""AI Optimizer data structures — RoundResult, OptimizeTask, serialization."""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass, field


# ── Data structures ──────────────────────────────────────────────────────────


@dataclass
class RoundResult:
    """Result of a single optimization round."""

    round_number: int
    configs: list[dict] = field(default_factory=list)  # configs tried this round
    digests: list[dict] = field(default_factory=list)  # compact results per config
    ai_reasoning: str = ""  # AI's explanation for parameter choices
    best_metric_value: float = 0.0
    duration_ms: float = 0.0


@dataclass
class OptimizeTask:
    """Tracks an AI optimization task across multiple rounds."""

    task_id: str
    strategy: str
    slugs: list[str]
    base_config: dict
    optimize_target: str  # metric name to optimize
    max_rounds: int
    runs_per_round: int
    initial_balance: float
    settlement_result: dict[str, float] | None = None
    param_keys: list[str] = field(default_factory=list)
    active_params: list[str] = field(default_factory=list)

    status: str = "running"  # "running" | "completed" | "cancelled" | "failed"
    created_at: str = ""
    started_at: str = ""
    finished_at: str = ""
    current_round: int = 0
    total_runs: int = 0
    completed_runs: int = 0

    rounds: list[RoundResult] = field(default_factory=list)
    all_digests: list[dict] = field(default_factory=list)  # accumulated across rounds
    market_profiles: dict[str, dict] = field(default_factory=dict)
    best_config: dict = field(default_factory=dict)
    best_metric: float = float("-inf")
    best_session_id: str = ""
    best_total_trades: int = 0
    error: str = ""  # kept for backward compat (last fatal error)
    errors: list[dict] = field(default_factory=list)  # accumulated structured errors
    persist_errors: list[str] = field(default_factory=list)  # callback persistence failures

    # AI interaction log
    ai_messages: list[dict] = field(default_factory=list)


# ── Serialization helpers ────────────────────────────────────────────────────


def _sanitize_floats(obj):
    """Recursively replace inf/nan floats with JSON-safe values."""
    if isinstance(obj, float):
        if math.isnan(obj):
            return None
        if math.isinf(obj):
            return None
        return obj
    if isinstance(obj, dict):
        return {k: _sanitize_floats(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_sanitize_floats(v) for v in obj]
    return obj


def task_to_dict(task: OptimizeTask) -> dict:
    """Serialize an OptimizeTask to a JSON-safe dict."""
    d = asdict(task)
    return _sanitize_floats(d)


def task_from_dict(d: dict) -> OptimizeTask:
    """Deserialize a dict back to an OptimizeTask."""
    rounds_raw = d.pop("rounds", [])
    rounds = []
    for r in rounds_raw:
        rounds.append(RoundResult(**r))
    # Handle -inf sentinel stored as None or -9999
    best_metric = d.get("best_metric")
    if best_metric is None or best_metric == -9999.0:
        d["best_metric"] = float("-inf")
    d["rounds"] = rounds
    return OptimizeTask(**d)
