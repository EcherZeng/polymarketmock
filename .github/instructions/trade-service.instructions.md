---
description: "Use when modifying trade/ backend or tradefrontend/ to enforce UTC time pipeline and unified numeric precision contracts between Python services and the React UI. Trigger phrases: trade UTC, ISO 时间, 时间格式, 数字精度, balance 精度, shares 精度, fmtTimeCst, fmtUsd, ratio-decimal, 时区, 前后端契约."
name: "Trade Service UTC & Number Format Rules"
applyTo: "trade/**,tradefrontend/**"
---
# Trade Service — UTC Time & Number Format Contract

This file unifies how `trade/` (Python) and `tradefrontend/` (React) exchange and display **time** and **numbers**. Apply on every change touching API payloads, LiveHub events, persisted rows, or UI rendering.

## Time Pipeline (UTC end-to-end)

### Backend (`trade/**/*.py`)

- All `datetime` values that cross a boundary (API JSON, LiveHub WS, DuckDB row, log line) MUST be **timezone-aware UTC**.
  - Construct with `datetime.now(timezone.utc)` — never `datetime.now()`, never `datetime.utcnow()` (naive, deprecated).
  - Convert from epoch with `datetime.fromtimestamp(ts, tz=timezone.utc)`.
  - Parse with `datetime.fromisoformat(s)`; if the result is naive, attach `tzinfo=timezone.utc` immediately.
- Wire format MUST be **ISO 8601 with offset** (e.g. `2026-04-29T03:14:15.123456+00:00`).
  - Always emit via `.isoformat()` on a tz-aware UTC datetime. Do not strip the offset, do not pre-format `"YYYY-MM-DD HH:MM:SS"` for transport.
  - For Unix timestamps use **seconds as integer** named `*_epoch` (e.g. `start_epoch`, `end_epoch`). Use **milliseconds only** when proxying upstream sources that already use ms (Binance kline, Polymarket WS) and name the field `*_ms` to make it explicit.
- Slug window parsing MUST go through `core.types.parse_slug_window(slug)` → `(start_iso, end_iso)`. Do not re-implement.
- LiveHub envelope (`infra/live_hub.py`): the broadcast helper already injects `ts: datetime.now(timezone.utc).isoformat()`. Inner `data` payload timestamps follow the same UTC ISO rule; do not duplicate `ts` inside `data`.
- DuckDB persistence: store ISO UTC strings (`VARCHAR`) for human-readable timestamps, integer epoch seconds for window boundaries. Never store local-time strings.
- Logs: prefer `logger.info("... %s", iso_str)` with the same UTC ISO string, not `time.strftime` against local time.

### Frontend (`tradefrontend/**/*.{ts,tsx}`)

- Display always renders in **CST (UTC+8)** via the formatters in [tradefrontend/src/lib/utils.ts](tradefrontend/src/lib/utils.ts):
  - `fmtTimeCst(iso)` → `HH:mm:ss`
  - `fmtDateTimeCst(iso)` → `MM-DD HH:mm`
  - `epochToIso(epoch)` for converting `*_epoch` (seconds) before passing into the formatters.
- FORBIDDEN in frontend code:
  - `new Date(iso).toLocaleString()` without `timeZone: "Asia/Shanghai"`.
  - `iso.slice(0, 19).replace("T", " ")`, `iso.slice(11, 19)`, `iso.split("T")[1]`, or any other string-based slicing of ISO timestamps.
  - Hand-rolled "+8 小时" math on epochs/ISO strings — the formatter already does it via `timeZone: "Asia/Shanghai"`.
- If a new display variant is needed (e.g. `MM-DD HH:mm:ss`), add a new `fmt*Cst` helper to `lib/utils.ts` and reuse — do not inline in components.
- React-query / WS message handlers MUST keep ISO strings as-is in state; conversion happens only at the render boundary.

## Number / Precision Contract

### Backend rounding (apply at the serialization boundary, not deep in core math)

