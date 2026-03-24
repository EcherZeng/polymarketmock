# Polymarket Mock Trading Platform — AI Agent Rules

> 本文档为 AI 编码助手提供项目上下文、编码规范和操作指南。任何对本项目的修改都必须遵守以下规则。

---

## 1. 项目身份

这是一个 **Polymarket 模拟交易平台**，代理 Polymarket 真实市场数据（Gamma + CLOB API），提供基于真实 orderbook 深度的模拟撮合引擎。目标用户是量化策略开发者和交易研究人员。系统为 **单用户无认证** 模式。

---

## 2. 技术栈（不可替换）

| 层 | 技术 | 版本要求 |
|---|------|---------|
| 后端语言 | Python | >= 3.11 |
| Web 框架 | FastAPI | >= 0.115 |
| ASGI 服务器 | uvicorn | >= 0.30 |
| HTTP 客户端 | httpx (async) | >= 0.27 |
| 数据验证 | Pydantic v2 + pydantic-settings | >= 2.0 |
| 缓存/模拟数据存储 | Redis 7 (redis-py async, hiredis) | >= 5.0 |
| 历史数据存储 | DuckDB + Apache Parquet (PyArrow) | DuckDB >= 1.0, PyArrow >= 17.0 |
| 前端框架 | React + TypeScript + Vite | Vite 8 |
| UI 组件库 | **shadcn/ui** (style: `radix-nova`, icons: `lucide`) | Tailwind CSS v4 |
| 图表 | Lightweight Charts (TradingView) | - |
| 状态管理 | @tanstack/react-query | - |
| 路由 | React Router | - |
| HTTP 请求 | axios | - |
| 容器化 | Docker Compose | - |

**禁止引入**: styled-components, MUI, Ant Design, SQLAlchemy, Flask, Django, Next.js, Zustand, Redux。
如需新增依赖，必须有充分理由且不与现有技术栈冲突。

---

## 3. 项目结构规范

```
polymarketmock/
├── docker-compose.yml
├── docs/
│   ├── architecture.md          # 架构文档 (只读参考)
│   └── rule.md                  # 本文件
├── backend/
│   ├── pyproject.toml           # PEP 621 格式，不使用 setup.py/requirements.txt
│   ├── Dockerfile
│   └── app/
│       ├── main.py              # FastAPI 入口 (lifespan 管理)
│       ├── config.py            # pydantic-settings，环境变量前缀 PM_
│       ├── models/              # Pydantic 数据模型（不含业务逻辑）
│       ├── routers/             # FastAPI 路由（薄层，不写业务逻辑）
│       ├── services/            # 业务逻辑（撮合引擎、代理、结算、回测）
│       ├── storage/             # 存储层（Redis 封装、DuckDB/Parquet、采集器）
│       └── utils/               # 纯工具函数（无 I/O 副作用）
├── frontend/
│   ├── components.json          # shadcn/ui 配置
│   └── src/
│       ├── api/client.ts        # axios 封装，一个函数对应一个 API
│       ├── types/index.ts       # TypeScript 类型（与后端 Pydantic 模型对齐）
│       ├── pages/               # 页面级组件
│       ├── components/          # 业务组件
│       └── components/ui/       # shadcn/ui 自动生成（不手动修改）
```

### 新增文件规则
- 后端新增 model → `backend/app/models/`
- 后端新增 API → `backend/app/routers/` 并在 `main.py` 注册
- 后端新增业务逻辑 → `backend/app/services/`
- 后端新增存储操作 → `backend/app/storage/`
- 前端新增页面 → `frontend/src/pages/` 并在 `App.tsx` 注册路由
- 前端新增组件 → `frontend/src/components/`
- 前端新增 shadcn 组件 → 使用 `npx shadcn@latest add <component>` 命令，不手写
- 前端新增 API 调用 → `frontend/src/api/client.ts` 中添加函数
- 前端新增类型 → `frontend/src/types/index.ts`

---

## 4. 后端编码规范

### 4.1 异步优先
- **所有函数使用 `async def`**，包括路由、服务、存储层
- 使用 `await` 调用所有 I/O 操作
- Redis 使用 `redis.asyncio`，HTTP 使用 `httpx.AsyncClient`
- 禁止在 async 函数中使用同步阻塞调用

### 4.2 Pydantic v2
```python
# 正确 ✅
from __future__ import annotations
from pydantic import BaseModel, Field

class OrderRequest(BaseModel):
    token_id: str
    side: OrderSide
    amount: float = Field(gt=0)
    price: float | None = Field(None, ge=0, le=1)

# 序列化
result.model_dump(mode="json")

# 不要使用 ❌
from typing import Optional  # 用 X | None 代替
result.dict()                # 用 model_dump() 代替
```

### 4.3 枚举
```python
# 必须继承 str 和 enum.Enum
class OrderSide(str, enum.Enum):
    BUY = "BUY"
    SELL = "SELL"
```

