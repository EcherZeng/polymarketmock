"""诊断脚本 — 扫描所有 slug，逐 tick 追踪每个入场检查，输出每条数据被拦截的原因统计。

使用方法: cd polymarketmock && python _diag_entry.py
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "Strategy"))

from config import config as app_config
from core.data_loader import load_archive
from core.runner import (
    _build_time_grid,
    _collect_timestamps,
    _collect_token_ids,
    _build_index,
    _Pointer,
    _init_working_ob,
    _apply_delta,
    _derive_snapshot_from_ob,
)

# ── Test预设 当前参数 ────────────────────────────────────────────────────────
PARAMS = {
    "min_price": 0.55,
    "time_remaining_ratio": 0.5,
    "momentum_window": 120,
    "momentum_min": 0.02,
    "use_momentum": True,
    "use_reverse": True,
    "reverse_tick_window": 15,
    "reverse_threshold": 0.03,
}

DATA_DIR = Path("backend/data")
SESSIONS_DIR = DATA_DIR / "sessions"


def simulate_slug(slug: str) -> dict:
    """对单条数据跑完整 tick 循环，统计每个检查的拦截次数和实际数值范围。"""
    data = load_archive(DATA_DIR, slug)
    if not data.prices and not data.orderbooks:
        return {"slug": slug, "error": "no data"}

    token_ids = _collect_token_ids(data)
    all_ts = _collect_timestamps(data)
    time_grid = _build_time_grid(all_ts)
    total_ticks = len(time_grid)

    ob_by_token = _build_index(data.orderbooks)
    delta_by_token = _build_index(data.ob_deltas)
    price_by_token = _build_index(data.prices)

    ob_ptrs = {t: _Pointer(ob_by_token.get(t, [])) for t in token_ids}
    delta_ptrs = {t: _Pointer(delta_by_token.get(t, [])) for t in token_ids}
    price_ptrs = {t: _Pointer(price_by_token.get(t, [])) for t in token_ids}

    working_obs = {t: {"bids": {}, "asks": {}} for t in token_ids}
    last_mid = {t: 0.0 for t in token_ids}
    price_history: dict[str, list[float]] = {t: [] for t in token_ids}

    p = PARAMS
    min_history = p["reverse_tick_window"]

    # 统计
    reject = {
        "time_gate": 0,
        "min_price": 0,
        "min_history": 0,
        "momentum_zero": 0,
        "momentum_low": 0,
        "reverse": 0,
    }
    # 记录实际观察到的数值范围
    momentum_vals: list[float] = []
    mid_vals: dict[str, list[float]] = {t: [] for t in token_ids}
    reverse_drops: list[float] = []
    entry_tick = None

    for tick_idx, grid_ts in enumerate(time_grid):
        # advance orderbook
        for tid in token_ids:
            for ob in ob_ptrs[tid].advance_to(grid_ts):
                working_obs[tid] = _init_working_ob(ob)
            for delta in delta_ptrs[tid].advance_to(grid_ts):
                _apply_delta(working_obs[tid], delta)

        # advance prices
        for tid in token_ids:
            for pr in price_ptrs[tid].advance_to(grid_ts):
                mid = float(pr.get("mid_price", 0))
                if mid > 0:
                    last_mid[tid] = mid

        # build snapshots & forward-fill
        for tid in token_ids:
            snap = _derive_snapshot_from_ob(tid, working_obs[tid])
            if snap.mid_price > 0:
                last_mid[tid] = snap.mid_price
        for tid in token_ids:
            if last_mid[tid] > 0:
                price_history[tid].append(last_mid[tid])
                if len(price_history[tid]) > app_config.price_history_window:
                    price_history[tid] = price_history[tid][-app_config.price_history_window:]

        # time gate
        remaining_ratio = (total_ticks - tick_idx) / total_ticks if total_ticks > 0 else 1.0
        if remaining_ratio > p["time_remaining_ratio"]:
            reject["time_gate"] += 1
            continue

        for tid in token_ids:
            mid = last_mid[tid]
            mid_vals[tid].append(mid)

            if mid <= 0 or mid < p["min_price"]:
                reject["min_price"] += 1
                continue

            history = price_history.get(tid, [])
            if len(history) < min_history:
                reject["min_history"] += 1
                continue

            # momentum
            if p["use_momentum"]:
                m_slice = history[-p["momentum_window"]:]
                if m_slice[0] == 0:
                    reject["momentum_zero"] += 1
                    continue
                momentum = (m_slice[-1] - m_slice[0]) / m_slice[0]
                momentum_vals.append(momentum)
                if momentum < p["momentum_min"]:
                    reject["momentum_low"] += 1
                    continue

            # reverse
            if p["use_reverse"]:
                rw = min(p["reverse_tick_window"], len(history))
                recent = history[-rw:]
                drops = []
                for i in range(1, len(recent)):
                    if recent[i - 1] > 0:
                        change = (recent[i] - recent[i - 1]) / recent[i - 1]
                        if change < 0:
                            drops.append(change)
                has_reverse = any(d < -p["reverse_threshold"] for d in drops)
                if drops:
                    reverse_drops.extend(drops)
                if has_reverse:
                    reject["reverse"] += 1
                    continue

            # WOULD ENTER
            entry_tick = tick_idx
            break

        if entry_tick is not None:
            break

    return {
        "slug": slug,
        "total_ticks": total_ticks,
        "token_ids": token_ids,
        "entry_tick": entry_tick,
        "reject": reject,
        "momentum_range": (
            (round(min(momentum_vals), 6), round(max(momentum_vals), 6))
            if momentum_vals
            else None
        ),
        "mid_price_ranges": {
            tid: (round(min(vs), 4), round(max(vs), 4)) if vs else None
            for tid, vs in mid_vals.items()
        },
        "reverse_drop_range": (
            (round(min(reverse_drops), 6), round(max(reverse_drops), 6))
            if reverse_drops
            else None
        ),
        "reverse_drop_count": len(reverse_drops),
        "reverse_over_threshold": sum(1 for d in reverse_drops if d < -p["reverse_threshold"]),
    }


def main() -> None:
    slugs = sorted(
        d.name for d in SESSIONS_DIR.iterdir() if d.is_dir()
    )
    print(f"扫描 {len(slugs)} 条数据，Test预设参数:")
    for k, v in PARAMS.items():
        print(f"  {k}: {v}")
    print()

    entered_count = 0
    for slug in slugs:
        print(f"{'─' * 60}")
        print(f"▸ {slug}")
        result = simulate_slug(slug)

        if "error" in result:
            print(f"  ✗ {result['error']}")
            continue

        total = result["total_ticks"]
        entry = result["entry_tick"]
        rej = result["reject"]

        if entry is not None:
            entered_count += 1
            print(f"  ✓ 入场 tick {entry}/{total}")
        else:
            print(f"  ✗ 未入场 (total_ticks={total})")

        # rejection breakdown
        print(f"  拦截统计:")
        for k, v in rej.items():
            if v > 0:
                print(f"    {k}: {v} 次")

        # mid price ranges
        for tid, rng in result["mid_price_ranges"].items():
            if rng:
                print(f"  Token {tid} 入场窗口内 mid: [{rng[0]}, {rng[1]}]")

        # momentum range
        mr = result["momentum_range"]
        if mr:
            print(f"  动量值范围: [{mr[0]}, {mr[1]}]  (阈值: {PARAMS['momentum_min']})")

        # reverse drops
        rd = result["reverse_drop_range"]
        if rd:
            print(
                f"  反转下跌范围: [{rd[0]}, {rd[1]}]  "
                f"(超阈值{PARAMS['reverse_threshold']}: "
                f"{result['reverse_over_threshold']}/{result['reverse_drop_count']})"
            )
        print()

    print(f"{'═' * 60}")
    print(f"结果: {entered_count}/{len(slugs)} 条数据有入场")

    if entered_count == 0:
        print()
        print("══ 建议调整方向 ══")
        print("根据数据特征，尝试放宽以下参数:")
        # Collect all momentum/reverse stats
        all_momentum = []
        all_reverse = []
        for slug in slugs:
            r = simulate_slug(slug)
            if "error" in r:
                continue
            if r["momentum_range"]:
                all_momentum.append(r["momentum_range"])
            if r["reverse_drop_range"]:
                all_reverse.append(r["reverse_drop_range"])

        if all_momentum:
            max_mom = max(m[1] for m in all_momentum)
            min_mom = min(m[0] for m in all_momentum)
            print(f"  所有数据动量范围: [{min_mom}, {max_mom}]")
            if max_mom < PARAMS["momentum_min"]:
                print(f"  → momentum_min 建议降至 {round(max_mom * 0.8, 4)}")

        if all_reverse:
            min_drop = min(d[0] for d in all_reverse)
            print(f"  所有数据最大反转跌幅: {min_drop}")
            if abs(min_drop) > PARAMS["reverse_threshold"]:
                suggest = round(abs(min_drop) * 1.2, 4)
                print(f"  → reverse_threshold 建议升至 {suggest} 或关闭 use_reverse_check")


if __name__ == "__main__":
    main()