| Domain                    | Field examples                             | Precision | Rule                                  |
|---------------------------|--------------------------------------------|-----------|---------------------------------------|
| USD balances / PnL        | `balance`, `initial_balance`, `equity`, `realised_pnl`, `unrealised_pnl`, `total_pnl`, `total_trade_pnl`, `total_settlement_pnl` | `round(x, 6)` | USDC.e has 6 decimals; preserve full precision on the wire. |
| Positions (shares)        | `positions[token_id]`                      | `round(x, 4)` | Polymarket shares quoted to 4 dp. |
| Order size for CLOB       | `OrderArgs.size` (BUY shares / SELL shares)| `round(x, 2)` | CLOB enforces 2-dp size; rounding here is a hard requirement, not cosmetic. |
| Prices / probabilities    | `price`, `bid`, `ask`, `mid`, `anchor_price`, `outcome_price` | unrounded float in [0,1] | Round only on display. Side consistency: see `/memories/repo/strategy-price-side-consistency.md`. |
| Time remaining            | `time_remaining_s`                         | `round(x, 1)` | |
| BTC trend metrics         | `a1`, `a2`, `amplitude`, `slope`           | `round(x, 8)` | High-precision diagnostic values. |
| Ratios / percentages      | `win_rate`, `target_ratio`, `stop_ratio`, `weight`, `confidence`, ... | raw decimal in [0,1], unrounded | **NEVER multiply by 100 in backend.** Frontend converts on render. |

- All ratio-typed parameters (entry/exit thresholds, weights, fractions) MUST be 0–1 decimals on every API in/out and in every preset/composite payload. Rejecting `> 1` for ratio fields at the request boundary is preferred over silently dividing.
- Do not round inside core math (`PositionTracker`, `StrategyEngine`, `BtcTrend.compute`); round only when emitting a payload to API / LiveHub / DataStore. This avoids drift from compounded rounding.
- Use `round(...)`, not `f"{x:.6f}"` for numeric fields — JSON must carry numbers, not strings.

### Frontend rendering

- USD: `fmtUsd(value, decimals = 2)` from [tradefrontend/src/lib/utils.ts](tradefrontend/src/lib/utils.ts). Default 2 dp for UI; pass `decimals=4` only for micro-positions explicitly.
- Shares: render with `value.toFixed(4)` (matches backend storage); never trim trailing zeros for table columns (visual alignment).
- Probability / price (0–1): render as percent with one decimal — `(value * 100).toFixed(1) + "%"`. Conversion happens **only here**, not in the API layer.
- Ratio params surfaced in config UI: input/display as percent (`value * 100`), but the payload sent back to `/config` MUST be re-divided to 0–1 before POST. Do this in `src/api/*` not in components.
- PnL color: `pnlColor(value)` — do not hand-code green/red class names.
- FORBIDDEN: `value.toFixed(2) + "$"`, `\`${value}USD\``, ad-hoc currency strings — always go through `fmtUsd`.

## Type Contract Sync

- New fields added to a LiveHub event, REST response, or DuckDB schema MUST be added to:
  1. The Python emit site (with the rounding rule above).
  2. `tradefrontend/src/types/` shared types.
  3. The matching `src/api/*.ts` mapper if any case conversion is needed.
- Backend uses `snake_case` JSON keys; frontend keeps `snake_case` in transport types and only renames in component-local view models when justified. Do not silently rename in the API layer.

## Quick Self-Check Before Submitting

- [ ] No `datetime.now()` / `utcnow()` introduced; every new datetime is `timezone.utc`-aware.
- [ ] Every new ISO string on the wire has an offset (`+00:00` or `Z`).
- [ ] New numeric field has an explicit precision rule from the table above (or a comment justifying a new one).
- [ ] No ratio field multiplied by 100 anywhere in `trade/`.
- [ ] Frontend renders time only via `fmt*Cst`; renders money only via `fmtUsd`; renders ratio only at the render boundary.
- [ ] New API field reflected in `tradefrontend/src/types/`.
