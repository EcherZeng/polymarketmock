---
description: "Use when modifying Strategy backend or Strategyfrontend for backtest, batch execution, evaluator metrics, portfolio comparison, and AI optimization. Enforces isolation, active-params contract, ratio-decimal contract, cumulative capital mode, and strategy-group comparison flow."
name: "Strategy Service Fullstack Rules"
applyTo: "Strategy/**,Strategyfrontend/**"
---
# Strategy Service Fullstack Rules

## Scope and Isolation

- Treat Strategy as a standalone local service. Do not import modules from backend or call Backend API at :8071.
- Only read historical data from backend/data (read-only). Never create, edit, or delete files under backend/data.
- Strategyfrontend must call only /strategy endpoints through src/api/client.ts. Do not call /api/*.
- Do not add WebSocket usage to Strategyfrontend. SSE (EventSource) is permitted for long-running task progress streams.

## Stack and Boundaries

- Backend stack is locked to FastAPI + Pydantic v2 + DuckDB + pandas/numpy + httpx (LLM calls only).
- Frontend stack is locked to React + TypeScript + Vite + shadcn/ui + react-query + Recharts.
- Do not introduce banned libraries: styled-components, MUI, Ant Design, Zustand, Redux, SQLAlchemy, Flask, Django, Next.js.
- Never manually edit Strategyfrontend/src/components/ui/*. Use shadcn CLI to add UI primitives.

## Backend Coding Rules

- Use async router handlers (async def) in api/*.py.
- Use Pydantic v2 serialization with model_dump(mode="json"). Do not use .dict().
- Use X | None syntax; do not use Optional[X].
- Keep io/async logic out of utils.
- Do not concatenate SQL strings from user input.

## Ratio and Percentage Contract

- Store and return all ratio metrics as raw decimals, not percentages.
- Never multiply by 100 in backend evaluator, APIs, or JSON result files.
- Frontend converts to percentage only in render code.
- If frontend sends pre-multiplied percentages, reject or clearly enforce decimal contract.

## Parameter Activation Contract (Req1)

- Follow scheme B: inactive params are not sent to backend and must not participate in computation.
- Use param_active(config, key) guard before strategy/risk branches that depend on optional params.
- Missing param key means skip that branch; do not emulate with disable_value.
- AI optimization must optimize only active_params provided by request.
- Prompt/schema generation for AI should include only active params.

## Parameter Metadata and Weights (Req2)

- param_schema must support visibility: core | advanced.
- param_schema must support weight: critical | high | medium | low.
- Treat "influence factors" as strategy parameters themselves, not separate signal coefficients.
- AI prompt should include weight context and require stricter reasoning for critical/high params.

## Metrics Correctness and Best Selection (Req3)

- Keep win_rate and all derived metrics consistent with evaluated trade/settlement definitions.
- Avoid selecting AI best result purely by one metric without reliability guard.
- Best selection and AI context should include total_trades (or equivalent reliability context).
- Maintain regression tests for low-trade high-win-rate edge cases and settlement split edge cases.

## Capital Mode in Batch Execution (Req5)

- Support both fixed and cumulative capital modes.
- In cumulative mode, execute slugs in request order (portfolio item order).
- Carry previous slug final_equity into next slug initial balance.
- If final_equity <= 0, stop subsequent slugs and mark capital_exhausted.
- Persist capital mode and per-slug capital chain in batch results.

## Strategy Group Comparison (Req4)

- A portfolio is a strategy group when all items share identical strategy plus identical config.
- Strategy group status is derived at query time; do not require manual tagging.
- Comparison entry is from portfolio list selecting 2+ strategy groups, then navigate to /comparison.
- Comparison should present parameter differences across groups.
- Comparison should present slug coverage count per group.
- Comparison should present return summary (min/max/avg).

## Frontend Data and API Rules

- Keep shared contracts in Strategyfrontend/src/types/index.ts aligned with backend models.
- Keep API calls centralized in Strategyfrontend/src/api/client.ts with explicit return types.
- Convert camelCase UI input to backend snake_case in API layer only.
- Use react-query patterns: useQuery for reads, useMutation for writes, invalidate queries on success.
- For task polling, enable interval only while task is running.
- Task status values: "running" | "completed" | "cancelled" | "failed" | "interrupted". "interrupted" means the server restarted while the task was running; treat it as terminal (no further polling).

## File Placement Rules

- Backend new type -> Strategy/core/types.py
- Backend new logic -> Strategy/core/
- Backend new router -> Strategy/api/ and register in Strategy/api/app.py
- Frontend new page -> Strategyfrontend/src/pages/ and route registration in Strategyfrontend/src/App.tsx
- Frontend new business component -> Strategyfrontend/src/components/

## Non-goals

- Do not add cross-service coupling to Backend.
- Do not persist backtest outputs to Parquet or DuckDB.
- Do not bypass config paths with hardcoded absolute paths.
