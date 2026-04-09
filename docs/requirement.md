1.参数添加减负：新建策略中，保留常见基本影响因子最大的参数，其余参数使用add param来添加。确保未添加参数被携带设置为默认值导致计算/AI分析出现偏差(策略页，计算业务逻辑，AI优化业务逻辑)
2.影响因子和权重确认。
3.胜率异常bug，反复确认每项数值的准确性。
4.参数对照功能，组合页面新增参数/数据源数量/收益 对照。
5.本金Bug， 当前的系统设计为每场都充值本金为设定值，保留当前的同时，新增选项使其模拟真实本金多轮次下的变化。 

##### ordered requirements

> 优先级排序依据：数据准确性 > 核心功能缺陷 > 高频UX > 增强功能
> 执行顺序：P0 → P1 → P1.5 → P2 → P3 → P4，有明确依赖链

**关键设计决策记录（讨论确认，不可回退）：**
1. **Req1 未激活参数处理 → 方案 B**：未激活参数完全不传给策略计算，策略代码判断 key 是否存在、缺失则跳过逻辑分支。**不是方案 A**（用 disable_value 替代 → 仍走完整计算路径）。需新增通用 `param_active(config, key)` 守卫函数。
2. **Req2 影响因子 = 策略参数本身**：原文「影响因子和权重」的含义——每个策略参数就是一个影响因子，「权重」是对该参数在 Polymarket BTC 预测市场环境下重要程度的赋值（critical/high/medium/low），不是数学意义上的策略信号加权系数。
3. **Req5 累计模式执行顺序 → 按组合(portfolio)中数据源的已有排序**：前端提交的 `slugs` 列表顺序即执行顺序（由组合页排列决定），不需要后端按数据时间重排。
4. **Req5 资金耗尽 → 立即中止**：累计模式下某 slug 结束后 `final_equity ≤ 0`，后续所有 slug 跳过（标记 `capital_exhausted`），不是继续以极小金额执行。
5. **Req4「数据源数量」= 覆盖度指标**：同一参数配置跑了多少个不同 slug，衡量策略泛化性。不是简单的 portfolio item 计数。
6. **Req4 策略组 = 自动识别（基于 Portfolio）**：Portfolio 中所有 items 的 `strategy` + `config` 完全相同 → 自动标记为策略组。对照功能在**策略组与策略组之间**进行，不是组合内部 items 之间。
7. **Req4 策略组添加数据源 → 自动回测**：向策略组添加 slug 时，后端用组的 config 自动跑回测，将结果作为新 item 加入组。
8. **Req4 对照入口 = 组合列表页勾选 → `/comparison` 页面**：在 PortfoliosPage 选择 2+ 策略组后跳转独立对照页面。

**3.1 与 3.2 是两个独立 bug**（勿混淆）：
- **3.1** 是 AI 优化器的 best 选择逻辑问题 → 低交易量 session 的 win_rate=1.0 霸占 best → 后续每轮 prompt 都以这个 100% 为参考 → AI 越调越偏（级联污染）
- **3.2** 是 evaluator 中结算 PnL 拆分为虚拟 entry 的边界 case 问题 → 可能虚高或虚低 win_rate
- 两者都会导致 win_rate 异常但根因不同，需独立排查和修复

**P1.5 与后续任务的顺序约束**：
- R.1（ai_optimizer 拆分）必须在 P2 的 1.4（AI 优化适配）之前完成
- R.3（evaluator 拆分）必须在 P0 的 3.1/3.2 修复之后执行
- R.2（runner 拆分）必须在 P2 的 1.3（param_active 改造）之前完成

**现有 AI prompt 注意**：`ai_optimizer.py` 的 `_SYSTEM_PROMPT`（~L90-145）已包含详细的 Polymarket 市场特征描述和各参数在预测市场中的影响说明。P4 的 2.2（权重注入 prompt）应在此基础上增强，**不是从零编写**。

---

