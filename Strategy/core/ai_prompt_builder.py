"""AI Optimizer prompt construction — system prompt, round prompts, group prompts."""

from __future__ import annotations

import json


# ── System prompt ────────────────────────────────────────────────────────────

SYSTEM_PROMPT = (
    "你是一个 Polymarket 预测市场量化策略参数优化专家。\n\n"
    "## Polymarket 市场特征（与股票市场的关键差异）\n"
    "Polymarket 是二元事件预测市场，与传统股票市场有本质区别：\n"
    "- **价格区间 [0, 1]**：每个 token 价格代表事件发生的概率，$0.75 = 75% 概率\n"
    "- **二元结算**：市场到期后，赢家 token → $1.00，输家 token → $0.00\n"
    "- **互补定价**：Yes_price + No_price ≈ $1.00，买 Yes@0.70 等价于卖 No@0.30\n"
    "- **有限生命周期**：每个市场有明确的到期/结算时间，不像股票可以无限期持有\n"
    "- **收益上限已知**：最大利润 = (1.0 - 买入价) × 数量，不存在无限上涨空间\n"
    "- **价格趋势特征**：接近结算时，高概率事件价格趋近 1.0（加速上涨），"
    "低概率事件趋近 0.0（加速下跌），这是正常的结算收敛而非泡沫\n"
    "- **价格>0.85 的 token**：胜率高但利润空间小（最多赚 0.15/份），"
    "需要较大仓位才能获得有意义的收益\n"
    "- **价格 0.50-0.85 的 token**：利润空间与风险的最佳平衡区间\n\n"
    "## 参数调优核心原则\n"
    "当前策略仅包含 7 个核心参数，分为风控、入场和仓位三组。\n"
    "- 首轮探索应使用宽松参数：先确保有足够交易次数（>=10 笔），再逐步收紧\n"
    "- 如果上一轮 total_trades=0 或 <5，必须降低 min_price 或增大 time_remaining_s\n"
    "- 每次只收紧 1-2 个参数，保持其他参数宽松\n\n"
    "## 参数权重体系\n"
    "每个参数标注了权重等级，表示该参数对 Polymarket 预测市场回测收益/本金安全的重要程度：\n"
    "- 🔴 **critical**：直接影响本金安全，调整须极度谨慎，每次变动幅度应最小\n"
    "- 🟠 **high**：显著影响收益，调整需谨慎推理，大幅变动需充分理由\n"
    "- 🟡 **medium**：影响入场频率/质量，可适度探索\n\n"
    "## 各参数在预测市场中的影响\n"
    "- 🔴 **stop_loss_price [0-1.0]** [critical]: 绝对止损价。"
    "设置过低则止损失效，本金暴露于极端下跌；设置过高则频繁止损侵蚀本金\n"
    "- 🔴 **min_price [0.01-1.0]** [critical]: 买入价格下限。"
    "过低则买入低概率垃圾标的导致本金亏损；设 >0.85 会排除大部分机会，"
    "建议首轮 0.55-0.65，逐步上调\n"
    "- 🟠 **take_profit_price [0.5-1.0]** [high]: 止盈价。对于买入>0.80的token，"
    "TP 设 0.95-0.98 更合理（接近结算值1.0）\n"
    "- 🟠 **position_max_pct [0.01-1.0]** [high]: 最大仓位比例。"
    "过大则单笔风险集中，过小则收益微薄。建议 0.2-0.5\n"
    "- 🟡 **force_close_remaining_seconds [0-300]** [medium]: 强制平仓剩余秒数。"
    "到期前预留的安全退出时间\n"
    "- 🟡 **time_remaining_s [0-86400]** [medium]: 剩余时间阈值（秒）。"
    "控制在市场剩余多少秒时开始允许入场，1 tick ≈ 1 秒\n"
    "- 🟡 **position_min_pct [0.01-1.0]** [medium]: 最小仓位比例。"
    "高概率 token 利润空间小，需要较大仓位，建议 min≥0.1\n\n"
    "## 规则\n"
    "1. 输出必须是严格的 JSON，格式：{\"configs\": [...], \"reason\": \"调整理由\"}\n"
    "2. 所有参数值必须在 schema 规定的 min/max 范围内\n"
    "3. 每轮给出简短的调整理由（reason 字段），**对 critical/high 权重参数的任何调整必须在 reason 中说明依据**\n"
    "4. 基于历史结果中表现好的参数方向进行收敛，但保持多样性探索\n"
    "5. 首轮用宽松参数，后续逐步收紧表现差的方向\n"
    "6. 如果前几轮都是 0 交易，必须显著降低 min_price 或增大 time_remaining_s\n"
    "7. 每组参数之间应有差异性，避免生成雷同配置\n"
    "8. [权重约束] critical 参数每次调整幅度不超过当前值的 20%；"
    "high 参数不超过 30%；medium 参数可自由探索"
)


