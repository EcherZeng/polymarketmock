---
description: "Apply the revised 5-point performance optimization plan to Strategy/core/ai_optimizer.py and Strategy/core/runner.py. Key changes over original: replaces double-semaphore IO/CPU split (OOM risk) with slug-group concurrency, adds runner tick fast-forward, and fixes persist race condition."
name: "AI Optimizer — Apply Revised Performance Optimizations"
argument-hint: "Optimization number(s) to apply: 1=Phase1-parallel, 2=btc-cache, 3=slug-group, 4=persist-snapshot, 5=runner-fastforward, or 'all'"
agent: "agent"
---

# AI Optimizer 性能优化实施（修订版）

目标文件：
- [Strategy/core/ai_optimizer.py](../../Strategy/core/ai_optimizer.py)
- [Strategy/core/runner.py](../../Strategy/core/runner.py)

参考文件：[Strategy/core/batch_runner.py](../../Strategy/core/batch_runner.py)

---

## 背景约束（实施前必须理解）

- `ArchiveData` **不能**一次性全部预加载：100 格 delta 数据约 4GB Python 对象
- 优化目标是减少重复 IO/CPU 工作，不是消除按需加载
- `backtest_semaphore`（容量=4）只保护 CPU 密集的 `run_backtest` 阶段
- BTC klines 缓存生命周期跟 task 绑定，不跨任务

---

## 优化1 — Phase 1 profiling 并行化（修订）

**当前**：Phase 1 串行 `load_archive → profile_market`，100 slug ≈ 200s

**目标**：IO + CPU 合并进同一线程，并发 gather，8 个 IO 槽足够。

**修订要点（对比原方案）**：
- `_load_and_profile` 是同步函数，`load_archive + profile_market` 合并在同一个 `asyncio.to_thread` 调用中：

  ```python
  io_sem = asyncio.Semaphore(8)  # 8 而非 16（避免峰值 ~640MB 压力）

  def _load_and_profile(slug: str) -> dict:
      """合并 IO + CPU 在同一线程，避免两次线程切换。"""
      data = load_archive(config.data_dir, slug)
      result = profile_market(slug, data)
      return result  # data 出作用域即被 GC

  async def _profile_one_slug(slug: str) -> None:
      async with io_sem:
          profile = await asyncio.to_thread(_load_and_profile, slug)
      task.market_profiles[slug] = profile  # 回 event loop 后写入，无需加锁

  await asyncio.gather(*[_profile_one_slug(slug) for slug in task.slugs])
  ```

- `market_profiles[slug]` 写入在 event loop 线程（asyncio 单线程调度保证），无需 Lock

---

## 优化2 — BTC klines task 级缓存 ✅（优先实施）

**当前**：每次 `_run_one_backtest` 独立调用 `fetch_btc_klines`，≈ 2000 次 Binance 请求

**目标**：在 `_run_optimization` 入口 Phase 1 并行阶段内预取，task 生命周期内复用。

**实施要点**：
- 在 Phase 1 gather 中与 profiling 并发预取所有 slug 的 BTC klines：

  ```python
  btc_cache: dict[str, list[dict] | None] = {}

  async def _profile_one_slug(slug: str) -> None:
      async with io_sem:
          profile = await asyncio.to_thread(_load_and_profile, slug)
          if btc_trend_enabled(task.base_config):
              try:
                  w = parse_slug_window(slug)
                  btc_cache[slug] = await fetch_btc_klines(w[0], w[1]) if w else None
              except Exception as e:
                  logger.warning("btc prefetch failed slug %s: %s", slug, e)
                  btc_cache[slug] = None
      task.market_profiles[slug] = profile
  ```

- `_run_one_backtest` 签名新增 `btc_cache: dict` 参数，内部 `btc_klines = btc_cache.get(slug)`，**移除原有的 `fetch_btc_klines` 调用**
- 若 btc 未启用（`btc_trend_enabled` 为 False），`btc_cache` 保持空 dict，`btc_cache.get(slug)` 返回 None，behavior 与原来一致

---

## 优化3 — slug 组并发（替代原方案的双层 semaphore）

**原方案风险**：semaphore 外 load，500 个协程同时 load → 500 × ~40MB = 20GB OOM