#### P0 — Req3: 胜率及指标准确性修复
**优先级理由**：数据准确性是所有后续需求的基础，指标不准会导致 Req1/2/4 的参数分析和对照结论失效。

##### 3.1 AI 优化器「当前最优」win_rate 异常（优先修复）✅ DONE
- **复现**：AI 优化页面，基准→3轮每一组 win_rate 均未超 60%，但「当前最优」显示 `win_rate=100.0000`。后续每轮 AI 参考的 best 均为 100%，导致 AI 越调越偏、胜率逐轮下降。
- **级联污染链**：低交易量 session 产出 win_rate=1.0 → 成为 task.best_metric → 传给下一轮 prompt 作为「当前最优」参考 → AI 试图达到 100% 胜率而使参数越来越极端 → 实际胜率逐轮下降
- **根因**：`ai_optimizer.py` L1004-1009 的 best 选择逻辑为 `metric_val > task.best_metric`（纯单值比较，无交易量门槛）。某个低交易量 session（例如仅 1-2 笔全赢）产出 `win_rate=1.0`，直接成为 best 且之后无法被超越。
- **现有代码参考**：best 选取逻辑在 `ai_optimizer.py` L1004-1009；上一轮结果传给 AI 的格式化在 `_build_group_prompt()`（L486-530），使用 `_avg_metrics_across_slugs()` 和 `_fmt_metrics_compact()` 生成 markdown 表格；best 展示当前**不包含 total_trades**。
- **涉及文件**：`Strategy/core/ai_optimizer.py` L1004-1009（best 选择）、`Strategy/core/evaluator.py` L73-76（win_rate 计算）
- **任务**：
  - evaluator：当 `len(all_pnls) < min_trades_threshold`（如 <3）时，win_rate 标记为不可信或降权处理
  - ai_optimizer：best 选择引入多指标加权或最低交易量门槛（如 `total_trades >= 5` 才参与 best 竞选）
  - ai_optimizer：传给 AI 的 prompt 中 best 展示需附带 total_trades，让 AI 自行判断可信度
  - 添加回归测试：模拟低交易量高 win_rate session，验证不会成为 best

##### 3.2 胜率(win_rate)结算拆分逻辑审计 ✅ DONE
- **现状**：`evaluator.py` 中 settlement_pnls 按 `outstanding = max(1, buy_count - sell_count)` 拆分为虚拟 entry。边界情况（buy_count=0 fallback 到 1）逻辑存疑。
- **涉及文件**：`Strategy/core/evaluator.py` L46-70
- **任务**：
  - 枚举 all_pnls 构成逻辑的所有边界 case（无 BUY、只有 SELL、多 token 混合持仓等）
  - 修正 settlement_pnls 拆分策略，确保 outstanding 计数与实际买入笔数一致
  - 添加单元测试覆盖：纯持仓结算、部分卖出+结算、全部卖出无结算、0 笔交易等场景

##### 3.3 其余指标交叉验证 ✅ DONE
- **现状**：profit_factor、avg_win/avg_loss、sharpe/sortino 均依赖 all_pnls 或 equity_curve；3.1/3.2 修复后需全链路回归。
- **涉及文件**：`Strategy/core/evaluator.py` 全文
- **任务**：
  - 对照 Sharpe/Sortino 年化因子计算（samples_per_year 取样频率）确认无溢出
  - 验证 max_drawdown_duration 单位（当前是 tick 数，非秒数）文档与前端是否对齐
  - 用 3 组已知结果的 mock session 做端到端断言

---

#### P1 — Req5: 本金累计模式
**优先级理由**：核心功能缺陷，直接影响批量回测结果的真实性。修复后 Req4 的对照才有意义。

