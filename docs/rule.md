# Polymarket Mock Trading — AI Agent Rules

Polymarket mock trading platform. Proxies real market data (Gamma + CLOB API) for simulated order matching against real orderbook depth. Single-user, no auth.

## STACK (locked — no substitutions)

**Backend**: Python >=3.11, FastAPI >=0.115, uvicorn >=0.30, httpx(async) >=0.27, Pydantic v2 + pydantic-settings, Redis 7 (redis-py async + hiredis), DuckDB >=1.0 + PyArrow >=17.0, pandas >=2.0 + numpy >=1.26 (DuckDB fetchdf), websockets >=12.0 (Polymarket Market Channel)
**Frontend**: React + TypeScript + Vite 8, shadcn/ui (style:`radix-nova`, icons:`lucide`, Tailwind CSS v4), Lightweight Charts (TradingView), @tanstack/react-query, React Router, axios
**Infra**: Docker Compose
**BANNED**: styled-components, MUI, Ant Design, SQLAlchemy, Flask, Django, Next.js, Zustand, Redux

## PROJECT STRUCTURE

```
backend/app/
  main.py          — FastAPI entry (lifespan)
  config.py        — pydantic-settings, env prefix PM_
  models/          — Pydantic models only (no logic)
  routers/         — thin route handlers (delegate to services), ws.py (WebSocket endpoint)
  services/        — business logic (matching, proxy, settlement, backtest, ws_manager)
  storage/         — Redis wrapper, DuckDB/Parquet, data collector
  utils/           — pure functions (NO I/O, NO async)
frontend/src/
  api/client.ts    — axios wrapper, one function per endpoint
  types/index.ts   — TS types aligned with backend Pydantic models
  pages/           — page components
  components/      — business components
  components/ui/   — shadcn auto-generated (NEVER edit manually)
```

**Where to put new files:**
- Model → `models/` | API route → `routers/` + register in `main.py` | Logic → `services/` | Storage → `storage/`
- Page → `pages/` + register in `App.tsx` | Component → `components/` | shadcn → `npx shadcn@latest add <name>`
- API fn → `api/client.ts` | TS type → `types/index.ts`

## BACKEND RULES

**Async-first**: ALL functions use `async def` (routers, services, storage). `await` all I/O. Redis via `redis.asyncio`, HTTP via `httpx.AsyncClient`. No sync blocking in async.

**Pydantic v2**:
- `from __future__ import annotations` at top of every file
- `X | None` (NOT `Optional[X]`), `list[dict]`, `dict[str, Any]`
- Serialize: `model_dump(mode="json")` (NOT `.dict()`)
- Enums: `class Side(str, enum.Enum): BUY = "BUY"`

**Financial precision**: VWAP/slippage/price calcs use `decimal.Decimal` internally. API I/O uses `float`. Round to 6 dp (price/amount) or 4 dp (percentage).

**Time**: `datetime.now(timezone.utc).isoformat()` — always UTC ISO 8601.

**Config**: All settings via `app/config.py` `Settings` class. Env prefix `PM_`. No hardcoded URLs/ports/TTLs.

**Redis keys**: `entity:subentity:id` pattern. Examples: `account:balance`, `account:positions:{token_id}`, `orders:pending:{order_id}`, `trades:history`. Store numbers as `str()`, complex data as JSON string. Define key constants.

**Routers**: `APIRouter()` registered via `include_router`. Route functions ONLY validate params + call service. Errors via `HTTPException`. Use `response_model=`. Use `Query()` with constraints.

**Code style**: Module-level docstring. `from __future__ import annotations` first line. Import order: stdlib → third-party → local (blank lines between). Section separators: `# ── SectionName ────────`.

## FRONTEND RULES

**Components**: Function components + hooks only. Export: `export default function Name()`. Props: `interface NameProps {}`. Pages in `pages/`, reusable in `components/`.

**shadcn/ui**: Add via `npx shadcn@latest add <name>` — NEVER manually edit `components/ui/`. Use `cn()` for className merging. Prefer shadcn semantic components. Tailwind v4 syntax.

**Data fetching**: `useQuery` for reads (with `queryKey`, `queryFn`, optional `refetchInterval`). `useMutation` for writes (with `onSuccess` → `invalidateQueries`).

**API client**: All requests via `src/api/client.ts`. One function per endpoint. axios baseURL `/api` (Vite proxy → backend). Explicit TS return types. camelCase params → snake_case for backend.

**Types**: All in `types/index.ts`. `interface` for objects, `type` for unions. Match backend Pydantic field names. Use `import type`.