# ── Weight icons ──────────────────────────────────────────────────────────────

_WEIGHT_ICONS: dict[str, str] = {
    "critical": "🔴",
    "high": "🟠",
    "medium": "🟡",
    "low": "🟢",
}


# ── Helper formatters ────────────────────────────────────────────────────────


def _fmt_table(rows: list[dict]) -> str:
    """Build a compact markdown table from a list of dicts."""
    if not rows:
        return "(无)"
    headers = list(rows[0].keys())
    header_line = "| " + " | ".join(headers) + " |"
    sep_line = "| " + " | ".join("---" for _ in headers) + " |"
    lines: list[str] = [header_line, sep_line]
    for row in rows:
        cells = []
        for h in headers:
            v = row.get(h, "")
            if isinstance(v, float):
                cells.append(f"{v:.4f}")
            else:
                cells.append(str(v))
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines)


def _avg_metrics_across_slugs(digests: list[dict]) -> dict:
    """Average key metrics across multiple slug digests for a single config."""
    if not digests:
        return {}
    metric_keys = [
        "total_return_pct", "sharpe_ratio", "win_rate",
        "max_drawdown", "profit_factor", "total_trades", "total_pnl",
    ]
    result: dict = {}
    for mk in metric_keys:
        vals = [
            d.get("metrics", {}).get(mk, 0)
            for d in digests
            if d.get("metrics")
        ]
        if vals:
            if mk == "total_trades":
                result[mk] = sum(vals)
            elif mk == "max_drawdown":
                result[mk] = max(vals)
            else:
                result[mk] = round(sum(vals) / len(vals), 4)
    return result


def _fmt_metrics_compact(metrics: dict) -> str:
    """Format metrics dict as a single compact line."""
    parts: list[str] = []
    for k in ["total_return_pct", "sharpe_ratio", "win_rate",
              "max_drawdown", "profit_factor", "total_trades", "total_pnl"]:
        v = metrics.get(k)
        if v is None:
            continue
        if isinstance(v, float):
            parts.append(f"{k}={v:.4f}")
        else:
            parts.append(f"{k}={v}")
    return "  " + ", ".join(parts) if parts else "  (无数据)"


# ── History digest ───────────────────────────────────────────────────────────