##### 5.1 Backend — BatchRunner 累计本金模式 ✅ DONE
- **现状**：`batch_runner.py` 中 `_run_batch` 对每个 slug 都传入相同的 `task.initial_balance`，无滚动资金逻辑。
- **涉及文件**：`Strategy/core/batch_runner.py`、`Strategy/api/execution.py`
- **任务**：
  - `BatchRequest` 新增 `cumulative_capital: bool = False` 字段
  - `BatchTask` 携带该字段
  - `_run_batch` 中当 `cumulative_capital=True` 时：
    - 按组合数据源（portfolio）的排序顺序串行执行
    - 上一个 slug 的 `session.final_equity` 作为下一个的 `initial_balance`
    - **当某 slug 结束后 final_equity ≤ 0 时，中止后续所有 slug**（标记为 "capital_exhausted"）
  - 当 `cumulative_capital=False` 时保持现有并行逻辑不变

##### 5.2 Backend — 结果中记录资金链路 ✅ DONE
- **涉及文件**：`Strategy/core/types.py`、`Strategy/api/result_store.py`
- **任务**：
  - `BacktestSession` / 结果 JSON 中增加 `capital_mode: "fixed" | "cumulative"` 字段
  - 累计模式下在 batch result 中记录每个 slug 的起始/结束资金链

##### 5.3 Frontend — 累计本金开关 ✅ DONE
- **涉及文件**：`Strategyfrontend/src/pages/StrategyPage.tsx`、`Strategyfrontend/src/api/client.ts`、`Strategyfrontend/src/types/index.ts`
- **任务**：
  - 批量执行区域新增 Switch/Checkbox "累计本金模式"
  - `BatchRequest` 类型增加 `cumulative_capital` 字段
  - 累计模式下 UI 提示 slug 将串行执行、总耗时可能更长

---

#### P1.5 — 策略服务架构拆分（技术债）
**优先级理由**：P2(参数减负) 会大规模修改 ai_optimizer / runner / registry，在 1100+ 行的臃肿文件上叠加功能会导致后续维护成本翻倍。在 P0/P1 两个针对性修复完成后、P2 功能开发前完成拆分，投入产出比最高。

##### R.1 ai_optimizer.py 拆分（1100行 → 5 个模块） ✅ DONE
- **现状**：prompt 构建(~400行)、LLM 调用(~80行)、配置解析(~120行)、数据结构(~120行)、编排逻辑(~230行) 全部混在一个文件中
- **涉及文件**：`Strategy/core/ai_optimizer.py`
- **拆分目标**：
  - `core/ai_optimizer.py` — 主 class + 任务生命周期编排（~230行）
  - `core/ai_prompt_builder.py` — 系统 prompt + 轮次 prompt + 分组 prompt 构建（~400行）
  - `core/ai_config_parser.py` — LLM 返回解析、参数校验、clamping（~120行）
  - `core/ai_types.py` — RoundResult、OptimizeTask 等数据结构（~120行）
  - `core/llm_client.py` — httpx OpenAI API 调用封装（~80行）
- **原则**：纯重构，不改行为，拆分前后 AI 优化端到端结果一致

##### R.2 runner.py 拆分（850行 → 3 个模块） ✅ DONE
- **现状**：时间网格构建、OB 重建 + delta 应用、tiered 锚定价格、快照派生、tick 循环全部堆在一个文件中
- **涉及文件**：`Strategy/core/runner.py`
- **拆分目标**：
  - `core/runner.py` — `run_backtest()` 主编排 + tick 循环（~320行）
  - `core/orderbook_state.py` — `_init_working_ob()`、`_apply_delta()`、OB 快照构建（~150行）
  - `core/anchor_pricing.py` — `_weighted_micro_price()`、`_compute_anchor_price()` tiered 逻辑（~200行）
- **原则**：tick 循环内调用签名不变，仅将辅助函数移至独立模块

##### R.3 evaluator.py 按指标分类拆分（450行 → 3 个模块） ✅ DONE
- **现状**：returns/risk/trade/settlement 4 类 20+ 指标全在一个 `evaluate()` 函数中
- **涉及文件**：`Strategy/core/evaluator.py`
- **拆分目标**：
  - `core/evaluator.py` — 主入口 `evaluate()` + 组装（~100行）
  - `core/metrics_returns.py` — total_return、annualized、profit_factor（~80行）
  - `core/metrics_risk.py` — drawdown、volatility、sharpe/sortino/calmar（~120行）
  - `core/metrics_trade.py` — win_rate、cost_basis、settlement 拆分 + trade pnl（~150行）