**替代方案 — 以 slug 为组的轮内并发**：每个 slug 只 load 一次，顺序跑完该 slug 的所有 configs

```python
async def _run_one_slug_all_configs(
    self,
    task: OptimizeTask,
    round_num: int,
    merged_configs: list[tuple[int, dict]],
    slug: str,
    btc_cache: dict,
) -> list[tuple[int, str, dict | None]]:
    """
    一次 IO 加载 + N 次 CPU 执行（顺序占用 semaphore）。
    每个 slug 的 data 在所有 configs 跑完后才释放。
    """
    data = await asyncio.to_thread(load_archive, config.data_dir, slug)
    results: list[tuple[int, str, dict | None]] = []
    try:
        for cfg_idx, merged in merged_configs:
            if task.status == "cancelled":
                break
            async with self._semaphore:
                try:
                    session = await asyncio.wait_for(
                        asyncio.to_thread(
                            run_backtest,
                            self._registry,
                            task.strategy,
                            slug,
                            merged,
                            task.initial_balance,
                            data,
                            task.settlement_result,
                            btc_cache.get(slug),
                        ),
                        timeout=config.slug_timeout,
                    )
                except asyncio.TimeoutError:
                    results.append((cfg_idx, slug, None))
                    continue
            metrics = evaluate(session)
            session.metrics = metrics
            session.drawdown_curve = compute_drawdown_curve(session.equity_curve)
            session.drawdown_events = compute_drawdown_events(session.equity_curve)
            if self._on_result:
                self._on_result(session)
            digest = digest_session(session)
            digest["round"] = round_num
            digest["config_index"] = cfg_idx
            results.append((cfg_idx, slug, digest))
    finally:
        del data  # all configs done → release
    return results

# Phase 2 gather 调用改为：
coros = [
    self._run_one_slug_all_configs(task, round_num, merged_configs, slug, btc_cache)
    for slug in task.slugs
]
nested_results = await asyncio.gather(*coros, return_exceptions=True)
raw_results = [item for r in nested_results if isinstance(r, list) for item in r]
```

**效果对比**：

| 指标 | 原双层 semaphore | slug 组方案 |
|---|---|---|
| 每轮 `load_archive` 次数 | N_cfg × N_slug | N_slug |
| OOM 风险 | 高（大量并发 load） | 低（≤ N_slug 个 archive 同时在内存） |
| 代码复杂度 | 高 | 中 |

---

## 优化4 — `_persist_task` 快照后异步写（修订）

**原方案风险**：`create_task(to_thread(self._persist_task, task))` 在线程中遍历 task 对象时，event loop 可能同时修改 `task.rounds`/`task.all_digests`，GIL 不保护跨对象复合操作。

**修订方案 — event loop 中拍快照，线程只做写磁盘**：

```python
# 在 event loop 线程中（单线程，绝对安全）取快照
_snapshot = task_to_dict(task)
_path = self._tasks_dir / f"opt_{task.task_id}.json"

# fire-and-forget 只写字节，无 task 对象访问
if self._tasks_dir:
    asyncio.create_task(
        asyncio.to_thread(
            lambda s=_snapshot, p=_path: p.write_text(
                json.dumps(s, ensure_ascii=False, default=str), encoding="utf-8"
            )
        )
    )
```

- `_persist_task` 原同步函数不变，仍供最终 `_run_optimization` 退出时同步调用（确保完成）
- 轮末中间快照改用上述 fire-and-forget 模式

---

## 优化5 — Runner tick loop 快进（新增，独立）

**目标文件**：`Strategy/core/runner.py`

**场景**：`time_remaining_s=300` 的 15m slug（900 ticks），前 600 个 tick 的 `on_tick` 因时间门控直接返回 `[]`，但每 tick 仍执行完整 OB + snapshot + TickContext 构建。

**实施要点**：在 `run_backtest` 中 `_build_time_grid` 之后，计算快进截止时间：

```python
from datetime import timedelta

fast_forward_until: str | None = None
if param_active(merged_config, "time_remaining_s"):
    trs = int(merged_config["time_remaining_s"])
    _sw = parse_slug_window(slug)
    if _sw:
        _slug_end_dt = datetime.fromisoformat(_sw[1])
        fast_forward_until = (_slug_end_dt - timedelta(seconds=trs)).isoformat()
```