def _build_history_digest(
    history_table: list[dict],
    optimize_target: str,
) -> tuple[str, str, str]:
    """Build a structured history digest: summary + sampled rows + diagnostics.

    Returns (summary_text, sample_table_text, diagnostic_text).
    Instead of dumping all rows, we:
      1. Compute aggregate statistics (avg/best/worst)
      2. Categorize into profitable / losing / zero-trade
      3. Sample top/bottom performers from each category
    """
    total = len(history_table)

    # ── Categorize ───────────────────────────────────────────────────────
    profitable: list[dict] = []
    losing: list[dict] = []
    zero_trade: list[dict] = []

    for row in history_table:
        trades = row.get("total_trades", 0)
        pnl = row.get("total_pnl", 0.0)
        if trades == 0:
            zero_trade.append(row)
        elif pnl > 0:
            profitable.append(row)
        else:
            losing.append(row)

    # ── Aggregate statistics (only from rows with trades) ────────────────
    traded_rows = [r for r in history_table if r.get("total_trades", 0) > 0]
    metric_keys = [
        "total_return_pct", "sharpe_ratio", "win_rate",
        "max_drawdown", "profit_factor", "total_trades",
        "avg_slippage", "total_pnl",
    ]

    summary_lines: list[str] = [
        f"## 历史结果统计 (共 {total} 次回测)",
        f"- 盈利: {len(profitable)} 次 | 亏损: {len(losing)} 次 | 未出手(0笔交易): {len(zero_trade)} 次",
    ]

    if traded_rows:
        stat_lines: list[str] = []
        for mk in metric_keys:
            vals = [r.get(mk, 0) for r in traded_rows]
            if not vals:
                continue
            avg_v = sum(vals) / len(vals)
            best_v = max(vals)
            worst_v = min(vals)
            stat_lines.append(
                f"  {mk}: avg={avg_v:.4f}, best={best_v:.4f}, worst={worst_v:.4f}"
            )
        summary_lines.append("- 有交易回测的指标统计：")
        summary_lines.extend(stat_lines)
    else:
        summary_lines.append("- [严重] 全部回测都没有产生交易，过滤条件需大幅放宽")

    summary_text = "\n".join(summary_lines)

    # ── Sample representative rows ───────────────────────────────────────
    # Sort each category by optimize_target; pick top & bottom
    sample_parts: list[str] = ["## 代表性历史样本"]

    def _sort_key(r: dict) -> float:
        v = r.get(optimize_target, r.get("total_return_pct", 0.0))
        return v if isinstance(v, (int, float)) else 0.0

    max_per_cat = 5  # up to 5 from each category

    if profitable:
        profitable.sort(key=_sort_key, reverse=True)
        top_profit = profitable[:max_per_cat]
        sample_parts.append(
            f"\n### 盈利 TOP {len(top_profit)} (共 {len(profitable)} 次盈利)"
        )
        sample_parts.append(_fmt_table(top_profit))

    if losing:
        losing.sort(key=_sort_key, reverse=True)
        # Best of losing (closest to breakeven) + worst
        best_losing = losing[:min(3, len(losing))]
        worst_losing = losing[-min(2, len(losing)):] if len(losing) > 3 else []
        combined_losing = best_losing + [r for r in worst_losing if r not in best_losing]
        sample_parts.append(
            f"\n### 亏损样本 (共 {len(losing)} 次亏损，选 {len(combined_losing)} 条)"
        )
        sample_parts.append(_fmt_table(combined_losing))

    if zero_trade:
        # Show a few zero-trade configs so AI sees which params to avoid
        zt_sample = zero_trade[:min(3, len(zero_trade))]
        sample_parts.append(
            f"\n### 未出手样本 (共 {len(zero_trade)} 次零交易，选 {len(zt_sample)} 条)"
        )
        sample_parts.append(_fmt_table(zt_sample))

    sample_text = "\n".join(sample_parts)

    # ── Diagnostics ──────────────────────────────────────────────────────
    diag_lines: list[str] = []

    if zero_trade and len(zero_trade) > total // 3:
        diag_lines.extend([
            f"[严重] {len(zero_trade)}/{total} 次回测产生 0 笔交易。",
            "过滤条件过严导致策略无法入场，必须显著放宽以下参数：",
            "- 降低 min_price（如 0.55）",
            "- 增大 time_remaining_s（如 150+）",
            "- 增大 position_max_pct（如 0.3+）",
        ])

    low_trade_rows = [r for r in traded_rows if r.get("total_trades", 0) < 5]
    if low_trade_rows and len(low_trade_rows) > len(traded_rows) // 2:
        diag_lines.extend([
            f"[注意] {len(low_trade_rows)}/{len(traded_rows)} 次有交易的回测交易次数不足5笔。",
            "建议适度放宽过滤条件以增加交易机会。",
        ])

    if profitable and losing:
        # Hint: what parameters differ between best profitable and worst losing?
        best = profitable[0]  # already sorted desc
        worst = losing[-1]
        diff_hints: list[str] = []
        for k in best:
            if k in ("total_return_pct", "sharpe_ratio", "win_rate",
                      "max_drawdown", "profit_factor", "total_trades",
                      "avg_slippage", "total_pnl"):
                continue
            bv, wv = best.get(k), worst.get(k)
            if isinstance(bv, (int, float)) and isinstance(wv, (int, float)) and bv != wv:
                diff_hints.append(f"  {k}: 最佳={bv}, 最差={wv}")
        if diff_hints:
            diag_lines.append(
                "[参考] 最佳盈利与最差亏损的参数差异："
            )
            diag_lines.extend(diff_hints[:8])

    diag_text = "\n".join(diag_lines)

    return summary_text, sample_text, diag_text


# ── Round prompt (legacy, kept for reference) ────────────────────────────────


