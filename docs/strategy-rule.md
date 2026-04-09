# Strategy Engine & Strategyfrontend — AI Agent Rules

Strategy backtest engine + dedicated frontend. Reads Parquet historical data from `backend/data/` (read-only), self-contained matching engine, provides strategy backtest / batch execution / evaluation / AI optimization. Zero communication with Backend.

## MUST NOT (hard constraints)

**Architecture isolation:**
- **MUST NOT** import any backend modules (`from app.*`, `from backend.*`)
- **MUST NOT** call Backend API (`:8071`). Only coupling is `backend/data/` directory (read-only)
- **MUST NOT** make any external network requests (HTTP/WS to Polymarket, Gamma, CLOB, etc.). Strategy is a pure local process (exception: httpx for LLM calls in `ai_optimizer.py`)
- **MUST NOT** modify any files under `backend/` directory (data is read-only)
- **MUST NOT** use Redis in Strategy code (no Redis dependency)

**Data / storage:**
- **MUST NOT** write backtest results to Parquet/DuckDB. Results go to JSON in `Strategy/results/` only
- **MUST NOT** create or modify files under `backend/data/`
- **MUST NOT** hardcode file paths. Use `config.data_dir` / `config.results_dir`

**Frontend isolation:**
- **MUST NOT** call Backend API (`/api/*`) from Strategyfrontend. Only call `/strategy/*`
- **MUST NOT** use WebSocket in Strategyfrontend (Strategy has no WS endpoint)
- **MUST NOT** manually edit files under `Strategyfrontend/src/components/ui/` (shadcn auto-generated)
- **MUST NOT** use styled-components, MUI, Ant Design
- **MUST NOT** use Zustand, Redux, or any state management library (use react-query for server state)

**Code conventions:**
- **MUST NOT** use `Optional[X]` — use `X | None`
- **MUST NOT** use `.dict()` — use `model_dump(mode="json")`
- **MUST NOT** use sync blocking I/O in async functions (`time.sleep`, sync large file reads, etc.)
- **MUST NOT** concatenate SQL strings. DuckDB queries use parameterized or f-string path interpolation (paths MUST come from config, never from user input)
- **MUST NOT** put I/O or async code in `utils/`

**Ratio / percentage boundary:**
- **MUST NOT** store ratio metrics as percentages in backend. ALL ratio-type metrics are stored as decimals in `[0, 1]` or unbounded floats (e.g. `total_return_pct=0.15` means 15%, `max_drawdown=0.08` means 8%, `win_rate=0.65` means 65%). Frontend converts to percentage display (`value * 100` + `%` suffix) at render time only
- **MUST NOT** multiply by 100 in backend evaluator, API response, or JSON result files
- **MUST NOT** accept pre-multiplied percentages from frontend; if frontend sends a value like `15` intending 15%, backend must reject or document the raw decimal contract

## STACK (locked — no substitutions)

**Strategy Backend**: Python >=3.11, FastAPI >=0.115, uvicorn, DuckDB >=1.0, PyArrow >=17.0, pandas >=2.0, numpy >=1.26, Pydantic v2, httpx (LLM calls only)
**Strategyfrontend**: React 19 + TypeScript + Vite 8, shadcn/ui (style:`radix-nova`, icons:`lucide`, Tailwind CSS v4), Recharts, @tanstack/react-query, React Router, axios
**Infra**: Docker Compose, Nginx (production proxy)
**BANNED**: styled-components, MUI, Ant Design, SQLAlchemy, Flask, Django, Next.js, Zustand, Redux, Redis

## PROJECT STRUCTURE

