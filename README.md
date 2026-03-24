# Polymarket Mock Trading Platform

Polymarket 模拟交易平台 — 代理真实行情数据，提供模拟买卖 / 限价单 / 结算 / 回测。

## 项目结构

```
├── backend/          # FastAPI 后端 (Python 3.11+)
├── frontend/         # React + Vite 前端
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

#### 1. 启动 Redis

本地需要一个 Redis 实例（默认 `localhost:6379`）。可以用 Docker 单独启动：

```bash
docker run -d --name redis -p 6379:6379 redis:7-alpine
```

#### 2. 启动后端

```bash
cd backend
pip install -e .
uvicorn app.main:app --host 0.0.0.0 --port 8071 --reload
```

后端 API 文档: http://localhost:8071/docs

#### 3. 启动前端

```bash
cd frontend
npm install
npm run dev
```

前端页面: http://localhost:5173

---

## 环境变量

后端通过环境变量配置（前缀 `PM_`）：

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `PM_REDIS_URL` | `redis://localhost:6379` | Redis 连接地址 |
| `PM_GAMMA_API_URL` | `https://gamma-api.polymarket.com` | Gamma API 地址 |
| `PM_CLOB_API_URL` | `https://clob.polymarket.com` | CLOB API 地址 |
| `PM_DATA_DIR` | `./data` | 数据存储目录 |