- **依赖**：P0(3.1) 修复后再拆分，避免拆分和 bug 修复交叉冲突

##### R.4 batch_runner / execution / results 瘦身（可选，视时间）
- **涉及文件**：`Strategy/core/batch_runner.py`(550行)、`Strategy/api/execution.py`(400行)、`Strategy/api/results.py`(450行)
- **任务**：
  - batch_runner：workflow 日志 StepLog/SlugWorkflow 类提取到 `core/batch_types.py`
  - results.py：cleanup 逻辑提取到 `api/results_cleanup.py`
  - execution.py：结果序列化逻辑提取到 `api/result_serializer.py`
- **原则**：API 路由和领域逻辑分离，每个文件 ≤300 行

---

#### P2 — Req1: 参数添加减负
**优先级理由**：高频交互 UX 改进，直接降低新建策略的认知负担，同时防止隐藏参数以默认值参与计算导致偏差。

##### 1.1 param_schema 元数据扩展 — 标记核心/高级参数 ✅ DONE
- **现状**：`strategy_presets.json` param_schema 有 group/label/desc/disable_value，但无"是否核心参数"标记。前端 visibleKeys 从 `default_config` key 集合决定可见性。
- **涉及文件**：`Strategy/strategy_presets.json`
- **任务**：
  - param_schema 每项增加 `"visibility": "core" | "advanced"` 字段
  - 各 preset 的 default_config 保持不变（向后兼容）
  - 确保 registry.py 加载时正确传递 visibility 字段

##### 1.2 Frontend — StrategyConfigForm 分层渲染 + Add Param ✅ DONE
- **涉及文件**：`Strategyfrontend/src/components/StrategyConfigForm.tsx`、`Strategyfrontend/src/types/index.ts`
- **任务**：
  - 默认只渲染 `visibility=core` 的参数
  - 新增"添加参数"按钮，弹出 Popover/Dialog 列出所有 `advanced` 参数，勾选后加入表单
  - 已添加的高级参数可单独移除（从表单消失，不传给后端）
  - 状态：维护 `activeParams: Set<string>` 记录用户主动添加的参数 key
  - 注意：`activeParams` 初始值 = preset 的 `default_config` 中所有 key（即当前已有可见参数），用户只能添加/移除 `advanced` 参数

##### 1.3 Backend — 未激活参数完全剔除计算路径（方案 B） ✅ DONE
- **涉及文件**：`Strategy/core/registry.py`、`Strategy/core/runner.py`、`Strategy/core/unified_base.py`、`Strategy/strategies/unified_strategy.py`
- **方案**：未激活参数**完全不传给策略**，策略代码判断参数是否存在，缺失则跳过整个逻辑分支。
- **任务**：
  - 前端提交 config 时仅携带 activeParams 中的 key
  - 新增通用抽象方法 `param_active(config, key) -> bool`（实现：`return key in config`），放在 `core/types.py` 或独立 utils 中，策略/风控代码统一调用
  - unified_base 中每个风控分支（TP/SL/连续亏损降仓/强平等）用 `param_active` 守卫，参数不存在则整个分支跳过
  - 示例 before/after：
    ```python
    # Before: 始终执行，config.get 会返回 default_config 中的值
    if mid_price >= config.get("take_profit_price", 0.99): do_take_profit()
    # After: 参数不存在则整个分支不执行
    if param_active(config, "take_profit_price") and mid_price >= config["take_profit_price"]: do_take_profit()
    ```
  - unified_strategy 中入场过滤条件（min_price/momentum/std 等）同理，参数缺失 = 不过滤（相当于该条件始终通过）
  - **不使用 disable_value 替代**，确保不存在的参数不会以任何默认值隐式参与计算

