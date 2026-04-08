"""AI config parser — parse, validate, and clamp LLM-generated parameter configs."""

from __future__ import annotations

import json
import re


def parse_ai_configs(
    raw: str,
    param_schema: dict,
    runs_per_round: int,
) -> tuple[list[dict], str]:
    """Parse and validate AI-generated configs.

    Returns (configs, reason).
    Clamps values to schema min/max. Discards invalid entries.
    """
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        # Try to extract JSON from markdown code block
        match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", raw, re.DOTALL)
        if match:
            parsed = json.loads(match.group(1))
        else:
            raise ValueError(f"Failed to parse AI response as JSON: {raw[:200]}")

    configs_raw = parsed.get("configs", [])
    reason = parsed.get("reason", "")

    if not isinstance(configs_raw, list):
        configs_raw = [configs_raw]

    configs: list[dict] = []
    for cfg in configs_raw[:runs_per_round]:
        if not isinstance(cfg, dict):
            continue
        # Clamp to schema ranges
        clamped: dict = {}
        for key, val in cfg.items():
            if key not in param_schema:
                clamped[key] = val
                continue
            schema = param_schema[key]
            ptype = schema.get("type", "float")
            if ptype == "bool":
                clamped[key] = bool(val)
            elif ptype == "int":
                v = int(val)
                if "min" in schema:
                    v = max(v, int(schema["min"]))
                if "max" in schema:
                    v = min(v, int(schema["max"]))
                clamped[key] = v
            elif ptype == "float":
                v = float(val)
                if "min" in schema:
                    v = max(v, float(schema["min"]))
                if "max" in schema:
                    v = min(v, float(schema["max"]))
                clamped[key] = round(v, 6)
            else:
                clamped[key] = val
        configs.append(clamped)

    return configs, reason