```
Strategy/
  config.py              — Config (env prefix STRATEGY_)
  main.py                — Entry (uvicorn + CLI)
  api/
    app.py               — FastAPI instance + lifespan + CORS
    strategies.py        — GET /strategies
    data.py              — GET/POST/DELETE /data/*
    execution.py         — POST /run, /batch, GET/POST /tasks/*
    results.py           — GET/DELETE /results/*, /results-stats, /results-cleanup
    presets.py           — GET/PUT/DELETE /presets/*
    portfolios.py        — CRUD /portfolios/*
    ai_optimize.py       — POST/GET /ai-optimize/*
    result_store.py      — Result persistence (JSON files)
    state.py             — Global runtime state (in-memory)
  core/
    types.py             — Data types (Signal, TickContext, FillInfo, TokenSnapshot)
    base_strategy.py     — BaseStrategy abstract base class
    unified_base.py      — UnifiedBaseStrategy (shared risk-control layer)
    registry.py          — Strategy registration + preset management
    data_loader.py       — DuckDB loads Parquet
    data_scanner.py      — Directory scan to discover data sources
    matching.py          — VWAP matching engine
    runner.py            — Single backtest runner (tick loop)
    batch_runner.py      — Parallel batch scheduler
    evaluator.py         — Evaluation metrics calculation
    result_digest.py     — Result summary generation
    ai_optimizer.py      — LLM multi-round optimizer
    market_profiler.py   — Market data profiling
  strategies/
    unified_strategy.py  — Single user strategy (implements compute_entry_signals)
  results/               — JSON result files
    batches/             — Batch task JSON
    portfolios/          — Portfolio JSON
    ai_tasks/            — AI optimization task JSON

Strategyfrontend/
  src/
    api/client.ts        — axios, baseURL=/strategy
    types/index.ts       — TS types (aligned with Pydantic models)
    pages/               — Page components
    components/          — Business components
    components/ui/       — shadcn auto-generated (NEVER edit manually)
    hooks/               — Custom hooks
    lib/utils.ts         — cn() utility
```

**Where to put new files:**
- New type → `core/types.py` | New API → `api/` + register in `app.py` | New logic → `core/` | New strategy → `strategies/`
- New page → `pages/` + register in `App.tsx` | New component → `components/` | shadcn → `npx shadcn@latest add <name>`
- API fn → `api/client.ts` | TS type → `types/index.ts`

## BACKEND RULES

**Async-first**: ALL router handlers use `async def`. DuckDB queries are sync — acceptable for single backtest; use `asyncio.to_thread()` in batch scenarios. Batch concurrency via `asyncio.Semaphore(max_concurrency=4)`.

**Pydantic v2**:
- `from __future__ import annotations` at top of every file
- `X | None` (NOT `Optional[X]`), `list[dict]`, `dict[str, Any]`
- Serialize: `model_dump(mode="json")` (NOT `.dict()`)

**Ratio metrics convention**: All ratio-type metrics (`total_return_pct`, `max_drawdown`, `win_rate`, `volatility`, `annualized_return`, `sharpe_ratio`, `sortino_ratio`, `calmar_ratio`, `avg_slippage`, `slippage_pct`, `hold_to_settlement_ratio`, `downside_deviation`) are stored and returned as **raw decimals**. Example: 15% return → `0.15`, 8% drawdown → `0.08`, 65% win rate → `0.65`. NEVER multiply by 100 in backend code.

**Config**: All settings in `config.py` `Config` class. Env prefix `STRATEGY_`. Key settings: `data_dir` (backend/data path), `results_dir`, `server_port` (8072), `max_concurrency` (4), `price_history_window` (1200s), `slug_timeout` (600s), `batch_chunk_size` (20). LLM: `llm_api_key`, `llm_api_url`, `llm_default_model`.

**Data loading**: Prefer `sessions/{slug}/archive/*.parquet`, fallback to merging `live/` chunks. DuckDB pattern: `duckdb.sql("SELECT * FROM read_parquet('{path}') ORDER BY timestamp").fetchdf()`. Decode: token_id int32 → string, side int8 → "BUY"/"SELL", timestamp → ISO 8601.

