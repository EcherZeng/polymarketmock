/* Strategy Backtest Engine — TypeScript types aligned with backend */

// ── i18n label ──────────────────────────────────────────────────────────────

export interface I18nLabel {
  zh: string
  en: string
}

// ── Param Schema (from strategy_presets.json) ───────────────────────────────

export interface ParamSchemaItem {
  group: string
  visibility?: "core" | "advanced"
  label: I18nLabel
  /** What this parameter does and how it affects the strategy */
  desc?: I18nLabel
  type: "float" | "int" | "bool"
  min?: number
  max?: number
  step?: number
  unit?: string
  scope: "unified" | "strategy"
  depends_on?: string
  /** The value to set when you want this parameter to have no effect on calculations. null means use the corresponding toggle instead. */
  disable_value?: number | null
  /** Human-readable explanation of what disable_value achieves */
  disable_note?: I18nLabel
}

export interface ParamGroupDef {
  zh: string
  en: string
  order: number
}

export interface PresetsResponse {
  unified_rules: Record<string, number>
  strategies: Record<string, StrategyPreset>
  param_schema: Record<string, ParamSchemaItem>
  param_groups: Record<string, ParamGroupDef>
}

export interface StrategyPreset {
  builtin?: boolean
  description?: I18nLabel | string
  [key: string]: unknown
}

// ── Strategy ────────────────────────────────────────────────────────────────

export interface StrategyInfo {
  name: string
  description: I18nLabel | string
  version: string
  default_config: Record<string, number | string | boolean>
  builtin?: boolean
}

export interface ArchiveInfo {
  slug: string
  path: string
  files: string[]
  size_mb: number
  time_range: { start: string; end: string }
  token_ids: string[]
  prices_count: number
  orderbooks_count: number
  live_trades_count: number
  source: "archive" | "live"
}

export interface EvaluationMetrics {
  total_pnl: number
  total_return_pct: number
  annualized_return: number
  profit_factor: number
  max_drawdown: number
  max_drawdown_duration: number
  volatility: number
  downside_deviation: number
  sharpe_ratio: number
  sortino_ratio: number
  calmar_ratio: number
  total_trades: number
  win_rate: number
  avg_win: number
  avg_loss: number
  best_trade: number
  worst_trade: number
  avg_holding_period: number
  buy_count: number
  sell_count: number
  avg_slippage: number
  // BTC prediction market metrics
  settlement_pnl: number
  trade_pnl: number
  hold_to_settlement_ratio: number
  avg_entry_price: number
  expected_value: number
}

export interface TradeRecord {
  timestamp: string
  token_id: string
  side: "BUY" | "SELL"
  requested_amount: number
  filled_amount: number
  avg_price: number
  total_cost: number
  slippage_pct: number
  balance_after: number
  position_after: number
}

export interface EquityPoint {
  timestamp: string
  equity: number
  balance: number
  positions_value: number
}

export interface DrawdownPoint {
  timestamp: string
  drawdown_pct: number
}

export interface DrawdownEvent {
  start_time: string
  trough_time: string
  recovery_time: string | null
  peak_equity: number
  trough_equity: number
  drawdown_pct: number
  duration_seconds: number
  recovery_seconds: number | null
}

export interface PositionPoint {
  timestamp: string
  token_id: string
  quantity: number
}

export interface BacktestResultSummary {
  session_id: string
  strategy: string
  slug: string
  initial_balance: number
  final_equity: number
  status: string
  created_at: string
  duration_seconds: number
  metrics: EvaluationMetrics
}

export interface PricePoint {
  timestamp: string
  token_id: string
  mid_price: number
  anchor_price?: number
  anchor_source?: "mid" | "micro" | "last_trade" | "none"
  best_bid?: number
  best_ask?: number
  spread?: number
  last_trade_price?: number
}

export interface BacktestResult extends BacktestResultSummary {
  config: Record<string, unknown>
  summary: {
    total_ticks: number
    buy_count: number
    sell_count: number
  }
  trades: TradeRecord[]
  equity_curve: EquityPoint[]
  drawdown_curve: DrawdownPoint[]
  drawdown_events: DrawdownEvent[]
  position_curve: PositionPoint[]
  price_curve: PricePoint[]
  strategy_summary: Record<string, unknown>
  settlement_result: Record<string, number>
}

export interface RunRequest {
  strategy: string
  slug: string
  initial_balance: number
  config: Record<string, unknown>
  settlement_result?: Record<string, number>
}

