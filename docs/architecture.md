# Polymarket Mock Trading Platform — 架构设计文档

## TL;DR

构建一个基于 React + FastAPI 的 Polymarket 模拟交易平台，后端代理并缓存 Polymarket 真实市场数据（Gamma API + CLOB API），提供基于真实 orderbook 深度的模拟撮合引擎，支持买入/卖出/限价单/结算/持仓管理。真实市场数据（价格、orderbook）用 Parquet + DuckDB 持久化，用户模拟交易数据（持仓、订单、交易记录、余额）全部存 Redis 缓存。所有模拟交易 API 公开 RESTful 接口供量化策略调用。前端使用 shadcn/ui 组件库。Docker 容器化部署。

---

## 架构总览

```
┌─────────────────────────────────────────────────────┐
│                    Frontend (React)                  │
│  ┌──────────┐  ┌──────────────┐  ┌───────────────┐  │
│  │ 市场详情  │  │  交易面板     │  │  持仓/PnL    │  │
│  │ +Orderbook│  │ Buy/Sell/Limit│  │  +历史记录    │  │
│  └──────────┘  └──────────────┘  └───────────────┘  │
│  ┌──────────────────────────────────────────────┐   │
│  │           历史数据/回测结果页面                │   │
│  └──────────────────────────────────────────────┘   │
└─────────────┬───────────────────────────────────────┘
              │ HTTP (REST API)
┌─────────────▼───────────────────────────────────────┐
│                 Backend (FastAPI)                     │
│  ┌──────────────┐  ┌──────────────┐  ┌────────────┐ │
│  │ Market Proxy  │  │ Trading Engine│  │ Backtest   │ │
│  │ (Gamma+CLOB)  │  │ (撮合引擎)    │  │ Engine     │ │
│  └──────┬───────┘  └──────┬───────┘  └─────┬──────┘ │
│         │                 │                 │        │
│  ┌──────▼─────────────────▼─────────────────▼──────┐ │
│  │              Data Layer                          │ │
│  │  Redis (模拟交易: 持仓/挂单/余额/交易记录)      │ │
│  │  DuckDB + Parquet (真实数据: 价格/orderbook快照)  │ │
│  └─────────────────────────────────────────────────┘ │
└──────────┬──────────────────────────────────────────┘
           │ HTTPS
┌──────────▼──────────────────────────────────────────┐
│            Polymarket External APIs                   │
│  Gamma API: https://gamma-api.polymarket.com         │
│  CLOB API:  https://clob.polymarket.com              │
└──────────────────────────────────────────────────────┘
```

---

## 技术栈

| 层 | 技术 |
|---|------|
| 前端 | React + TypeScript + Vite |
| UI 组件库 | shadcn/ui (Radix + Tailwind CSS v4) |
| 图表 | Lightweight Charts (TradingView) + Recharts (via shadcn Chart) |
| 状态管理 | React Query (@tanstack/react-query) |
| 路由 | React Router |
| 后端 | Python 3.11 + FastAPI |
| HTTP 客户端 | httpx (async) |
| 缓存 / 模拟数据 | Redis 7 (redis-py async) |
| 历史数据持久化 | DuckDB + Apache Parquet (PyArrow) |
| 容器化 | Docker Compose |

---

## 项目结构

