"""模拟完整批量回测路径 — 使用 Registry + Strategy class + Runner，与 API 执行路径一致。

确认修复后代码是否实际工作。
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "Strategy"))

from config import config
from core.data_loader import load_archive
from core.registry import StrategyRegistry
from core.runner import run_backtest

SESSIONS_DIR = Path("backend/data/sessions")

# ── Exactly replicate the API flow ──────────────────────────────────────────

# 1) Registry scan (same as app.py lifespan)
registry = StrategyRegistry()
registry.scan(config.strategies_dir)

strategy_name = "Test预设"

# 2) Show what the registry knows
default_config = registry.get_default_config(strategy_name)
print(f"=== Registry default_config for '{strategy_name}' ===")
for k, v in sorted(default_config.items()):
    print(f"  {k}: {v}")

# 3) Simulate frontend behavior:
#    Frontend does: configValues = {...s.default_config}
#    i.e. it sends ALL default params as the config (unless user edits some)
user_config = dict(default_config)  # Frontend copies all defaults

print(f"\n=== User config (sent by frontend, same as defaults) ===")
print(f"  Keys: {len(user_config)}")

# 4) Show the MERGED config (same as runner.py line)
merged = {**registry.get_default_config(strategy_name), **user_config}
print(f"\n=== Merged config (what strategy receives) ===")
print(f"  use_amplitude_check: {merged.get('use_amplitude_check', 'NOT SET → defaults to True')}")
print(f"  use_reverse_check: {merged.get('use_reverse_check', 'NOT SET → defaults to True')}")
print(f"  use_std_check: {merged.get('use_std_check', 'NOT SET → defaults to True')}")
print(f"  use_drawdown_check: {merged.get('use_drawdown_check', 'NOT SET → defaults to True')}")
print(f"  use_momentum_check: {merged.get('use_momentum_check', 'NOT SET → defaults to True')}")
print(f"  min_price: {merged.get('min_price')}")
print(f"  time_remaining_ratio: {merged.get('time_remaining_ratio')}")
print(f"  momentum_window: {merged.get('momentum_window')}")
print(f"  momentum_min: {merged.get('momentum_min')}")
print(f"  reverse_threshold: {merged.get('reverse_threshold')}")

# 5) Run backtest on all slugs (same as batch_runner)
slugs = sorted(d.name for d in SESSIONS_DIR.iterdir() if d.is_dir())
print(f"\n=== Running batch on {len(slugs)} slugs ===\n")

entered_count = 0
for slug in slugs:
    try:
        data = load_archive(config.data_dir, slug)
        if not data.prices and not data.orderbooks:
            print(f"  {slug}: SKIP (no data)")
            continue

        session = run_backtest(
            registry=registry,
            strategy_name=strategy_name,
            slug=slug,
            user_config=user_config,
            initial_balance=10000,
            data=data,
        )

        trade_count = len(session.trades)
        summary = session.strategy_summary
        entered = summary.get("entered", False)

        if entered:
            entered_count += 1
            print(f"  {slug}: ✓ ENTERED  trades={trade_count}, equity={session.final_equity:.2f}")
        else:
            print(f"  {slug}: ✗ NO ENTRY  trades={trade_count}, equity={session.final_equity:.2f}")

    except Exception as e:
        print(f"  {slug}: ERROR — {e}")

print(f"\n{'═' * 60}")
print(f"Result: {entered_count}/{len(slugs)} entered")