def build_round_prompt(
    round_number: int,
    param_schema: dict,
    base_config: dict,
    market_profiles: dict[str, dict],
    optimize_target: str,
    runs_per_round: int,
    history_table: list[dict],
    param_keys: list[str],
) -> str:
    """Build the user prompt for one optimization round."""
    # Parameter schema (compact: name, type, min, max, step, weight)
    schema_lines: list[str] = []
    for name, info in param_schema.items():
        if name not in param_keys:
            continue
        ptype = info.get("type", "float")
        pmin = info.get("min", "")
        pmax = info.get("max", "")
        step = info.get("step", "")
        weight = info.get("weight", "medium")
        weight_icon = _WEIGHT_ICONS.get(weight, "")
        schema_lines.append(f"  {weight_icon} {name}: {ptype} [{pmin}, {pmax}] step={step} weight={weight}")
    schema_text = "\n".join(schema_lines)

    # Market characteristics (limit to 10 markets to control prompt size)
    market_lines: list[str] = []
    market_items = list(market_profiles.items())
    if len(market_items) > 10:
        market_items = market_items[:10]
        market_lines.append(f"  (共 {len(market_profiles)} 个数据源，仅展示前 10 个)")
    for slug, profile in market_items:
        duration = profile.get("duration_seconds", 0)
        token_count = profile.get("token_count", 0)
        tokens_info: list[str] = []
        for tid, tdata in profile.get("tokens", {}).items():
            short_id = tid[:8] + "..." if len(tid) > 12 else tid
            tokens_info.append(
                f"    {short_id}: price=[{tdata['price_min']:.4f}, {tdata['price_max']:.4f}], "
                f"vol={tdata['volatility']:.6f}, spread={tdata['avg_spread']:.4f}"
            )
        market_lines.append(
            f"  {slug}: duration={duration:.0f}s, tokens={token_count}\n"
            + "\n".join(tokens_info)
        )
    market_text = "\n".join(market_lines)

    # Base config
    base_text = json.dumps(
        {k: v for k, v in base_config.items() if k in param_keys},
        indent=2,
        ensure_ascii=False,
    )

    parts: list[str] = [
        f"## 优化轮次 {round_number}",
        f"优化目标: {optimize_target} (越高越好)",
        f"每轮生成: {runs_per_round} 组参数",
        "",
        "## 可调参数范围",
        schema_text,
        "",
        "## 数据源特征",
        market_text,
        "",
        f"## 基准参数",
        base_text,
    ]

    if history_table:
        summary_text, sample_text, diag_text = _build_history_digest(
            history_table, optimize_target,
        )
        parts.extend(["", summary_text, "", sample_text])
        if diag_text:
            parts.extend(["", diag_text])
    else:
        parts.extend([
            "",
            "## 无历史结果 (首轮探索)",
            "[重要] 首轮请使用偏宽松的参数组合，确保策略能产生交易。",
            "建议：min_price≤0.60, time_remaining_s≥100, "
            "position_min_pct≥0.10, position_max_pct≥0.30",
        ])

    parts.extend([
        "",
        f"请生成 {runs_per_round} 组新参数（JSON 格式），目标是最大化 {optimize_target}。",
    ])

    return "\n".join(parts)


# ── Group prompt (primary, used in runtime) ──────────────────────────────────


