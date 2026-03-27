# Strategy Backtest Engine — 架构设计

> 完全独立的 Python 进程。通过目录结构直接读取 `backend/data/` 下的 Parquet 历史数据，**不与 Backend 做任何 API 调用**。自身提供完整的 HTTP API，供前端页面控制策略选择、回测执行和结果评估。

---

## 1. 系统定位

```
┌───────────────────────────────────────────────────────────────────┐
│  Polymarket Mock Trading Platform                                 │
│                                                                   │
│  ┌─────────────┐   ┌─────────────┐   ┌───────────────────────┐   │
│  │  Frontend    │   │  Backend    │   │  Strategy Engine       │   │
│  │  React+Vite  │   │  FastAPI    │   │  FastAPI :8072         │   │
│  │  :3021       │   │  :8071      │   │  独立进程              │   │
│  └──┬───────┬──┘   └──────┬──────┘   └──────┬────────────────┘   │
│     │       │              │                  │                    │
│     │  /api/*              │          /strategy/*                  │
│     │       │              │                  │                    │
│     │       ▼              │                  ▼                    │
│     │  模拟交易/实时行情    │          策略回测/评估               │
│     │                      │                  │                    │
│     │               ┌──────▼──────────────────▼──────┐            │
│     │               │  backend/data/  (共享磁盘)      │            │
│     │               │  prices/ orderbooks/ ob_deltas/ │            │
│     │               │  live_trades/ archives/         │            │
│     │               │  (Parquet + DuckDB 只读)        │            │
│     │               └────────────────────────────────┘            │
└─────┼────────────────────────────────────────────────────────────┘
      │
  前端通过 Vite 双代理:
  /api/*      → http://localhost:8071  (Backend)
  /strategy/* → http://localhost:8072  (Strategy Engine)
```

### 核心原则

- **完全独立** — 与 Backend 零通信，不 import backend 任何模块，不调用 backend 任何 API
- **磁盘共享** — 唯一的耦合点是 `backend/data/` 目录，通过文件系统目录结构发现和读取数据
- **API-first** — 策略列表、回测执行、评估结果全部通过 HTTP API 暴露，为前端页面控制预留接口
- **零网络请求** — 不做任何外部网络调用，纯本地文件 I/O + CPU 计算

---

## 2. 目录结构

```
Strategy/
├── ARCHITECTURE.md          # 本文档
├── requirements.txt         # 依赖（复用 backend 的 duckdb/pyarrow/pandas/numpy）
├── main.py                  # 入口：CLI + 策略加载 + 回测调度
├── config.py                # 回测引擎配置
│
├── core/                    # 核心框架
│   ├── __init__.py
│   ├── types.py             # 数据类型定义（Signal, TickContext, FillInfo 等）
│   ├── base_strategy.py     # BaseStrategy 抽象基类
│   ├── data_loader.py       # 历史数据加载（自实现 DuckDB 查询，不 import backend）
│   ├── data_scanner.py      # 目录结构扫描：发现 archives/、prices/ 等可用数据
│   ├── matching.py          # 撮合引擎（自实现 VWAP/滑点计算）
│   ├── runner.py            # 单次回测 Workflow 执行器
│   ├── batch_runner.py      # 批量并行回测调度器
│   ├── evaluator.py         # 回测评估指标计算
│   └── registry.py          # 策略注册表（启动时扫描加载）
│
├── api/                     # HTTP API 层
│   ├── __init__.py
│   ├── app.py               # FastAPI 实例 + lifespan
│   ├── strategies.py        # 策略查询 API
│   ├── data.py              # 数据源查询 API（目录扫描）
│   ├── execution.py         # 回测执行 API（单场 / 批量）
│   └── results.py           # 结果 & 评估指标查询 API
│
├── strategies/              # 用户策略目录
│   ├── __init__.py
│   ├── example_momentum.py  # 示例：动量策略
│   └── example_mean_rev.py  # 示例：均值回归策略
│
└── results/                 # 回测结果输出（内存为主，可选导出）
    └── .gitkeep
```

---

## 3. 策略接口设计

### 3.1 BaseStrategy（抽象基类）

