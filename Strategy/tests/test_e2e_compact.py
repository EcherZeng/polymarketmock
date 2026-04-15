"""End-to-end validation: full backtest with compact ob_deltas.

Runs a complete backtest on a real slug to verify the entire pipeline
(load → index → tick loop → apply_delta → evaluate) works with
the compact namedtuple-based ob_deltas.
"""
import gc
import sys
import time
from pathlib import Path

_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_root))

from core.data_scanner import load_token_map
from core.data_loader import load_archive
from core.evaluator import evaluate, compute_drawdown_curve, compute_drawdown_events
from core.registry import StrategyRegistry
from core.runner import run_backtest
from config import config

load_token_map(config.data_dir)

registry = StrategyRegistry()
registry.scan(config.strategies_dir)

SLUG = "btc-updown-15m-1775532600"

print("=" * 70)
print("E2E TEST: Full backtest with compact ob_deltas")
print("=" * 70)

# 1. Load data
t0 = time.monotonic()
data = load_archive(config.data_dir, SLUG)
dt_load = (time.monotonic() - t0) * 1000

print(f"  Data loaded in {dt_load:.0f} ms")
print(f"  ob_deltas type: {type(data.ob_deltas[0]).__name__} ({len(data.ob_deltas)} rows)")

# Verify compact rows
assert hasattr(data.ob_deltas[0], "_fields"), "ob_deltas must be namedtuple"
assert data.ob_deltas[0].get("side") in ("BUY", "SELL"), "side must be decoded"

# 2. Run backtest
strategies = registry.list_strategies()
strategy_name = strategies[0]["name"] if strategies else "unified"
print(f"  Using strategy: {strategy_name}")

t1 = time.monotonic()
session = run_backtest(
    registry=registry,
    strategy_name=strategy_name,
    slug=SLUG,
    user_config={},
    initial_balance=10000.0,
    data=data,
)
dt_run = (time.monotonic() - t1) * 1000

print(f"  Backtest completed in {dt_run:.0f} ms")
print(f"  Status: {session.status}")
print(f"  Trades: {len(session.trades)}")
print(f"  Equity curve points: {len(session.equity_curve)}")
print(f"  Final equity: {session.final_equity:.2f}")

# 3. Evaluate
t2 = time.monotonic()
metrics = evaluate(session)
session.metrics = metrics
session.drawdown_curve = compute_drawdown_curve(session.equity_curve)
session.drawdown_events = compute_drawdown_events(session.equity_curve)
dt_eval = (time.monotonic() - t2) * 1000

print(f"  Evaluate completed in {dt_eval:.0f} ms")
print(f"  Total return: {metrics.total_return_pct:.4f}")
print(f"  Sharpe: {metrics.sharpe_ratio:.4f}")
print(f"  Win rate: {metrics.win_rate:.4f}")
print(f"  Max drawdown: {metrics.max_drawdown:.4f}")

# 4. Verify session can be serialized (for persist)
from dataclasses import asdict
result = asdict(session)
assert "session_id" in result
assert "equity_curve" in result
print(f"  Serialization: OK ({len(str(result))} chars)")

# 5. Memory after full pipeline
del data
gc.collect()
print()
print(f"  Total time: {dt_load + dt_run + dt_eval:.0f} ms")

print()
print("=" * 70)
print("E2E TEST PASSED ✓")
print("=" * 70)