**Styles**: Tailwind utility classes ONLY (except CSS vars in `index.css`). Semantic colors: `text-foreground`, `text-muted-foreground`, `bg-background`, `border`. Chart colors: `chart-1` (red/asks), `chart-2` (green/bids).

**Imports**: Always use `@/` prefix. Configured in `vite.config.ts` + `tsconfig.json`.

## DATA PERSISTENCE (critical)

- Real market prices/orderbook snapshots → **Parquet** (DuckDB query), partitioned `{market_id}/{date}.parquet` under `backend/data/`
- Simulated trading data (balance, positions, orders, trades, PnL) → **Redis ONLY**
- NEVER write simulated data to Parquet/DuckDB/files
- NEVER store real market data in Redis only — must persist to Parquet

## EXTERNAL API

**Gamma API** (`https://gamma-api.polymarket.com`): markets, events. Cache TTL: 60s (`PM_CACHE_TTL_MARKETS`).
**CLOB API** (`https://clob.polymarket.com`): orderbook, midpoint. Cache TTL: orderbook 5s, midpoint 3s. Order execution MUST use `get_orderbook_raw` (bypass cache).
**Proxy rules**: All external requests via `polymarket_proxy.py`. Frontend NEVER calls Polymarket directly. Cache in Redis: `cache:{api_name}:{params_hash}`.

## MATCHING ENGINE

- **Market order**: fetch CLOB orderbook → consume levels (VWAP) → update balance/positions → record trade
- **Limit order**: reserve funds → store pending → check midpoint every 5s → fill on trigger
- Validate: sufficient position (sell), sufficient balance (buy)
- Read-only: simulated trades NEVER modify real orderbook
- Partial fills are valid when depth insufficient
- Settlement: winning token → $1/share, losing → $0/share

## DOCKER

Services: `redis` :6379 (AOF), `backend` :8071 (depends redis, mount `./backend/data:/app/data`), `frontend` :3021 (depends backend).
Env: `PM_REDIS_URL=redis://redis:6379`, `PM_GAMMA_API_URL=https://gamma-api.polymarket.com`, `PM_CLOB_API_URL=https://clob.polymarket.com`, `PM_DATA_DIR=/app/data`.
Local dev: Vite proxies `/api` → `http://localhost:8071`.

## WEBSOCKET (Polymarket Market Channel)

**Architecture**: Backend proxy mode — backend maintains single upstream WS to Polymarket (`wss://ws-subscriptions-clob.polymarket.com/ws/market`), processes events (updates Redis + writes Parquet), fans out to frontend clients via `/ws/market` endpoint.

**Upstream events**: `book` (full orderbook snapshot), `price_change` (incremental delta), `last_trade_price`, `best_bid_ask`, `tick_size_change`, `new_market`, `market_resolved`. Polymarket may send batch JSON arrays — always handle both `dict` and `list[dict]`.

**App-level heartbeat**: Send `"PING"` every `ws_ping_interval` seconds. Polymarket replies `"PONG"`. MUST disable library-level ping (`ping_interval=None`) in `websockets.connect()` — Polymarket does not respond to WS protocol pings.

**Frontend protocol**: Client sends `{"type": "subscribe", "asset_ids": [...]}` / `{"type": "unsubscribe", ...}` / `"PING"`. Server pushes Polymarket-format events. React hook: `useMarketWebSocket(assetIds)` — single connection per market page, auto-reconnect with exponential backoff.

**Fallback**: When WS connected, `data_collector` skips orderbook/price HTTP polling and reduces live-trade polling to 30s. When WS disconnects, full HTTP polling resumes automatically.

**Config**: `PM_WS_URL`, `PM_WS_PING_INTERVAL` (10s), `PM_WS_RECONNECT_MAX` (30s).

## SECURITY

Single-user, no auth/JWT/session. CORS allow-all (dev). No real funds. Validate all numeric input in router/Pydantic (`gt=0`, `ge=0`, `le=1`). Parameterized DuckDB queries only — no SQL string concatenation.

## WORKFLOWS

**New API endpoint**: models/ (Pydantic) → services/ (async logic) → routers/ (thin handler) → main.py (register) → types/index.ts (TS type) → api/client.ts (request fn) → component (useQuery/useMutation).

**New shadcn component**: `cd frontend && npx shadcn@latest add <name>`. Never create/edit `components/ui/` manually.

**Run project**: `docker-compose up -d` or locally:
1. Venv: `python -m venv .venv && .venv\Scripts\Activate.ps1` (Windows) / `source .venv/bin/activate` (Linux/macOS)
2. Redis: `docker compose -f docker-compose-redis-only.yml up -d`
3. Backend: `cd backend && pip install -e . && uvicorn app.main:app --reload --port 8071`
4. Frontend: `cd frontend && npm install && npm run dev`