```
polymarketmock/
├── docker-compose.yml
├── backend/
│   ├── Dockerfile
│   ├── pyproject.toml
│   ├── app/
│   │   ├── main.py              # FastAPI 入口, CORS, lifespan
│   │   ├── config.py            # 配置
│   │   ├── models/
│   │   │   ├── market.py        # Market, Event, Orderbook
│   │   │   ├── trading.py       # Order, Position, Trade, Account
│   │   │   └── backtest.py      # 回测请求/结果
│   │   ├── routers/
│   │   │   ├── markets.py       # 市场数据代理
│   │   │   ├── trading.py       # 模拟交易 (公开 API)
│   │   │   ├── account.py       # 账户/持仓/PnL
│   │   │   └── backtest.py      # 回测
│   │   ├── services/
│   │   │   ├── polymarket_proxy.py   # Gamma+CLOB 代理+缓存
│   │   │   ├── matching_engine.py    # 撮合引擎
│   │   │   ├── position_manager.py   # 持仓管理 + PnL
│   │   │   ├── settlement.py         # 结算
│   │   │   └── backtest_engine.py    # 回测引擎
│   │   ├── storage/
│   │   │   ├── redis_store.py        # Redis 封装
│   │   │   ├── duckdb_store.py       # DuckDB + Parquet
│   │   │   └── data_collector.py     # 后台采集任务
│   │   └── utils/
│   │       └── price_impact.py       # 滑点计算
│   └── data/                    # Parquet 存储 (volume mount)
│       ├── prices/              # 真实价格快照
│       └── orderbooks/          # 真实 orderbook 快照
├── frontend/
│   ├── Dockerfile
│   ├── components.json          # shadcn/ui 配置
│   ├── src/
│   │   ├── App.tsx
│   │   ├── pages/
│   │   │   ├── TradingDashboard.tsx
│   │   │   └── HistoryPage.tsx
│   │   ├── components/
│   │   │   ├── ui/              # shadcn/ui 组件 (auto-generated)
│   │   │   ├── MarketInfo.tsx
│   │   │   ├── OrderbookView.tsx
│   │   │   ├── TradingPanel.tsx
│   │   │   ├── PositionTable.tsx
│   │   │   ├── PriceChart.tsx
│   │   │   └── TradeHistory.tsx
│   │   ├── api/client.ts
│   │   └── types/index.ts
│   └── vite.config.ts
└── docs/
    └── architecture.md
```

---

## 数据持久化策略

| 存储 | 数据类型 | 说明 |
|------|---------|------|
| **Redis** | 模拟交易数据 | 余额、持仓、订单（含历史）、交易记录、PnL。Redis 重启丢失（已启用 AOF 持久化） |
| **Parquet + DuckDB** | 真实市场数据 | 价格快照、orderbook 深度快照。按 `{market_id}/{date}.parquet` 分区 |

### Redis 数据结构

| Key | 类型 | 用途 |
|-----|------|------|
| `account:balance` | String | 当前 USDC 余额 |
| `account:config` | Hash | 初始余额等配置 |
| `account:realized_pnl` | String | 累计已实现 PnL |
| `account:positions:{token_id}` | Hash | 持仓 (shares, avg_cost, side) |
| `orders:all:{order_id}` | String (JSON) | 所有订单记录 |
| `orders:pending:{order_id}` | String (JSON) | 挂单中的限价单 |
| `trades:history` | Sorted Set | 按时间排序的成交记录 |
| `watched:markets` | Hash | 关注的市场 (token_id → market_id) |

### Parquet Schema

**prices/{market_id}/{date}.parquet:**
| 列 | 类型 | 说明 |
|---|------|------|
| timestamp | string | ISO 8601 |
| token_id | string | CLOB token ID |
| mid_price | float64 | 中间价 |
| best_bid | float64 | 最优买价 |
| best_ask | float64 | 最优卖价 |
| spread | float64 | 价差 |

**orderbooks/{market_id}/{date}.parquet:**
| 列 | 类型 | 说明 |
|---|------|------|
| timestamp | string | ISO 8601 |
| token_id | string | CLOB token ID |
| bid_prices | string | JSON array of prices |
| bid_sizes | string | JSON array of sizes |
| ask_prices | string | JSON array of prices |
| ask_sizes | string | JSON array of sizes |

---

## 撮合引擎

### 市价单流程
1. 从 CLOB API 实时拉取 orderbook
2. 买入 → 吃 asks（从低到高），卖出 → 吃 bids（从高到低）
3. 逐级消耗直到填满请求数量
4. 计算 VWAP（加权平均成交价）和总成本
5. 深度不足 → 部分成交
6. 更新 Redis 中的持仓和余额

### 限价单流程
1. 买入限价单 → 预留资金（amount × price）
2. 存入 Redis pending orders
3. 后台每 5s 检查：如果 midpoint ≤ limit price (buy) 或 ≥ limit price (sell)，触发成交
4. 成交后更新持仓/余额，移除 pending

### 滑点计算
```
slippage_pct = ((avg_price - mid_price) / mid_price) × 100  (买入)
slippage_pct = ((mid_price - avg_price) / mid_price) × 100  (卖出)
```

---

## 公开 API 总览