##### 1.4 AI 优化适配 — 仅优化激活参数（方案 B） ✅ DONE
- **涉及文件**：`Strategy/core/ai_optimizer.py`、`Strategy/api/ai_optimize.py`
- **任务**：
  - AI 优化请求携带 `active_params: list[str]`
  - Prompt 构建时仅包含激活参数的 schema/range/当前值，未激活参数完全不出现在 prompt 中
  - LLM 返回的建议只作用于激活参数，AI 不知道也不会修改未激活参数
  - 回测执行时也仅传 active params 给策略（与 1.3 一致）

---

#### P3 — Req4: 策略组参数对照功能
**优先级理由**：依赖 Req5（累计模式修复后对照才有意义）和 Req1（参数可见性明确后对照更清晰）。

**关键设计决策（已确认）：**
1. **策略组 = 自动识别**：Portfolio 中所有 items 的 `strategy` + `config` 完全相同 → 自动标记为策略组（`is_strategy_group=true`）。不需要手动标记。
2. **策略组添加数据源 → 自动回测**：向策略组添加 slug 时，后端用组的 config 自动跑回测，将回测结果作为新 item 加入组。
3. **对照入口 = 组合列表页勾选 → 跳转独立 `/comparison` 页面**：在 PortfoliosPage 选择 2+ 策略组后打开参数对照。
4. **混合策略组合不参与对照**：Portfolio 中存在不同 strategy 或不同 config 的 items → 非策略组，无对照功能。
5. **对照维度**：参数差异 + 数据源覆盖度（同配置跑了多少 slug）+ 收益对比（min/max/avg）。

##### 4.1 Backend — PortfolioItem 携带 config 快照 ✅ DONE
- **现状**：`result_store.py` 存储的 JSON 已包含 `config` 字段（在 BacktestSession 中），但 `PortfolioItemBody` 未携带 config。
- **涉及文件**：`Strategy/api/portfolios.py`、`Strategy/core/types.py`、`Strategyfrontend/src/types/index.ts`
- **任务**：
  - `PortfolioItemBody` 新增 `config: dict[str, Any] = {}` 字段
  - 前端 `PortfolioItem` 类型新增 `config: Record<string, unknown>`
  - 前端添加 item 时从 BacktestResult 中携带 config
  - Portfolio list/detail API 返回每个 item 的 config

##### 4.2 Backend — 策略组自动识别 API（依赖 4.1） ✅ DONE
- **涉及文件**：`Strategy/api/portfolios.py`
- **任务**：
  - 查询时自动判断：items 非空 + 所有 items 的 `strategy` 相同 + 所有 items 的 `config` 相同 → `is_strategy_group=true`
  - Portfolio API 响应中附加 `is_strategy_group: bool`、`group_strategy: str | None`、`group_config: dict | None`
  - 无额外存储字段，纯查询时派生

##### 4.3 Frontend — 策略组添加数据源自动过滤（依赖 4.2） ✅ DONE
- **涉及文件**：`Strategyfrontend/src/components/AddItemsToPortfolioDialog.tsx`、`Strategyfrontend/src/pages/PortfolioDetailPage.tsx`
- **变更说明**：不做自动回测，改为自动过滤已有回测结果中匹配该策略组策略的数据源。
- **任务**：
  - `AddItemsToPortfolioDialog` 新增 `groupStrategy?: string` prop
  - 当 `groupStrategy` 有值时（策略组上下文）：
    - 批量回测 tab：仅显示 `batch.strategy === groupStrategy` 的批量任务
    - 组合 tab：仅显示其他 portfolio 中 `item.strategy === groupStrategy` 的 items
  - 非策略组保持现有无过滤行为