### 4.4 金融计算精度
- **VWAP / 滑点 / 价格相关计算**使用 `decimal.Decimal`
- 输入/输出接口使用 `float`，内部计算使用 `Decimal`
- 结果 round 到 6 位小数（价格/金额）或 4 位小数（百分比）

### 4.5 时间
```python
from datetime import datetime, timezone
now = datetime.now(timezone.utc).isoformat()  # ISO 8601 字符串
```

### 4.6 配置
- 所有配置项通过 `app/config.py` 的 `Settings` 类管理
- 环境变量前缀统一为 `PM_`（如 `PM_REDIS_URL`、`PM_DATA_DIR`）
- 不要在代码中硬编码 URL、端口、TTL 等

### 4.7 Redis Key 命名
- 格式：`entity:subentity:id`
- 示例：`account:balance`、`account:positions:{token_id}`、`orders:pending:{order_id}`、`trades:history`
- 数值存为字符串（`str(balance)`），复杂结构存为 JSON 字符串
- 使用 Key 前缀常量：`ACCOUNT_BALANCE_KEY = "account:balance"`

### 4.8 路由层
- 使用 `APIRouter()`，在 `main.py` 通过 `include_router` 注册
- 路由函数只做参数校验和调用 service 层，不写业务逻辑
- 错误通过 `HTTPException(status_code=..., detail=...)` 抛出
- 使用 `response_model=` 声明返回类型
- Query 参数使用 `Query()` 带约束

### 4.9 代码风格
- 文件头使用 `"""模块级 docstring"""`
- 首行 `from __future__ import annotations`
- import 顺序：标准库 → 第三方 → 本项目（空行分隔）
- 模块内用 `# ── 分节名 ────────` 注释分隔代码区域
- 类型注解使用 Python 3.10+ 语法：`str | None`、`list[dict]`、`dict[str, Any]`

---

## 5. 前端编码规范

### 5.1 组件
- 使用**函数组件 + Hooks**，不使用 class 组件
- 组件使用 `export default function ComponentName()` 导出
- Props 定义 interface：`interface ComponentNameProps { ... }`
- 页面组件放 `pages/`，可复用组件放 `components/`

### 5.2 shadcn/ui（关键）
- 配置：style `radix-nova`、icons `lucide`、aliases `@/components`
- 添加组件：`npx shadcn@latest add <name>`，**永远不要手动修改 `components/ui/` 下的文件**
- 使用 `cn()` 工具函数合并 className
- 优先使用 shadcn 提供的语义组件（Card, Button, Input, Table, Tabs, Alert, Badge, Dialog, ScrollArea, ToggleGroup 等）
- Tailwind 类名使用 v4 语法

### 5.3 数据获取
```typescript
// 查询 — useQuery
const { data } = useQuery<Market>({
  queryKey: ["market", marketId],
  queryFn: () => fetchMarket(marketId),
  enabled: !!marketId,
  refetchInterval: 30_000,  // 自动刷新（可选）
})

// 变更 — useMutation
const mutation = useMutation({
  mutationFn: () => placeOrder(req),
  onSuccess: () => {
    queryClient.invalidateQueries({ queryKey: ["account"] })
  },
})
```

### 5.4 API 客户端
- 所有后端请求通过 `src/api/client.ts` 中的函数发起
- 一个 API 端点对应一个函数：`fetchMarket()`, `placeOrder()`, `estimateOrder()` 等
- axios 实例 baseURL 为 `/api`（由 Vite proxy 转发到后端）
- 返回值使用明确的 TypeScript 类型
- 参数命名：前端 camelCase → 传给后端时转为 snake_case

### 5.5 类型
- 所有类型集中在 `src/types/index.ts`
- 使用 `interface` 定义对象类型，使用 `type` 定义联合类型
- 与后端 Pydantic 模型字段名保持一致（后端字段名即 API 字段名）
- 使用 `import type { ... }` 导入类型

### 5.6 样式
- 只使用 **Tailwind CSS** 工具类，不写自定义 CSS（`index.css` 中的 CSS 变量除外）
- 布局用 `flex`、`grid`、`gap`
- 响应式用 `lg:grid-cols-12`、`lg:col-span-4` 等
- 颜色使用语义变量：`text-foreground`、`text-muted-foreground`、`bg-background`、`border`
- 图表颜色使用 CSS 变量：`chart-1`（红/asks）、`chart-2`（绿/bids）

### 5.7 路径别名
- 所有 import 使用 `@/` 前缀：`import { Button } from "@/components/ui/button"`
- 配置在 `vite.config.ts`（resolve.alias）和 `tsconfig.json`（paths）

---

## 6. 数据持久化规则（核心约束）

| 数据类型 | 存储位置 | 原因 |
|---------|---------|------|
| 真实市场价格快照 | Parquet (DuckDB 查询) | 需要持久化用于回测 |
| 真实 orderbook 快照 | Parquet (DuckDB 查询) | 需要持久化用于回测 |
| 用户模拟交易数据（余额、持仓、订单、交易记录、PnL） | **Redis 缓存** | 不持久化到磁盘文件 |

