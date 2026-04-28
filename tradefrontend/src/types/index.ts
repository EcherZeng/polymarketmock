// ── Types matching trade backend API responses ──────────────────────────────

export interface HealthResponse {
  status: string
  service: string
}

export type SessionState =
  | "discovered"
  | "preparing"
  | "active"
  | "closing"
  | "settled"
  | "skipped"
  | "error"

export interface SessionSlot {
  slug: string
  state: SessionState
  time_remaining_s: number
  token_ids: string[]
  started: boolean
}

export interface StatusResponse {
  paused: boolean
  current: SessionSlot | null
  next: SessionSlot | null
  uptime_s: number
}

export interface PositionEntry {
  token_id: string
  shares: number
  cost_basis: number
  current_value: number
  unrealised_pnl: number
}

export interface PositionsResponse {
  balance: number
  initial_balance: number
  positions: Record<string, number>
  cost_basis: Record<string, number>
  equity: number
  unrealised_pnl: number
}

export interface BalanceResponse {
  balance: number
  initial_balance: number
}

export interface PnlTotal {
  total_pnl: number
  total_trade_pnl: number
  total_settlement_pnl: number
  total_sessions: number
  winning_sessions: number
  losing_sessions: number
}

export interface PnlRecentItem {
  slug: string
  total_pnl: number
  state: string
}

export interface PnlResponse {
  total: PnlTotal
  recent: PnlRecentItem[]
}

export interface SessionRow {
  slug: string
  token_ids: string
  outcomes: string
  start_epoch: number
  end_epoch: number
  duration_s: number
  state: SessionState
  trade_pnl: number
  settlement_pnl: number
  total_pnl: number
  settlement_outcome: string
  error: string
  created_at: string
  updated_at: string
}

export interface TradeRow {
  id: number
  order_id: string
  session_slug: string
  token_id: string
  side: string
  filled_shares: number
  avg_price: number
  total_cost: number
  fees: number
  timestamp: string
  created_at: string
}

export interface SessionDetailResponse {
  session: SessionRow
  trades: TradeRow[]
}

export interface StrategyInfo {
  name: string
  description: string | { zh: string; en: string }
  version: string
  default_config: Record<string, unknown>
  builtin?: boolean
}

export interface ConfigResponse {
  local_strategies: StrategyInfo[]
  backtest_strategies: StrategyInfo[]
  composite_presets: CompositePreset[]
  current_config: Record<string, unknown>
  composite_config: CompositeConfigInfo | null
  allowed_keys?: Record<string, [number, number]>
  executor_mode?: string
  active_strategy?: string
}

export interface CompositePreset {
  name: string
  description?: string
  btc_windows: { btc_trend_window_1: number; btc_trend_window_2: number }
  branches: CompositeBranch[]
}

export interface CompositeBranch {
  label: string
  min_momentum: number
  preset_name: string
  config?: Record<string, unknown>
}

export interface CompositeConfigInfo {
  composite_name: string
  btc_windows: { btc_trend_window_1: number; btc_trend_window_2: number }
  branches: CompositeBranch[]
}

// ── WebSocket message types ─────────────────────────────────────────────────

export interface WsMessage<T = unknown> {
  type: string
  data: T
  ts?: string
}

export interface BtcPricePoint {
  price: number
  timestamp: string
}

export interface TokenMarket {
  outcome: string
  mid_price: number
  best_bid: number
  best_ask: number
  spread: number
  anchor_price: number
  bid_levels: [number, number][]
  ask_levels: [number, number][]
}

export interface MarketSnapshot {
  slug: string
  tokens: Record<string, TokenMarket>
}

export interface WsSessionStatus {
  running: boolean
  paused: boolean
  ws_connected: boolean
  executor_ready: boolean
  current_session: {
    slug: string
    state: SessionState
    time_remaining_s: number
    trades: number
    has_position: boolean
    btc_trend_computed?: boolean
    btc_trend_passed?: boolean | null
    btc_amplitude?: number | null
    btc_direction?: string | null
    matched_branch?: string | null
    no_trades?: boolean
  } | null
  next_session: {
    slug: string
    state: SessionState
    time_remaining_s: number
    trades: number
    has_position: boolean
  } | null
  settling_count: number
}

export interface PriceSnapshot {
  id: number
  session_slug: string
  token_id: string
  mid_price: number
  best_bid: number
  best_ask: number
  spread: number
  anchor_price: number
  timestamp: string
}