```python
from abc import ABC, abstractmethod
from core.types import TickContext, Signal, FillInfo


class BaseStrategy(ABC):
    """策略基类 — 用户只需实现这几个方法。"""

    # 元信息（子类覆写）
    name: str = "unnamed"
    description: str = ""
    version: str = "0.1.0"

    # 策略可声明它需要的配置参数及默认值
    default_config: dict = {}

    @abstractmethod
    def on_init(self, config: dict) -> None:
        """策略初始化，接收用户配置。在回测开始前调用一次。"""
        ...

    @abstractmethod
    def on_tick(self, ctx: TickContext) -> list[Signal]:
        """每个时间点调用一次，返回交易信号列表（可为空）。"""
        ...

    def on_fill(self, fill: FillInfo) -> None:
        """成交回调（可选覆写）。每笔成交后调用。"""
        pass

    def on_end(self) -> dict:
        """回测结束回调（可选覆写）。返回策略自定义摘要。"""
        return {}
```

### 3.2 核心数据类型

```python
from dataclasses import dataclass, field


@dataclass
class Signal:
    """策略产出的交易信号。"""
    token_id: str
    side: str                       # "BUY" | "SELL"
    amount: float                   # 目标成交数量（shares）
    order_type: str = "MARKET"      # "MARKET" | "LIMIT"
    limit_price: float | None = None


@dataclass
class TickContext:
    """每个 tick 推送给策略的完整市场快照。"""
    timestamp: str                            # ISO 8601 UTC
    index: int                                # 当前 tick 序号
    total_ticks: int                          # 总 tick 数

    # 各 token 的行情数据
    tokens: dict[str, TokenSnapshot]          # token_id → snapshot

    # 当前账户状态
    balance: float                            # 可用余额
    positions: dict[str, float]               # token_id → 持仓量
    equity: float                             # 总权益 = balance + sum(pos * mid)

    # 历史窗口（策略可用于技术指标计算）
    price_history: dict[str, list[float]]     # token_id → 最近 N 个 mid_price
    trade_history: list[dict]                 # 最近的真实成交记录


@dataclass
class TokenSnapshot:
    """单个 token 在某一 tick 的行情。"""
    token_id: str
    mid_price: float
    best_bid: float
    best_ask: float
    spread: float
    bid_levels: list[tuple[float, float]]     # [(price, size), ...]
    ask_levels: list[tuple[float, float]]     # [(price, size), ...]


@dataclass
class FillInfo:
    """成交回报。"""
    timestamp: str
    token_id: str
    side: str
    requested_amount: float
    filled_amount: float
    avg_price: float
    total_cost: float
    slippage_pct: float
    balance_after: float
    position_after: float
```

---

## 4. Workflow — 单次回测流程

```
┌────────────────────────────────────────────────────────────┐
│  runner.py — BacktestRunner                                │
│                                                            │
│  输入: strategy_name, slug, config, initial_balance        │
│                                                            │
│  ① 从 registry 获取策略类，实例化                          │
│  ② data_loader 加载该 slug 的全部历史数据                  │
│     ├── prices (Parquet → list[dict])                      │
│     ├── orderbooks (Parquet → list[dict])                  │
│     ├── ob_deltas (Parquet → list[dict])                   │
│     └── live_trades (Parquet → list[dict])                 │
│  ③ 构建 1 秒间隔时间网格 (time_grid)                      │
│  ④ 调用 strategy.on_init(config)                           │
│  ⑤ 逐 tick 循环:                                          │
│     │                                                      │
│     ├─ 重建当前 tick 的 orderbook 快照 (delta-driven)      │
│     ├─ 构建 TickContext（行情 + 账户状态 + 历史窗口）      │
│     ├─ signals = strategy.on_tick(ctx)                     │
│     ├─ 对每个 Signal:                                      │
│     │   ├─ matching.execute() → VWAP 撮合                  │
│     │   ├─ 更新余额 / 持仓                                │
│     │   ├─ 记录 trade_record                               │
│     │   └─ strategy.on_fill(fill_info)                     │
│     └─ 记录 equity_curve 数据点                            │
│  ⑥ strategy.on_end()                                       │
│  ⑦ evaluator 计算全部评估指标                              │
│  ⑧ 返回 BacktestSession（结果存内存）                      │
└────────────────────────────────────────────────────────────┘
```

---

## 5. 批量回测 & 并行调度

### 5.1 调度模型