export interface BatchRequest {
  strategy: string
  slugs: string[]
  initial_balance: number
  config: Record<string, unknown>
  settlement_result?: Record<string, number>
  cumulative_capital?: boolean
}

// ── BTC Kline (Binance) ────────────────────────────────────────────────────

export interface BtcKline {
  open_time: number
  open: number
  high: number
  low: number
  close: number
  volume: number
  close_time: number
  quote_volume: number
  trades: number
}

export interface BtcKlineResponse {
  symbol: string
  interval: string
  start_time: string
  end_time: string
  klines: BtcKline[]
}

export interface BatchTask {
  batch_id: string
  strategy: string
  slugs: string[]
  config: Record<string, unknown>
  status: string
  total: number
  completed: number
  created_at: string
}

export interface BatchResultSummary {
  session_id: string
  status: string
  initial_balance: number
  final_equity: number
  total_return_pct: number
  sharpe_ratio: number
  total_trades: number
  win_rate: number
  max_drawdown: number
  avg_slippage: number
  profit_factor: number
}

export interface StepLog {
  timestamp: string
  step: string // "data_load" | "strategy_init" | "tick_loop" | "evaluate" | "done" | "error" | "cancelled"
  status: string // "ok" | "fail" | "skip"
  message: string
  detail: string
  duration_ms: number
}

export interface SlugWorkflow {
  slug: string
  status: string // "pending" | "running" | "completed" | "failed" | "skipped"
  error: string
  steps: StepLog[]
}

export interface CapitalChainEntry {
  slug: string
  start_balance: number
  end_balance: number | null
  status: string
}

export interface BatchTaskDetail extends BatchTask {
  cumulative_capital: boolean
  capital_chain: CapitalChainEntry[]
  results: Record<string, BatchResultSummary>
  errors: Record<string, string>
  persist_errors: string[]
  workflows: Record<string, SlugWorkflow>
}

// ── Portfolios (data-source combinations) ──────────────────────────────────

export interface PortfolioItem {
  session_id: string
  strategy: string
  slug: string
  total_return_pct: number
  sharpe_ratio: number
  win_rate: number
  max_drawdown: number
  profit_factor: number
  total_trades: number
  avg_slippage: number
  initial_balance: number
  final_equity: number
  config: Record<string, unknown>
}

export interface Portfolio {
  portfolio_id: string
  name: string
  created_at: string
  updated_at: string
  items: PortfolioItem[]
  is_strategy_group: boolean
  group_strategy: string | null
  group_config: Record<string, unknown> | null
}

// ── AI Optimize ─────────────────────────────────────────────────────────────

export interface AiOptimizeRequest {
  strategy: string
  slugs: string[]
  base_config: Record<string, unknown>
  optimize_target: string
  max_rounds: number
  runs_per_round: number
  initial_balance: number
  param_keys?: string[]
  active_params?: string[]
  settlement_result?: Record<string, number>
  llm_model: string
}

export interface AiModelsResponse {
  models: string[]
  default_model: string
  api_key_configured: boolean
}

export interface AiOptimizeTask {
  task_id: string
  strategy: string
  slugs: string[]
  status: string
  optimize_target: string
  max_rounds: number
  current_round: number
  completed_runs: number
  total_runs: number
  best_metric: number | null
  best_total_trades: number
  created_at: string
}

export interface AiOptimizeConfigResult {
  config_index: number
  config: Record<string, unknown>
  slug_count: number
  avg_metrics: Record<string, number>
  slug_metrics: AiOptimizeSlugMetric[]
}

export interface AiOptimizeSlugMetric {
  slug: string
  session_id: string
  total_return_pct: number
  sharpe_ratio: number
  win_rate: number
  max_drawdown: number
  total_trades: number
}

export interface AiOptimizeRound {
  round: number
  configs_count: number
  runs_completed: number
  best_metric_value: number
  ai_reasoning: string
  duration_ms: number
  configs_results: AiOptimizeConfigResult[]
}

export interface AiOptimizeError {
  round: number
  phase: string
  message: string
  detail: string
  timestamp: string
  config_index?: number
  slug?: string
}

export interface AiOptimizeTaskDetail extends AiOptimizeTask {
  error: string
  errors: AiOptimizeError[]
  persist_errors: string[]
  best_config: Record<string, unknown>
  best_session_id: string
  market_profiles: Record<string, unknown>
  rounds: AiOptimizeRound[]
  ai_messages: Array<{
    round: number
    role: string
    content_length: number
    content?: string
    timestamp: string
  }>
}
