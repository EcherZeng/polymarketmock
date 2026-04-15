"""Validate compact ob_deltas loading: memory, compatibility, correctness.

Run from Strategy root:  python tests/test_compact_deltas.py
"""
import gc
import sys
import time
from pathlib import Path

# Ensure Strategy root is importable
_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_root))

from core.data_scanner import load_token_map
from core.data_loader import (
    _load_compact_parquet,
    _query_parquet,
    _decode_rows,
    load_archive,
)
from config import config

load_token_map(config.data_dir)

SLUG = "btc-updown-15m-1775532600"
BASE = config.data_dir / "sessions" / SLUG / "archive"

print("=" * 70)
print("TEST 1: Compact loading produces correct rows")
print("=" * 70)

compact_rows = _load_compact_parquet(BASE / "ob_deltas.parquet", has_side=True)
dict_rows = _decode_rows(_query_parquet(BASE / "ob_deltas.parquet"), has_side=True)

assert len(compact_rows) == len(dict_rows), (
    f"Row count mismatch: compact={len(compact_rows)} vs dict={len(dict_rows)}"
)
print(f"  Row count: {len(compact_rows)} ✓")

# Spot check first, last, middle rows
for idx in [0, len(compact_rows) // 2, -1]:
    cr = compact_rows[idx]
    dr = dict_rows[idx]
    for key in ["timestamp", "token_id", "side", "price", "size"]:
        cv = cr.get(key)
        dv = dr.get(key)
        # Compare with type coercion (float vs int edge cases)
        if isinstance(cv, float) and isinstance(dv, float):
            assert abs(cv - dv) < 1e-9, f"Row {idx} key '{key}': {cv} != {dv}"
        else:
            assert str(cv) == str(dv), f"Row {idx} key '{key}': {cv!r} != {dv!r}"
    print(f"  Row [{idx}] values match ✓")

# Test .get() with default
assert compact_rows[0].get("nonexistent", "DEFAULT") == "DEFAULT"
print("  .get() with default ✓")

# Test __contains__
assert "timestamp" in compact_rows[0]
assert "nonexistent" not in compact_rows[0]
print("  __contains__ ✓")

del dict_rows
gc.collect()

print()
print("=" * 70)
print("TEST 2: Memory comparison")
print("=" * 70)

# Measure compact rows memory
if compact_rows:
    sample = min(200, len(compact_rows))
    per_row = sum(sys.getsizeof(r) for r in compact_rows[:sample]) / sample
    # Value memory (approximate)
    val_mem = 0
    for r in compact_rows[:sample]:
        for f in r._fields:
            val_mem += sys.getsizeof(getattr(r, f))
    val_per_row = val_mem / sample
    compact_est = (per_row + val_per_row) * len(compact_rows) + sys.getsizeof(compact_rows)
    print(f"  Compact row size: {per_row:.0f} bytes/row (container)")
    print(f"  Compact total est: {compact_est / 1024 / 1024:.1f} MB")

# Measure dict rows memory
dict_rows_2 = _decode_rows(_query_parquet(BASE / "ob_deltas.parquet"), has_side=True)
if dict_rows_2:
    per_row_d = sum(sys.getsizeof(r) for r in dict_rows_2[:sample]) / sample
    val_mem_d = 0
    for r in dict_rows_2[:sample]:
        for v in r.values():
            val_mem_d += sys.getsizeof(v)
    val_per_row_d = val_mem_d / sample
    dict_est = (per_row_d + val_per_row_d) * len(dict_rows_2) + sys.getsizeof(dict_rows_2)
    print(f"  Dict row size: {per_row_d:.0f} bytes/row (container)")
    print(f"  Dict total est: {dict_est / 1024 / 1024:.1f} MB")
    reduction = (1 - compact_est / dict_est) * 100
    print(f"  Memory reduction: {reduction:.0f}%")

del dict_rows_2
gc.collect()

print()
print("=" * 70)
print("TEST 3: Full load_archive produces valid ArchiveData")
print("=" * 70)

t0 = time.monotonic()
data = load_archive(config.data_dir, SLUG)
dt = (time.monotonic() - t0) * 1000

print(f"  Load time: {dt:.0f} ms")
print(f"  prices: {len(data.prices)} rows")
print(f"  orderbooks: {len(data.orderbooks)} rows")
print(f"  ob_deltas: {len(data.ob_deltas)} rows")
print(f"  live_trades: {len(data.live_trades)} rows")

# Verify ob_deltas are compact rows (not dicts)
if data.ob_deltas:
    row0 = data.ob_deltas[0]
    assert hasattr(row0, "_fields"), "ob_deltas should be namedtuple-based"
    assert hasattr(row0, "get"), "ob_deltas rows must have .get()"
    print(f"  ob_deltas[0] type: {type(row0).__name__} ✓")
    print(f"  ob_deltas[0].get('side'): {row0.get('side')} ✓")

# Verify prices/orderbooks/live_trades are still dicts
if data.prices:
    assert isinstance(data.prices[0], dict), "prices should remain dicts"
    print(f"  prices[0] type: dict ✓")
if data.orderbooks:
    assert isinstance(data.orderbooks[0], dict), "orderbooks should remain dicts"
    print(f"  orderbooks[0] type: dict ✓")
if data.live_trades:
    assert isinstance(data.live_trades[0], dict), "live_trades should remain dicts"
    print(f"  live_trades[0] type: dict ✓")

print()
print("=" * 70)
print("TEST 4: Runner compatibility — _build_index, _Pointer, _collect_*")
print("=" * 70)

from core.runner import _build_index, _Pointer, _collect_timestamps, _collect_token_ids

timestamps = _collect_timestamps(data)
token_ids = _collect_token_ids(data)
print(f"  Timestamps: {len(timestamps)} unique")
print(f"  Token IDs: {token_ids}")

delta_by_token = _build_index(data.ob_deltas)
print(f"  Delta index: {len(delta_by_token)} tokens, {sum(len(v) for v in delta_by_token.values())} rows")

# Test _Pointer with compact rows
for tid in token_ids:
    ptr = _Pointer(delta_by_token.get(tid, []))
    if ptr.items:
        first_ts = ptr.items[0].get("timestamp", "")
        consumed = ptr.advance_to(first_ts)
        assert len(consumed) > 0, "Pointer should advance"
        print(f"  Pointer advance for {tid[:20]}...: {len(consumed)} rows consumed ✓")

print()
print("=" * 70)
print("TEST 5: apply_delta compatibility")
print("=" * 70)

from core.orderbook_state import apply_delta

working_ob = {"bids": {}, "asks": {}}
if data.ob_deltas:
    delta = data.ob_deltas[0]
    apply_delta(working_ob, delta)
    side_key = "bids" if delta.get("side") == "BUY" else "asks"
    price_str = str(round(float(delta.get("price", 0)), 6))
    expected_size = float(delta.get("size", 0))
    if expected_size > 0:
        assert price_str in working_ob[side_key], f"Price {price_str} should be in {side_key}"
        assert working_ob[side_key][price_str] == expected_size
    print(f"  apply_delta with compact row: {side_key}[{price_str}] = {expected_size} ✓")

print()
print("=" * 70)
print("ALL TESTS PASSED ✓")
print("=" * 70)