```python
# batch_runner.py 伪代码

class BatchRunner:
    def __init__(self, max_concurrency: int = 4):
        self._semaphore = asyncio.Semaphore(max_concurrency)
        self._tasks: dict[str, BatchTask] = {}       # batch_id → task

    async def submit(self, strategy: str, slugs: list[str], config: dict) -> str:
        batch_id = uuid4().hex[:12]
        # 同一 slug 的数据只加载一次
        data_cache: dict[str, ArchiveData] = {}
        for slug in slugs:
            if slug not in data_cache:
                data_cache[slug] = await load_archive_data(slug)

        # 为每个 slug 创建独立回测任务
        tasks = []
        for slug in slugs:
            tasks.append(self._run_one(batch_id, strategy, slug, config, data_cache[slug]))
        asyncio.gather(*tasks)
        return batch_id

    async def _run_one(self, batch_id, strategy, slug, config, data):
        async with self._semaphore:
            # 在线程池中执行（DuckDB query 是同步阻塞的）
            result = await asyncio.to_thread(
                runner.run, strategy, slug, config, data
            )
            self._tasks[batch_id].results[slug] = result
```

### 5.2 性能管理策略

| 机制 | 说明 |
|------|------|
| **Semaphore** | 限制并发数（默认 4），防止内存溢出 |
| **数据共享** | 同一 slug 的历史数据在批次内只加载一次 |
| **线程池隔离** | DuckDB 同步查询跑在 `to_thread`，不阻塞事件循环 |
| **懒加载** | orderbook 重建按需进行，不预构建全量快照 |
| **内存估算** | 单场数据约 10-50MB（取决于时间跨度），4 并发 ≈ 200MB 峰值 |

---

## 6. 评估指标体系

### 6.1 自动计算指标（evaluator.py）

```
收益类
├── total_pnl              总盈亏
├── total_return_pct       总收益率
├── annualized_return      年化收益率
└── profit_factor          盈亏比 = 总盈利 / |总亏损|

风险类
├── max_drawdown           最大回撤
├── max_drawdown_duration  最大回撤持续时间
├── volatility             收益波动率（日化）
└── downside_deviation     下行偏差

风险调整收益
├── sharpe_ratio           Sharpe (rf=0)
├── sortino_ratio          Sortino
└── calmar_ratio           Calmar = 年化收益 / MDD

交易统计
├── total_trades           总交易次数
├── win_rate               胜率
├── avg_win / avg_loss     平均盈利 / 平均亏损
├── best_trade             单笔最大盈利
├── worst_trade            单笔最大亏损
├── avg_holding_period     平均持仓时间
├── buy_count / sell_count 买入 / 卖出次数
└── avg_slippage           平均滑点

曲线数据
├── equity_curve           权益曲线 [{timestamp, equity}]
├── drawdown_curve         回撤曲线 [{timestamp, drawdown_pct}]
└── position_curve         持仓变化曲线 [{timestamp, token_id, quantity}]
```

### 6.2 指标计算公式

```
total_return_pct = (final_equity - initial_balance) / initial_balance * 100
annualized_return = total_return_pct * (365 * 24 * 3600) / backtest_duration_seconds
max_drawdown = max((peak - trough) / peak) over equity curve
sharpe_ratio = mean(returns) / std(returns) * sqrt(N)       # N = 年化因子
sortino_ratio = mean(returns) / downside_std(returns) * sqrt(N)
calmar_ratio = annualized_return / max_drawdown
profit_factor = sum(winning_trades_pnl) / abs(sum(losing_trades_pnl))
win_rate = winning_trades / total_trades * 100
```

---

## 7. 策略注册与加载

### 7.1 加载机制

```python
# registry.py

import importlib.util
from pathlib import Path

class StrategyRegistry:
    """进程启动时扫描 strategies/ 目录，加载所有策略。"""

    def __init__(self):
        self._strategies: dict[str, type] = {}    # name → class

    def scan(self, directory: Path) -> None:
        for py_file in directory.glob("*.py"):
            if py_file.name.startswith("_"):
                continue
            spec = importlib.util.spec_from_file_location(py_file.stem, py_file)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            # 查找 BaseStrategy 子类
            for attr in dir(module):
                cls = getattr(module, attr)
                if (isinstance(cls, type)
                    and issubclass(cls, BaseStrategy)
                    and cls is not BaseStrategy):
                    self._strategies[cls.name] = cls

    def list(self) -> list[dict]:
        return [
            {"name": cls.name, "description": cls.description,
             "version": cls.version, "default_config": cls.default_config}
            for cls in self._strategies.values()
        ]

    def get(self, name: str) -> type:
        return self._strategies[name]
```