在 tick loop 内快进阶段只维护 `last_mid` 和 OB 状态（供快进结束后立即可用）：

```python
for tick_idx, grid_ts in enumerate(time_grid):
    # OB + delta 必须始终更新（保证快进结束时 OB 状态正确）
    for tid in token_ids:
        for ob in ob_ptrs[tid].advance_to(grid_ts):
            working_obs[tid] = init_working_ob(ob)
        for delta in delta_ptrs[tid].advance_to(grid_ts):
            apply_delta(working_obs[tid], delta)

    # 快进模式：只更新 last_mid，跳过 snapshot/equity/strategy
    if fast_forward_until and grid_ts < fast_forward_until:
        for tid in token_ids:
            for p in price_ptrs[tid].advance_to(grid_ts):
                if (mid := float(p.get("mid_price", 0))) > 0:
                    last_mid[tid] = mid
        equity_curve.append({"timestamp": grid_ts, "equity": initial_balance})
        continue

    # 正常 tick 处理...
```

**效果**：`time_remaining_s=300` 场景每次 backtest CPU 减少约 50-60%，对 AI 优化 100 slug × 5 cfg × (rounds+1) 调用效果最显著。

---

## 实施顺序（按优先级）

| 优先级 | 改动 | 文件 | 收益 |
|---|---|---|---|
| 1 | **优化2** — BTC klines task 级缓存 | ai_optimizer.py | 消除 ~2000 次 Binance 请求 |
| 2 | **优化5** — Runner tick 快进 | runner.py | CPU -50~60%（time_remaining_s 场景） |
| 3 | **优化3** — slug 组并发 | ai_optimizer.py | IO 请求 5× 减少，内存安全有界 |
| 4 | **优化1** — Phase 1 并行 | ai_optimizer.py | Phase 1 time: ~200s → ~15s |
| 5 | **优化4** — persist 快照异步写 | ai_optimizer.py | 消除事件循环阻塞，无竞争 |

---

## 完成验收

- [ ] 使用 btc 过滤策略时，日志不再出现 `no_klines_provided`
- [ ] 日志只出现每轮每 slug 各 **1 次** `Loaded archive`（不再因 N_cfg 重复）
- [ ] `time_remaining_s` 启用场景中 tick loop 日志中 skip 行出现在前段
- [ ] `get_errors` 无新增错误
- [ ] Phase 1 日志出现多个 slug 同时 `Loaded archive`（非严格串行）

---
description: "Apply the 4-point performance optimization plan to Strategy/core/ai_optimizer.py: Phase-1 parallel profiling (IO semaphore), BTC klines task-level cache, IO/CPU decoupling (load outside compute semaphore), async persist_task"
name: "AI Optimizer — Apply Performance Optimizations"
argument-hint: "Optional: specify which optimizations to apply (1/2/3/4 or 'all')"
agent: "agent"
---

# AI Optimizer 性能优化实施

对 [Strategy/core/ai_optimizer.py](../../Strategy/core/ai_optimizer.py) 实施以下已确认的优化点。
参考文件：[Strategy/core/batch_runner.py](../../Strategy/core/batch_runner.py)（BTC prefetch 的已有实现模式）。

---

## 背景约束（实施前必须理解）

- `ArchiveData` **不能**一次性全部预加载：100 格 delta 数据约 4GB Python 对象，是 OOM 的根本原因
- 优化目标是 **IO 与 CPU 流水线解耦**，不是消除按需加载
- 服务级 `backtest_semaphore`（容量=4）只用于 CPU 密集的 `run_backtest` 阶段
- BTC klines 缓存生命周期跟 task 绑定，不跨任务、不需要外部存储

---

## 优化1 — Phase 1 profiling 并行化

**当前**：`for slug in slugs: load_archive(slug)` 串行，100 slug ≈ 200s

**目标**：用一个独立的 IO semaphore（建议容量 10–20，不占 compute 槽）对 Phase 1 的 `load_archive + profile_market` 并发 gather。