### 市场数据
| 方法 | 路径 | 描述 |
|------|------|------|
| GET | `/api/markets` | 市场列表 |
| GET | `/api/markets/{id}` | 市场详情 |
| GET | `/api/events` | 事件列表 |
| GET | `/api/events/{id}` | 事件详情 |
| GET | `/api/orderbook?token_id=` | Orderbook |
| GET | `/api/midpoint?token_id=` | 中间价 |

### 交易操作
| 方法 | 路径 | 描述 |
|------|------|------|
| POST | `/api/trading/order` | 下单 (市价/限价) |
| POST | `/api/trading/estimate` | 预估成交 (不执行) |
| GET | `/api/trading/orders` | 所有订单 |
| GET | `/api/trading/orders/pending` | 挂单列表 |
| DELETE | `/api/trading/orders/{order_id}` | 取消限价单 |
| GET | `/api/trading/history` | 交易历史 |
| POST | `/api/trading/settle/{market_id}` | 手动结算 |

### 账户
| 方法 | 路径 | 描述 |
|------|------|------|
| POST | `/api/account/init` | 初始化账户 |
| GET | `/api/account` | 账户概览 |
| GET | `/api/account/positions` | 持仓列表 |
| GET | `/api/account/positions/{token_id}` | 持仓详情 |

### 回测
| 方法 | 路径 | 描述 |
|------|------|------|
| GET | `/api/backtest/markets` | 可回测市场列表 |
| GET | `/api/backtest/data/{market_id}` | 历史数据 |
| POST | `/api/backtest/replay` | 回放回测 |

### 请求/响应示例

**下单:**
```json
POST /api/trading/order
{
  "token_id": "abc123...",
  "side": "BUY",
  "type": "MARKET",
  "amount": 100
}

→ {
  "order_id": "uuid",
  "status": "FILLED",
  "filled_amount": 100,
  "avg_price": 0.5234,
  "total_cost": 52.34,
  "slippage_pct": 0.125
}
```

**预估:**
```json
POST /api/trading/estimate
{
  "token_id": "abc123...",
  "side": "BUY",
  "type": "MARKET",
  "amount": 100
}

→ {
  "estimated_avg_price": 0.5234,
  "estimated_slippage_pct": 0.125,
  "estimated_total_cost": 52.34,
  "orderbook_depth_available": 100
}
```

---

## 前端页面

### 主交易页面 (TradingDashboard)
三栏布局：
- **左栏**: 市场信息 (Card) + Orderbook 深度 (ScrollArea) + 价格图表 (Lightweight Charts)
- **中栏**: 交易面板 (Tabs Buy/Sell + ToggleGroup Market/Limit + Input + 滑点预估 Alert + 确认 Button) + 近期交易记录 (Table)
- **右栏**: 持仓表 (Table + Badge PnL) + 账户概览 (Card) + 初始资金设置 (Dialog)

### 历史数据页面 (HistoryPage)
- 交易历史完整表格（分页）
- 可回测市场列表
- 回测结果展示

---

## Docker 部署

```bash
# 启动所有服务
docker-compose up -d

# 访问
# 前端: http://localhost:3021
# 后端 Swagger: http://localhost:8071/docs
# Redis: localhost:6379
```

### 本地开发模式

```bash
# 启动 Redis
docker run -d --name redis -p 6379:6379 redis:7-alpine redis-server --appendonly yes

# 后端
cd backend
pip install -e .
uvicorn app.main:app --reload --port 8071

# 前端
cd frontend
npm install
npm run dev
```

---

## 设计决策

- **单用户无认证**: API 直接可用，简化量化策略对接
- **撮合用真实 orderbook**: 每次下单实时拉 CLOB orderbook 逐级消耗，真实模拟滑点和部分成交
- **模拟交易不影响真实 orderbook**: "只读"价格影响，本地记录虚拟消耗
- **持久化分层**: Parquet+DuckDB 只存真实数据，模拟交易全存 Redis
- **Parquet 按 market_id + 日期分区**: DuckDB 可高效扫描
- **前端 shadcn/ui**: 语义色彩、gap 布局、Card 组合、Badge 状态标签等规范
- **回测不内置策略**: 只提供数据 + 回放交易能力，策略由外部程序驱动
- **Redis AOF**: docker-compose 中开启 `--appendonly yes`，缓解模拟数据丢失