### 7.2 策略示例

```python
# strategies/example_momentum.py

from core.base_strategy import BaseStrategy
from core.types import TickContext, Signal


class MomentumStrategy(BaseStrategy):
    name = "momentum"
    description = "当价格连续上涨 N tick 时买入，连续下跌 N tick 时卖出"
    version = "0.1.0"
    default_config = {"lookback": 5, "position_size": 100}

    def on_init(self, config: dict) -> None:
        self.lookback = config.get("lookback", 5)
        self.position_size = config.get("position_size", 100)

    def on_tick(self, ctx: TickContext) -> list[Signal]:
        signals = []
        for token_id, history in ctx.price_history.items():
            if len(history) < self.lookback:
                continue
            recent = history[-self.lookback:]
            # 连续上涨 → 买入
            if all(recent[i] < recent[i+1] for i in range(len(recent)-1)):
                if ctx.positions.get(token_id, 0) == 0:
                    signals.append(Signal(
                        token_id=token_id,
                        side="BUY",
                        amount=self.position_size,
                    ))
            # 连续下跌 → 卖出
            elif all(recent[i] > recent[i+1] for i in range(len(recent)-1)):
                held = ctx.positions.get(token_id, 0)
                if held > 0:
                    signals.append(Signal(
                        token_id=token_id,
                        side="SELL",
                        amount=held,
                    ))
        return signals
```

---

## 8. HTTP API 设计（API-first）

所有功能通过 HTTP API 暴露，前端通过 `/strategy/*` 代理访问。

### 8.1 策略管理

| Method | Path | 功能 |
|--------|------|------|
| GET | `/strategies` | 列出已加载的策略列表 |
| GET | `/strategies/{name}` | 获取策略详情（描述、版本、配置参数 schema） |

响应示例：
```json
[
  {
    "name": "momentum",
    "description": "当价格连续上涨 N tick 时买入...",
    "version": "0.1.0",
    "default_config": {"lookback": 5, "position_size": 100},
    "file": "example_momentum.py"
  }
]
```

### 8.2 数据源查询（目录扫描）

| Method | Path | 功能 |
|--------|------|------|
| GET | `/data/archives` | 扫描 `archives/` 目录，列出所有归档场次 |
| GET | `/data/archives/{slug}` | 获取某场次的详情（时间范围、数据量、token 列表） |
| GET | `/data/markets` | 扫描 `prices/` + `orderbooks/` 目录，列出有数据的 market |

> **关键**：数据发现完全基于目录结构扫描（`Path.glob`），不调用 backend API。

响应示例（`/data/archives`）：
```json
[
  {
    "slug": "btc-updown-5m-1774600500",
    "path": "archives/btc-updown-5m-1774600500",
    "files": ["prices.parquet", "orderbooks.parquet", "ob_deltas.parquet", "live_trades.parquet"],
    "size_mb": 12.4,
    "time_range": {"start": "2025-05-24T...", "end": "2025-05-24T..."},
    "token_ids": ["1142465...", "5692915..."]
  }
]
```

### 8.3 回测执行

| Method | Path | 功能 |
|--------|------|------|
| POST | `/run` | 单场回测（同步返回或异步 task） |
| POST | `/batch` | 批量回测（异步，返回 batch_id） |
| GET | `/tasks` | 列出所有进行中/已完成的任务 |
| GET | `/tasks/{batch_id}` | 查询批量任务进度和子任务状态 |
| POST | `/tasks/{batch_id}/cancel` | 取消进行中的批量任务 |

`POST /run` 请求体：
```json
{
  "strategy": "momentum",
  "slug": "btc-updown-5m-1774600500",
  "initial_balance": 10000,
  "config": {"lookback": 5, "position_size": 100}
}
```

`POST /batch` 请求体：
```json
{
  "strategy": "momentum",
  "slugs": ["btc-updown-5m-1774600500", "eth-updown-5m-1774601000"],
  "initial_balance": 10000,
  "config": {"lookback": 5}
}
```

### 8.4 结果 & 评估查询