**实施要点**：
- 新增局部 `io_sem = asyncio.Semaphore(16)`（只在 `_run_optimization` 内）
- 提取 `_profile_one_slug(task, slug, io_sem)` 协程：acquire io_sem → load → profile → del data
- Phase 1 改为 `await asyncio.gather(*[_profile_one_slug(...) for slug in slugs])`
- `market_profiles` 写入需加锁或改用局部 dict 最后合并（profile_market 是纯函数，安全）

---

## 优化2 — BTC klines task 级缓存

**当前**：每次 `_run_one_backtest` 独立调用 `fetch_btc_klines`，100 slug × (rounds+1) × configs ≈ 2000 次 Binance 请求

**目标**：在 `_run_optimization` 入口预取一次，task 生命周期内复用。

**实施要点**：
- 在 `_run_optimization` 开头（Phase 1 profiling 并行阶段内或之后）预取所有 slug 的 klines：
  ```python
  btc_cache: dict[str, list[dict] | None] = {}
  if btc_trend_enabled(task.base_config):
      # 与 Phase 1 profiling 并发，用同一个 io_sem 控制
      async def _fetch_btc(slug):
          try:
              w = parse_slug_window(slug)
              btc_cache[slug] = await fetch_btc_klines(w[0], w[1]) if w else None
          except Exception as e:
              logger.warning("btc prefetch failed slug %s: %s", slug, e)
              btc_cache[slug] = None
  ```
- `_run_one_backtest` 签名新增 `btc_cache: dict` 参数，内部直接 `btc_cache.get(slug)`，不再调用 `fetch_btc_klines`

---

## 优化3 — `load_archive` 移到 compute semaphore 外

**当前**：`async with self._semaphore:` 内部串行执行 btc prefetch + load_archive + run_backtest，IO 等待白占 compute 槽

**目标**：IO 阶段在 semaphore 外提前完成，semaphore 内只跑 `run_backtest` 纯 CPU 阶段。

**实施要点**（注意优化2已消除 btc 重复请求）：
```python
async def _run_one_backtest(..., btc_klines):
    # ── IO 阶段（semaphore 外）──────────────────────────────
    data = await asyncio.to_thread(load_archive, config.data_dir, slug)

    # ── CPU 阶段（semaphore 内）──────────────────────────────
    async with self._semaphore:
        try:
            session = await asyncio.wait_for(
                asyncio.to_thread(run_backtest, ..., data, ..., btc_klines),
                timeout=config.slug_timeout,
            )
        finally:
            del data  # 出 semaphore 之前释放
```
- `evaluate`、`compute_drawdown_*`、`digest_session` 都是纯 CPU，保留在 semaphore 内
- `_on_result`（写磁盘）可在 semaphore 外执行

---

## 优化4 — `_persist_task` 异步化

**当前**：`self._persist_task(task)` 是同步调用，每轮末序列化 `all_digests`（随轮次增大，第3轮可达 ~1.2MB），阻塞事件循环

**目标**：推到线程池执行，不阻塞 asyncio 调度。

**实施要点**：
- 在 `_run_optimization` 内所有 `self._persist_task(task)` 改为：
  ```python
  asyncio.create_task(asyncio.to_thread(self._persist_task, task))
  ```
- `_persist_task` 本身不需要改（已是同步函数）
- 注意：create_task 是 fire-and-forget，不 await，确保不阻塞轮次推进
- task 对象在序列化时可能已被下一轮修改 → `_persist_task` 内部用 `task_to_dict(task)` 做快照，这是现有实现，无需改动

---

## 实施顺序建议

1. 优化2（最小改动，效果最大：消除 2000 次 Binance 请求）
2. 优化3（结构调整，依赖优化2已完成）
3. 优化1（Phase 1 并行，依赖优化2的 `_fetch_btc` 并发模式）
4. 优化4（独立改动，最后做）

---

## 完成验收

- [ ] Phase 1 日志出现多个 slug 同时 `Loaded archive` 而非严格时序串行
- [ ] 使用 btc 过滤策略时，日志不再出现 `no_klines_provided`
- [ ] `max_concurrency=4` 时，4个 compute 槽位始终处于运行状态（不因 IO 等待空转）
- [ ] `get_errors` 无新增错误
- [ ] 实施后与 [Strategy/core/batch_runner.py](../../Strategy/core/batch_runner.py) 的 BTC prefetch 模式保持对称
