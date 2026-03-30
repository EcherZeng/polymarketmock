/* Strategy Backtest Engine — TypeScript types aligned with backend */

export interface StrategyInfo {
  name: string
  description: string
  version: string
  default_config: Record<string, number | string | boolean>
}

export interface ArchiveInfo {
  slug: string
  path: string
  files: string[]
  size_mb: number
  time_range: { start: string; end: string }
  token_ids: string[]
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
  position_curve: PositionPoint[]
  strategy_summary: Record<string, unknown>
}

export interface RunRequest {
  strategy: string
  slug: string
  initial_balance: number
  config: Record<string, unknown>
}

export interface BatchTask {
  batch_id: string
  strategy: string
  slugs: string[]
  status: string
  total: number
  completed: number
  created_at: string
}