| Method | Path | 功能 |
|--------|------|------|
| GET | `/results` | 列出所有回测结果摘要 |
| GET | `/results/{session_id}` | 完整结果：评估指标 + 交易摘要 |
| GET | `/results/{session_id}/metrics` | 仅评估指标 |
| GET | `/results/{session_id}/equity` | 权益曲线数据 |
| GET | `/results/{session_id}/drawdown` | 回撤曲线数据 |
| GET | `/results/{session_id}/trades` | 交易明细列表 |
| GET | `/results/{session_id}/positions` | 持仓变化曲线 |
| DELETE | `/results/{session_id}` | 丢弃某次结果 |
| DELETE | `/results` | 清空所有结果 |

`GET /results/{session_id}` 响应示例：
```json
{
  "session_id": "a1b2c3d4",
  "strategy": "momentum",
  "slug": "btc-updown-5m-1774600500",
  "initial_balance": 10000,
  "status": "completed",
  "created_at": "2026-03-27T12:00:00Z",
  "duration_seconds": 3.2,
  "metrics": {
    "total_pnl": 523.45,
    "total_return_pct": 5.23,
    "max_drawdown": 2.1,
    "sharpe_ratio": 1.85,
    "win_rate": 62.5,
    "total_trades": 16,
    "profit_factor": 2.3
  },
  "summary": {
    "final_equity": 10523.45,
    "total_ticks": 300,
    "buy_count": 8,
    "sell_count": 8
  }
}
```

### 8.5 端口与代理

- 默认端口 `8072`，配置项 `STRATEGY_PORT`
- Vite 前端配置双代理：

```ts
// vite.config.ts
server: {
  proxy: {
    '/api':      { target: 'http://localhost:8071' },   // Backend
    '/strategy': { target: 'http://localhost:8072' },   // Strategy Engine
  }
}
```

---

## 9. 入口 & CLI

```python
# main.py — 进程入口

"""
Strategy Backtest Engine — 独立进程

用法:
  python main.py server                         # 启动 HTTP API 服务（默认模式）
  python main.py list                           # 列出已加载策略
  python main.py run <strategy> <slug> [opts]   # CLI 单场回测
  python main.py batch <strategy> [slugs] [opts]# CLI 批量回测

选项:
  --balance    初始资金 (default: 10000)
  --config     策略配置 JSON 字符串
  --port       HTTP 服务端口 (default: 8072)
  --workers    并行数 (default: 4)
"""
```

`server` 是主要运行模式，CLI 用于快速调试。

---

## 10. 数据访问层（目录扫描，零 API 调用）

### 10.1 数据发现

```python
# data_scanner.py — 通过目录结构发现可用数据

def scan_archives(data_dir: Path) -> list[ArchiveInfo]:
    """扫描 archives/ 下所有子目录，每个子目录名即 slug。"""
    results = []
    for d in (data_dir / "archives").iterdir():
        if d.is_dir():
            files = [f.name for f in d.glob("*.parquet")]
            results.append(ArchiveInfo(
                slug=d.name,
                path=d,
                files=files,
                size_bytes=sum(f.stat().st_size for f in d.glob("*.parquet")),
            ))
    return results

def scan_live_markets(data_dir: Path) -> list[MarketInfo]:
    """扫描 prices/ + orderbooks/ 目录，发现有数据的 market_id。"""
    ...
```

### 10.2 数据加载

```python
# data_loader.py — DuckDB 直接 READ_PARQUET，不 import backend

import duckdb

def load_archive(data_dir: Path, slug: str) -> ArchiveData:
    """加载一个归档场次的全部数据。"""
    base = data_dir / "archives" / slug
    return ArchiveData(
        prices=_query_parquet(base / "prices.parquet"),
        orderbooks=_query_parquet(base / "orderbooks.parquet"),
        ob_deltas=_query_parquet(base / "ob_deltas.parquet"),
        live_trades=_query_parquet(base / "live_trades.parquet"),
    )

def _query_parquet(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return duckdb.sql(f"SELECT * FROM read_parquet('{path}') ORDER BY timestamp").fetchdf().to_dict('records')
```

### 10.3 数据流