**Matching engine**: `calculate_vwap_from_levels(levels, amount, max_cost, min_price)` — consume levels incrementally. BUY: consume ask depth, `max_cost` budget cap. SELL two modes: `ideal` (fill at mid, zero slippage), `orderbook` (walk bid depth, optional `min_price` floor). Slippage: `(avg_price - mid) / mid`.

**Tiered Anchor Price**:
```
spread < 0.05        → mid_price        (anchor_source="mid")
0.05 ≤ spread < 0.15 → micro_price      (anchor_source="micro")
spread ≥ 0.15        → last_trade_price  (anchor_source="last_trade")
                       fallback → micro_price (anchor_source="micro")
```

**Strategy registration**: On startup `registry.scan(strategies_dir)`: load `strategy_presets.json` + `strategy_presets_user.json` (user overlay), scan `strategies/*.py` for `BaseStrategy` subclasses. Preset file contains: `unified_rules` (risk rules), `param_schema` (param definitions + i18n), `param_groups` (grouping), `strategies` (concrete preset configs).

**Result storage**: Single result → `results/{session_id}.json`. Batch → `results/batches/{batch_id}.json`. Portfolio → `results/portfolios/{portfolio_id}.json`. AI task → `results/ai_tasks/{task_id}.json`. In-memory active task state in `api/state.py`, persistence via `api/result_store.py`.

**Evaluation metrics**:
- Returns: total_pnl, total_return_pct, annualized_return, profit_factor
- Risk: max_drawdown, max_drawdown_duration, volatility, downside_deviation
- Risk-adjusted: sharpe_ratio, sortino_ratio, calmar_ratio
- Trade stats: total_trades, win_rate, avg_win, avg_loss, avg_slippage
- Settlement: settlement_pnl, trade_pnl, expected_value
- Annualization factor: `365 × 24 × 3600 / duration_seconds`

**Code style**: `from __future__ import annotations` first line. Import order: stdlib → third-party → local (blank lines between). Section comments: `# ── SectionName ────────`.

## FRONTEND RULES

**Components**: Function components + hooks only. Export: `export default function Name()`. Props: `interface NameProps {}`. Pages in `pages/` (PascalCase + Page suffix), reusable in `components/`.

**shadcn/ui**: Add via `cd Strategyfrontend && npx shadcn@latest add <name>`. NEVER manually edit `components/ui/`. Use `cn()` for className merging. Style: `radix-nova`, icons: `lucide-react`.

**Data fetching**: `useQuery` for reads (`queryKey`, `queryFn`, optional `refetchInterval`). `useMutation` for writes (`onSuccess` → `invalidateQueries`). Batch task polling: `refetchInterval: 3000` (only while running).

**API client**: All requests via `src/api/client.ts`. One function per endpoint. axios baseURL: `/strategy` (Vite proxy → `http://localhost:8072`, Nginx same path). Explicit TS return types. camelCase params → snake_case for backend.

**Ratio display convention**: Backend returns all ratio metrics as raw decimals. Frontend MUST convert at render time: `(value * 100).toFixed(2) + '%'`. Apply this to: `total_return_pct`, `max_drawdown`, `win_rate`, `volatility`, `annualized_return`, `avg_slippage`, `slippage_pct`, `hold_to_settlement_ratio`, `downside_deviation`. Do NOT store converted percentages in state or types — always keep raw decimals in TS interfaces, convert only in JSX/display logic.

**Types**: All in `types/index.ts`. `interface` for objects, `type` for unions. Field names align with backend Pydantic model (snake_case). Use `import type`.

**Styles**: Tailwind utility classes ONLY (except CSS vars in `index.css`). Semantic colors: `text-foreground`, `text-muted-foreground`, `bg-background`, `border`. neutral palette, dark mode via next-themes.

**Charts**: Recharts: ComposedChart (dual-axis), ResponsiveContainer. Used for equity curve, drawdown curve, price curve, K-line.

**Imports**: Always use `@/` prefix alias (`@/components`, `@/api`, `@/types`).

## DOCKER