##### 4.4 Frontend — PortfolioDetailPage 策略组展示 + PortfoliosPage 勾选入口（依赖 4.2） ✅ DONE
- **涉及文件**：`Strategyfrontend/src/pages/PortfolioDetailPage.tsx`、`Strategyfrontend/src/pages/PortfoliosPage.tsx`、`Strategyfrontend/src/types/index.ts`
- **任务**：
  - ~~TS `Portfolio` 类型增加 `is_strategy_group`、`group_strategy`、`group_config`~~ ✅ 已在 4.2 完成
  - **PortfolioDetailPage**：策略组 → 页面顶部显示策略名称 + config 参数面板
  - **PortfoliosPage**：策略组 card 显示 badge 标识；增加 checkbox 多选（仅策略组可选）；选 2+ 个后显示"参数对照"按钮 → 跳转 `/comparison?ids=a,b,c`

##### 4.5 Frontend — `/comparison` 参数对照页面（依赖 4.1, 4.4） ✅ DONE
- **涉及文件**：新建 `Strategyfrontend/src/pages/ComparisonPage.tsx`、注册到 `App.tsx`
- **任务**：
  - 从 URL params 获取 portfolio ids，fetch 各 portfolio 数据
  - 参数对照表格：列 = 策略组（portfolio 名称），行 = 参数 key，高亮差异单元格
  - 筛选：可切换「仅显示差异参数」
  - 摘要区域：
    - 每组的数据源覆盖数（slug 数）
    - 收益区间（min/max/avg return）
    - 参数差异数
  - 表头行：策略名、组合名、slug 数量、平均收益

---

#### P4 — Req2: 参数权重体系与 AI 感知
**优先级理由**：增强功能，依赖 Req1（已有 visibility 分层后再叠加权重信息更合理）和 Req3（指标准确后权重才有参考意义）。
**核心概念**：每个策略参数 = 一个影响因子，为其赋予「权重」表达该参数对 Polymarket BTC 预测市场回测收益/本金安全的重要程度。AI 优化时必须理解这些权重。

##### 2.1 param_schema 扩展 — 参数权重标注
- **涉及文件**：`Strategy/strategy_presets.json`
- **任务**：
  - param_schema 每项增加 `"weight": "critical" | "high" | "medium" | "low"` 字段
  - 基于 Polymarket BTC 预测市场特征标注（初始人工标注）：
    - **critical**：直接影响本金安全。如 `stop_loss_price`/`stop_loss_pct`（止损）、`min_price`（最低买入价，过低则买入垃圾标的亏损本金）
    - **high**：显著影响收益。如 `take_profit_price`、`position_max_pct`、`take_profit_pct`
    - **medium**：影响入场频率/质量。如 `momentum_min`、`max_spread`、`max_std`
    - **low**：微调类。如 `amplitude_min`、`reverse_threshold`
  - 后续可用敏感度分析验证/校准标注

##### 2.2 AI 优化 prompt 注入权重上下文
- **涉及文件**：`Strategy/core/ai_prompt_builder.py`（拆分后）或 `Strategy/core/ai_optimizer.py`
- **任务**：
  - System prompt 中为每个参数附带权重标签及原因说明
  - 要求 AI 严格理解 Polymarket BTC 预测市场特征：价格区间 [0,1]、二元结算、有限生命周期、收益上限已知
  - AI 调参时 critical/high 权重参数的变动幅度和方向需要更谨慎的推理（prompt 约束）
  - 每轮 AI 输出的 reason 中须说明对 critical 参数的调整依据

##### 2.3 Frontend — 权重可视化
- **涉及文件**：`Strategyfrontend/src/components/StrategyConfigForm.tsx`
- **任务**：
  - 参数标签旁显示权重等级 badge（🔴 critical / 🟠 high / 🟡 medium / 🟢 low）
  - 可选：修改 critical/high 权重参数时弹出确认提示

##### 2.4 （远期）敏感度分析端点
- **涉及文件**：新建 `Strategy/api/sensitivity.py`、`Strategy/core/sensitivity.py`
- **任务**：
  - 基于 batch runner，对单个参数做 N 档扫描回测
  - 返回 param → metric 的相关性/弹性系数
  - 可拿结果校准 2.1 中的权重标注