**严格规则**：
- ❌ 不要把模拟交易数据写入 Parquet / DuckDB / 任何文件
- ❌ 不要把真实市场数据只存 Redis（必须写 Parquet）
- ✅ Parquet 文件按 `{market_id}/{date}.parquet` 分区存储在 `backend/data/` 下
- ✅ Redis AOF 持久化已开启，但这只是 Redis 自身的恢复机制，不等于「持久化到文件」

---

## 7. 外部 API 交互

### Polymarket Gamma API (`https://gamma-api.polymarket.com`)
- 市场列表/详情、事件列表/详情
- 缓存 TTL：60 秒（`PM_CACHE_TTL_MARKETS`）

### Polymarket CLOB API (`https://clob.polymarket.com`)
- Orderbook 深度、中间价
- 缓存 TTL：orderbook 5 秒，midpoint 3 秒
- 下单时的 orderbook 必须**不走缓存**（`get_orderbook_raw`）

### 代理规则
- 所有外部 API 请求经后端代理（`polymarket_proxy.py`）
- 前端不直接请求 Polymarket
- 代理层统一缓存到 Redis（`cache_get`/`cache_set`）
- 缓存 key 格式：`cache:{api_name}:{params_hash}`

---

## 8. 撮合引擎规则

- **市价单**：实时拉取 CLOB orderbook → 逐级消耗（VWAP）→ 更新余额/持仓 → 记录交易
- **限价单**：预留资金 → 存入 pending → 后台每 5 秒检查 midpoint 触发 → 成交
- **卖出前验证**：必须有足够持仓
- **买入前验证**：必须有足够余额
- **模拟不影响真实 orderbook**：只读取，不修改
- **部分成交**：深度不足时部分成交是合法状态
- **结算**：赢方 token 按 $1/share 结算，输方按 $0 结算

---

## 9. Docker 部署

```yaml
# 三个服务
redis:    端口 6379，AOF 持久化
backend:  端口 8071，依赖 redis，挂载 ./backend/data:/app/data
frontend: 端口 3021，依赖 backend
```

环境变量前缀：`PM_`
- `PM_REDIS_URL=redis://redis:6379`
- `PM_GAMMA_API_URL=https://gamma-api.polymarket.com`
- `PM_CLOB_API_URL=https://clob.polymarket.com`
- `PM_DATA_DIR=/app/data`

本地开发：Vite dev server 将 `/api` 代理到 `http://localhost:8071`。

---

## 10. 安全与边界

- 单用户系统，无认证，无 JWT，无 session
- CORS 允许所有来源（开发模式）
- 不处理真实资金，不与链上合约交互
- 不缓存用户敏感数据
- 所有数值输入必须在路由层或 Pydantic 模型中校验（`gt=0`、`ge=0`、`le=1`）
- 使用参数化查询（DuckDB），不拼接 SQL 字符串

---

## 11. 操作指南

### 添加新 API 端点的步骤
1. 在 `models/` 中定义请求/响应 Pydantic 模型
2. 在 `services/` 中实现业务逻辑（async）
3. 在 `routers/` 中添加路由函数（调用 service）
4. 在 `main.py` 中注册路由（如新 router 文件）
5. 在 `frontend/src/types/index.ts` 中添加 TypeScript 类型
6. 在 `frontend/src/api/client.ts` 中添加请求函数
7. 在前端组件中使用 useQuery/useMutation 调用

### 添加 shadcn 组件
```bash
cd frontend
npx shadcn@latest add <component-name>
```
不要手动创建或修改 `components/ui/` 下的文件。

### 运行项目
```bash
# Docker 一键启动
docker-compose up -d

# 或本地开发
docker run -d --name redis -p 6379:6379 redis:7-alpine redis-server --appendonly yes
cd backend && pip install -e . && uvicorn app.main:app --reload --port 8071
cd frontend && npm install && npm run dev
```

---

## 12. 常见陷阱

| 陷阱 | 正确做法 |
|------|---------|
| 在 utils/ 中写了 async 函数 | utils/ 下应为纯函数，无 I/O |
| 在 router 中写了复杂业务逻辑 | 业务逻辑放 services/，router 只做分发 |
| 手动修改了 `components/ui/` 下的文件 | 使用 `npx shadcn add` 管理，手动改会被覆盖 |
| 模拟交易数据写入了 Parquet | 模拟数据只存 Redis |
| 使用 `Optional[str]` 而非 `str \| None` | 本项目使用 Python 3.11+ 语法 |
| 使用 `result.dict()` | 使用 `result.model_dump(mode="json")` (Pydantic v2) |
| 在前端直接请求 Polymarket API | 所有外部请求通过后端代理 |
| 下单时使用了缓存的 orderbook | 下单必须调用 `get_orderbook_raw`（不走缓存） |
| 前端 import 不带 `@/` 前缀 | 统一使用 `@/` 路径别名 |
| 在 Redis 中用 float 存数值 | 用 `str()` 转字符串存储 |