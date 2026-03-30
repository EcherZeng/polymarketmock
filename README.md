# Polymarket Mock Trading Platform

Polymarket 模拟交易平台 — 代理真实行情数据，提供模拟买卖 / 限价单 / 结算 / 回测。

## 项目结构

```
├── backend/          # FastAPI 后端 (Python 3.11+)
├── frontend/         # React + Vite 前端
├── Strategy/         # 策略回测引擎后端 (FastAPI, port 8072)
├── Strategyfrontend/ # 策略回测前端 (React + Vite, port 3022)
├── docker-compose.yml          # Docker 完整部署（前端 + 后端 + Redis）
├── docker-compose-redis.yml    # Docker 部署（后端 + Redis，无前端）
└── docs/             # 设计文档
```

## 快速开始

### 方式一：Docker Compose 启动（推荐）

> 需要安装 [Docker](https://docs.docker.com/get-docker/) 和 Docker Compose。

**启动后端 + Redis（不含前端）：**

```bash
docker compose -f docker-compose-redis.yml up --build
```

**启动全部（前端 + 后端 + Redis）：**

```bash
docker compose -f docker-compose.yml up --build
```

启动后访问：
- 后端 API: http://localhost:8071
- 后端文档: http://localhost:8071/docs
- 前端页面: http://localhost:3021 （仅完整部署）

**停止服务：**

```bash
docker compose -f docker-compose.yml down
```

---

### 方式二：本地启动

#### 0. 创建 Python 虚拟环境（首次）

```bash
# 在项目根目录下创建虚拟环境（需要 Python 3.11+）
python -m venv .venv

# 激活虚拟环境
# Windows PowerShell:
.venv\Scripts\Activate.ps1
# Linux / macOS:
source .venv/bin/activate
```

#### 1. 启动 Redis

本地需要一个 Redis 实例（默认 `localhost:6379`）。推荐用 Docker Compose：

```bash
# 只启动 Redis（推荐，持久化 + 自动管理）
docker compose -f docker-compose-redis-only.yml up -d
```

或者用 `docker run` 一次性启动：

```bash
docker run -d --name redis -p 6379:6379 redis:7-alpine redis-server --appendonly yes
```

#### 2. 启动后端

```bash
cd backend
pip install -e .        # 安装所有依赖（含 pandas, numpy, duckdb, pyarrow, websockets 等）
uvicorn app.main:app --host 0.0.0.0 --port 8071 --reload
```

后端 API 文档: http://localhost:8071/docs

> 启动时后端会自动连接 Polymarket WebSocket (`wss://ws-subscriptions-clob.polymarket.com/ws/market`)，
> 订阅已监控市场的 token 并推送实时行情。当 WS 连接正常时，HTTP 轮询自动降频/跳过。

#### 3. 启动前端

```bash
cd frontend
npm install
npm run dev
```

前端页面: http://localhost:5173

#### 4. 启动策略回测后端

```bash
cd Strategy
pip install -r requirements.txt   # 安装依赖
python main.py server --reload    # 启动 HTTP API（默认端口 8072）
```

策略后端 API: http://localhost:8072

#### 5. 启动策略回测前端

```bash
cd Strategyfrontend
npm install
npm run dev
```

策略前端页面: http://localhost:3022

---

## 环境变量

后端通过环境变量配置（前缀 `PM_`）：

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `PM_REDIS_URL` | `redis://localhost:6379` | Redis 连接地址 |
| `PM_GAMMA_API_URL` | `https://gamma-api.polymarket.com` | Gamma API 地址 |
| `PM_CLOB_API_URL` | `https://clob.polymarket.com` | CLOB API 地址 |
| `PM_DATA_DIR` | `./data` | 数据存储目录 |
| `PM_WS_URL` | `wss://ws-subscriptions-clob.polymarket.com/ws/market` | Polymarket WebSocket 地址 |
| `PM_WS_PING_INTERVAL` | `10` | WS 应用级 PING 间隔（秒） |
| `PM_WS_RECONNECT_MAX` | `30` | WS 断线重连最大退避（秒） |