def build_group_prompt(
    round_number: int,
    param_schema: dict,
    base_config: dict,
    market_profiles: dict[str, dict],
    optimize_target: str,
    runs_per_round: int,
    baseline_digests: list[dict],
    prev_round_digests: list[dict],
    prev_round_number: int,
    param_keys: list[str],
    best_metric: float = float("-inf"),
    best_total_trades: int = 0,
) -> str:
    """Build AI prompt with per-group tracking from the previous round.

    Instead of dumping all accumulated history, this prompt shows:
    1. Baseline results as reference
    2. Previous round's per-group results (params + metrics)
    3. Asks AI to adjust each group individually
    """
    # Parameter schema (with weight)
    schema_lines: list[str] = []
    for name, info in param_schema.items():
        if name not in param_keys:
            continue
        ptype = info.get("type", "float")
        pmin = info.get("min", "")
        pmax = info.get("max", "")
        step = info.get("step", "")
        weight = info.get("weight", "medium")
        weight_icon = _WEIGHT_ICONS.get(weight, "")
        schema_lines.append(f"  {weight_icon} {name}: {ptype} [{pmin}, {pmax}] step={step} weight={weight}")
    schema_text = "\n".join(schema_lines)

    # Market characteristics (compact)
    market_lines: list[str] = []
    market_items = list(market_profiles.items())
    if len(market_items) > 10:
        market_items = market_items[:10]
        market_lines.append(f"  (共 {len(market_profiles)} 个数据源，仅展示前 10 个)")
    for slug, profile in market_items:
        duration = profile.get("duration_seconds", 0)
        token_count = profile.get("token_count", 0)
        tokens_info: list[str] = []
        for tid, tdata in profile.get("tokens", {}).items():
            short_id = tid[:8] + "..." if len(tid) > 12 else tid
            tokens_info.append(
                f"    {short_id}: price=[{tdata['price_min']:.4f}, {tdata['price_max']:.4f}], "
                f"vol={tdata['volatility']:.6f}, spread={tdata['avg_spread']:.4f}"
            )
        market_lines.append(
            f"  {slug}: duration={duration:.0f}s, tokens={token_count}\n"
            + "\n".join(tokens_info)
        )
    market_text = "\n".join(market_lines)

    # Base config (only tunable keys)
    base_text = json.dumps(
        {k: v for k, v in base_config.items() if k in param_keys},
        indent=2,
        ensure_ascii=False,
    )

    parts: list[str] = [
        f"## 优化轮次 {round_number}",
        f"优化目标: {optimize_target} (越高越好)",
        f"每轮生成: {runs_per_round} 组参数（每组独立调整）",
        "",
        "## 可调参数范围",
        schema_text,
        "",
        "## 数据源特征",
        market_text,
        "",
        "## 基准参数",
        base_text,
    ]

    # Baseline results (round 0)
    if baseline_digests:
        bl_metrics = _avg_metrics_across_slugs(baseline_digests)
        parts.extend([
            "",
            "## 基准结果 (Round 0 — 策略原始参数)",
            _fmt_metrics_compact(bl_metrics),
        ])

    # Previous round's per-group results
    if prev_round_digests:
        # Group by config_index
        groups: dict[int, list[dict]] = {}
        for d in prev_round_digests:
            idx = d.get("config_index", 0)
            groups.setdefault(idx, []).append(d)

        if prev_round_number == 0:
            parts.extend([
                "",
                "## 首轮优化 — 请基于基准结果生成参数变体",
                "[重要] 生成的每组参数应探索不同方向，不要生成雷同配置。",
                "表现好的参数可以微调深入探索，同时尝试不同策略方向。",
            ])
        else:
            parts.extend(["", f"## 上一轮 (Round {prev_round_number}) 各组结果"])
            for idx in sorted(groups.keys()):
                group_digests = groups[idx]
                avg_m = _avg_metrics_across_slugs(group_digests)
                # Extract the config used
                cfg = group_digests[0].get("config", {})
                cfg_tunable = {k: v for k, v in cfg.items() if k in param_keys}
                cfg_text = ", ".join(
                    f"{k}={v:.4f}" if isinstance(v, float) else f"{k}={v}"
                    for k, v in cfg_tunable.items()
                )
                parts.extend([
                    f"\n### 组 {idx + 1}",
                    f"参数: {cfg_text}",
                    _fmt_metrics_compact(avg_m),
                ])
            parts.extend([
                "",
                "[要求] 基于各组各自的表现分别调整参数：",
                "- 表现好的组：微调参数深入探索",
                "- 表现差的组：改变方向尝试新策略",
                "- 保持组数不变，每组输出对应调整后的参数",
            ])
    else:
        parts.extend([
            "",
            "## 无历史结果 (首轮探索)",
            "[重要] 首轮请使用偏宽松的参数组合，确保策略能产生交易。",
        ])

    # Current global best (across all rounds)
    if best_metric != float("-inf") and round_number > 1:
        reliability = "可信" if best_total_trades >= 5 else f"低交易量({best_total_trades}笔)，可信度低"
        parts.extend([
            "",
            f"## 当前全局最优 ({optimize_target}={best_metric:.4f}, total_trades={best_total_trades}, {reliability})",
            "[注意] 交易笔数极少(如<5笔)的高胜率不具参考价值，优化时应确保策略能产生足够交易。",
        ])

    parts.extend([
        "",
        f"请生成 {runs_per_round} 组参数（JSON 格式），目标是最大化 {optimize_target}。",
        "输出格式: {\"configs\": [{组1参数}, {组2参数}, ...], \"reason\": \"调整理由\"}",
    ])

    return "\n".join(parts)
