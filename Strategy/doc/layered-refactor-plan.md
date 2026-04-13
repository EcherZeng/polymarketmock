# Strategy 分层分目录迁移方案（零业务变更）

> 目标：在不改变对外行为、指标口径、参数契约的前提下，将当前 `core` 的混合职责拆分为可维护的分层与分业务结构。

## 1. 重构原则（必须保持不变）

- 保持服务边界：Strategy 仍为独立服务，不与 backend API 耦合。
- 保持参数激活契约：仅 active_params 参与计算与 AI 优化。
- 保持比率口径：后端所有 ratio 指标继续使用 decimal，不乘 100。
- 保持批量资金模式：fixed/cumulative 语义与现有行为一致。
- 保持 API 兼容：URL、请求字段、响应字段、状态机不变。

## 2. 目标分层与目录

```text
Strategy/
  api/                           # 协议适配层（FastAPI 路由）
  application/                   # 用例编排层
    execution/
    optimization/
    sensitivity/
  domain/                        # 业务规则层（纯计算/规则）
    strategy/
    execution/
    evaluation/
    market/
  infrastructure/                # 外部依赖与 IO
    data/
    llm/
    storage/
  shared/                        # 跨层公共类型与工具（尽量薄）
```

分层依赖方向：

- api -> application
- application -> domain, infrastructure, shared
- domain -> shared
- infrastructure -> shared
- domain 禁止依赖 FastAPI/httpx/文件系统

## 3. 当前文件到目标层映射（建议）

### 3.1 Domain

- strategy
  - core/base_strategy.py
  - core/unified_base.py
  - core/registry.py（规则部分）
- execution
  - core/matching.py
  - core/orderbook_state.py
  - core/anchor_pricing.py
- evaluation
  - core/evaluator.py
  - core/metrics_returns.py
  - core/metrics_risk.py
  - core/metrics_trade.py
  - core/result_digest.py
- market
  - core/market_profiler.py

### 3.2 Application

- execution
  - core/runner.py
  - core/batch_runner.py
- optimization
  - core/ai_optimizer.py
  - core/ai_prompt_builder.py
  - core/ai_config_parser.py
- sensitivity
  - core/sensitivity.py

### 3.3 Infrastructure

- data
  - core/data_loader.py
  - core/data_scanner.py
  - core/btc_data.py
- llm
  - core/llm_client.py
- storage
  - api/result_store.py（可暂留 api，后续迁入 infrastructure/storage）

### 3.4 Shared

- core/types.py
- core/ai_types.py

## 4. 迁移顺序（按风险从低到高）

## 阶段 A：先拆 evaluation（低风险，高收益）

动作：

- 新建 domain/evaluation，迁移 evaluator 与 metrics*、result_digest。
- 旧路径保留兼容转发文件（仅 import 新模块并导出）。

验收：

- execution、batch、ai optimize 的指标结果逐项一致。
- win_rate、profit_factor、max_drawdown 与历史结果一致。

回滚点：

- 删除新目录引用，恢复旧 import（兼容层存在时可秒回滚）。

## 阶段 B：拆 data 与 llm（中低风险）

动作：

- 新建 infrastructure/data 与 infrastructure/llm。
- 迁移 data_loader、data_scanner、btc_data、llm_client。

验收：

- 数据扫描、加载、BTC 趋势预取行为一致。
- AI 调用路径与超时行为一致。

回滚点：

- 切回 core 旧 import（兼容层保留）。

## 阶段 C：拆 execution 编排（中风险）

动作：

- 新建 application/execution。
- 迁移 runner、batch_runner。
- 保持 API 路由层仅调用 application，不直接拼装流程。

验收：

- 单回测与批量回测结果一致。
- cumulative_capital 链路、capital_exhausted 语义一致。

回滚点：

- 保留 core 包装器，切换 import 即回滚。

## 阶段 D：拆 optimization（中高风险）

动作：

- 新建 application/optimization 与 domain/market（若未拆）。
- 迁移 ai_optimizer、ai_prompt_builder、ai_config_parser。

验收：

- active_params 过滤逻辑不变。
- 最优结果选择仍带 total_trades 可靠性上下文。

回滚点：

- 任务调度入口恢复至旧模块。

## 阶段 E：收敛 shared 与删除兼容层（收尾）

动作：

- 将 types/ai_types 统一到 shared。
- 全仓替换 import 指向新路径。
- 删除 core 下兼容转发模块。

验收：

- 全量测试通过；无 core 旧路径依赖残留。

回滚点：

- 在删除兼容层前打 tag；必要时回退到 tag。

## 5. 兼容迁移模板（建议）

旧文件在迁移初期保留最小转发内容：

```python
"""Compatibility shim. Remove after import migration is complete."""
from domain.evaluation.evaluator import *
```

说明：

- 只用于迁移窗口期，避免一次性大改导致面过大。
- 每完成一个阶段，先将调用方 import 切到新路径，再删除对应 shim。

## 6. import 治理规则（重构期间）

- 禁止新增 api -> core 直连；新增逻辑一律走 api -> application。
- 领域函数尽量纯函数化，避免隐式读取 config 全局状态。
- IO 只放在 infrastructure；domain 不直接触盘或发网络请求。

## 7. 可执行清单（第一周）

- Day 1：创建 application/domain/infrastructure/shared 目录与 __init__.py。
- Day 2：迁移 evaluation 子域 + 兼容 shim + 回归测试。
- Day 3：迁移 data/llm 子域 + 回归测试。
- Day 4：迁移 runner/batch_runner 到 application/execution。
- Day 5：整理 import、补文档、评估删除第一批 shim。

## 8. 关键风险与防护

- 风险：循环依赖在迁移期上升。
- 防护：每阶段只迁一层一域，优先引入 shim，后替换 import。

- 风险：指标口径被误改（百分比/小样本高胜率偏差）。
- 防护：增加快照回归样本，逐项对比 total_trades、win_rate、drawdown。

- 风险：批量任务状态在重启后不一致。
- 防护：保留 interrupted 终态逻辑；批量状态持久化字段不变。

## 9. 建议的目录落地顺序（最小扰动）

1. 先建新目录与空包，不改运行代码。
2. 迁移 evaluation + shim。
3. 迁移 infrastructure(data/llm) + shim。
4. 迁移 application(execution/optimization/sensitivity)。
5. 最后统一 import，删 shim。

---

该方案默认“零业务变更、零接口变更、零契约变更”。如需进一步降风险，可按“每次只迁移 1 个文件 + 立即跑回归”的粒度执行。