```
backend/data/
├── archives/{slug}/          ← 归档场次（主要数据源）
│   ├── prices.parquet
│   ├── orderbooks.parquet
│   ├── ob_deltas.parquet
│   └── live_trades.parquet
├── prices/{market_id}/       ← 实时采集的历史数据（可选）
├── orderbooks/{market_id}/
├── ob_deltas/{market_id}/
└── live_trades/{market_id}/
         │
         │  Path.glob() 发现
         │  DuckDB READ_PARQUET() 只读
         ▼
    ┌──────────────┐
    │ data_scanner  │  目录扫描 → 可用场次/市场列表
    │ data_loader   │  Parquet → list[dict]，按 token_id 分组索引
    └──────┬───────┘
           │
           ▼
    ┌─────────────┐
    │   runner     │  构建时间网格 → 逐 tick 重建快照
    └──────┬──────┘
           │
     TickContext
           │
           ▼
    ┌─────────────┐
    │  Strategy    │  on_tick() → Signal[]
    └──────┬──────┘
           │
        Signal[]
           │
           ▼
    ┌─────────────┐
    │  matching    │  VWAP 撮合 → FillInfo
    └──────┬──────┘
           │
     FillInfo
           │
           ▼
    ┌─────────────┐
    │  evaluator   │  交易记录 + 权益曲线 → 评估指标
    └──────┬──────┘
           │
           ▼
    BacktestSession (进程内存)
    ├── trades: list[FillInfo]
    ├── equity_curve: list[dict]
    ├── metrics: EvaluationMetrics
    └── strategy_summary: dict (from on_end)
```

---

## 11. 配置

```python
# config.py

from pathlib import Path
from pydantic_settings import BaseSettings

_STRATEGY_DIR = Path(__file__).resolve().parent

class StrategyEngineConfig(BaseSettings):
    # 数据目录（指向 backend/data，通过文件系统访问，不通过 API）
    data_dir: Path = _STRATEGY_DIR.parent / "backend" / "data"

    # 并行回测
    max_concurrency: int = 4              # 最大并行回测数
    tick_batch_size: int = 1000           # 每批处理的 tick 数（内存控制）

    # 策略
    strategies_dir: Path = _STRATEGY_DIR / "strategies"
    price_history_window: int = 60        # TickContext 中保留最近 N 个价格

    # HTTP 服务
    server_port: int = 8072
    server_host: str = "0.0.0.0"

    model_config = {"env_prefix": "STRATEGY_"}
```

环境变量覆盖：`STRATEGY_DATA_DIR`、`STRATEGY_MAX_CONCURRENCY`、`STRATEGY_SERVER_PORT` 等。

---

## 12. 依赖

独立安装，不依赖 backend 的包。核心库与 backend 版本兼容即可：

```
duckdb>=1.0
pyarrow>=17.0
pandas>=2.0
numpy>=1.26
pydantic>=2.0
pydantic-settings>=2.0
fastapi>=0.115
uvicorn>=0.30
```

> **注意**：不 `import` backend 下的任何模块。VWAP/滑点等计算逻辑在 `core/matching.py` 中独立实现。

---

## 13. 与 Backend 的关系

| 维度 | Backend (FastAPI :8071) | Strategy Engine (:8072) |
|------|------------------------|------------------------|
| 职责 | 实时代理 + 模拟交易 + 数据采集 | 历史回测 + 策略评估 |
| 数据 | 读写 Parquet，读写 Redis | **只读** Parquet（目录扫描） |
| 网络 | 代理 Polymarket API | **零网络请求** |
| 状态 | Redis | **进程内存** |
| 代码 | `backend/app/` | `Strategy/`（**不 import backend**） |
| 进程 | 常驻服务 | 独立进程（HTTP Server 为主） |
| 前端 | `/api/*` | `/strategy/*`（Vite 双代理） |
| 耦合点 | 写入 `backend/data/` | 读取 `backend/data/`（唯一交集） |

### 独立性保证

1. **无 import** — `Strategy/` 下的代码不 import `backend.app.*` 任何模块
2. **无 API 调用** — 不向 `localhost:8071` 发送任何 HTTP 请求
3. **无 Redis** — 不连接 Redis，状态全部在进程内存
4. **数据只读** — 通过 `Path` + `DuckDB READ_PARQUET` 直接读文件
5. **可独立部署** — 可以在没有 Backend 运行的情况下工作（只要 data 目录存在）

---

## 14. 后续扩展（当前不实现）

- [ ] 结果持久化（Parquet / SQLite）— 等策略调参稳定后
- [ ] 前端回测页面 — 权益曲线图表 + 指标仪表板 + 交易明细表
- [ ] 实时回调日志流（SSE）— 长时间回测的进度推送
- [ ] 策略参数优化 — 网格搜索 / 贝叶斯优化
- [ ] 多策略对比 — 同一场次不同策略的横向比较
- [ ] Walk-forward 分析 — 滚动窗口验证策略稳定性