Services: `strategy` :8072 (volume `../backend/data:/app/data:ro`, env `STRATEGY_DATA_DIR=/app/data`), `strategyfrontend` :3022 (nginx proxy `/strategy/` → `http://strategy:8072/`). Network: `polymarket`.

Local dev:
1. Strategy: `cd Strategy && pip install -r requirements.txt && python main.py` (default :8072)
2. Strategyfrontend: `cd Strategyfrontend && npm install && npm run dev` (default :3022, Vite proxy `/strategy` → `http://localhost:8072`)

## WORKFLOWS

**New API endpoint**: `core/types.py` (data type) → `core/` (logic) → `api/` (router handler) → `api/app.py` (register router) → `types/index.ts` (TS type) → `api/client.ts` (request fn) → page/component (useQuery/useMutation).

**New strategy param**: `strategy_presets.json` (default + param_schema) → `strategies/unified_strategy.py` (logic) → `core/unified_base.py` (risk layer, if needed) → frontend `StrategyConfigForm` auto-renders from param_schema.

**New evaluation metric**: `core/evaluator.py` (calculate, return raw decimal) → `core/types.py` (type) → `types/index.ts` (TS type, raw decimal) → `MetricsPanel.tsx` (display, `* 100` + `%` at render).

**New shadcn component**: `cd Strategyfrontend && npx shadcn@latest add <name>`

## API ENDPOINTS

| Module | Method | Path | Purpose |
|--------|--------|------|---------|
| strategies | GET | `/strategies` | List strategies |
| strategies | GET | `/strategies/{name}` | Strategy detail |
| presets | GET | `/presets` | Presets + schema + groups |
| presets | GET/PUT/DELETE | `/presets/{name}` | Single preset CRUD |
| presets | GET/PUT | `/presets/rules/unified` | Unified risk rules |
| data | GET | `/data/archives` | List archived data sources |
| data | GET | `/data/archives/{slug}` | Archive detail |
| data | DELETE | `/data/archives/{slug}` | Delete archive |
| data | POST | `/data/archives/{slug}/track` | Mark tracked |
| data | GET | `/data/tracked` | List tracked |
| data | GET | `/data/incomplete` | Incomplete data sources |
| data | POST | `/data/cleanup` | Cleanup data sources |
| execution | POST | `/run` | Single backtest |
| execution | POST | `/batch` | Batch backtest |
| execution | GET | `/tasks` | Task list |
| execution | GET | `/tasks/{batch_id}` | Task detail |
| execution | POST | `/tasks/{batch_id}/cancel` | Cancel task |
| results | GET | `/results` | Result summary list |
| results | GET | `/results/{id}` | Full result |
| results | GET | `/results/{id}/metrics` | Metrics only |
| results | GET | `/results/{id}/equity` | Equity curve |
| results | GET | `/results/{id}/drawdown` | Drawdown curve |
| results | GET | `/results/{id}/drawdown-events` | Drawdown events |
| results | GET | `/results/{id}/trades` | Trade list |
| results | GET | `/results/{id}/positions` | Position curve |
| results | DELETE | `/results/{id}` | Delete result |
| results | DELETE | `/results` | Delete all |
| results | GET | `/results-stats` | Storage stats |
| results | POST | `/results-cleanup` | Batch cleanup |
| results | POST | `/results-cleanup/by-batch/{id}` | Cleanup by batch |
| results | POST | `/results-cleanup/batches` | Batch cleanup batches |
| portfolios | GET/POST | `/portfolios` | List / create |
| portfolios | GET/PUT/DELETE | `/portfolios/{id}` | Portfolio CRUD |
| portfolios | PUT/DELETE | `/portfolios/{id}/items` | Portfolio item management |
| ai-optimize | GET | `/ai-optimize/models` | LLM model list |
| ai-optimize | POST/GET | `/ai-optimize` | Submit / list |
| ai-optimize | GET | `/ai-optimize/{id}` | Task detail |
| ai-optimize | POST | `/ai-optimize/{id}/stop` | Stop optimization |
