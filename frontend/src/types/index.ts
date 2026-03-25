// Types aligned with backend Pydantic models

export interface PriceLevel {
  price: string
  size: string
}

export interface Orderbook {
  market: string
  asset_id: string
  timestamp: string
  bids: PriceLevel[]
  asks: PriceLevel[]
  min_order_size: string
  tick_size: string
  neg_risk: boolean
  last_trade_price: string
}

export interface Market {
  id: string
  question: string
  conditionId: string
  slug: string
  active: boolean
  closed: boolean
  outcomes: string[]
  outcomePrices: string[]
  liquidity: number
  volume: number
  volume24hr: number
  lastTradePrice: number
  bestBid: number
  bestAsk: number
  spread: number
  clobTokenIds: string
  orderPriceMinTickSize: number
  orderMinSize: number
  negRisk: boolean
  acceptingOrders: boolean
  enableOrderBook: boolean
  description: string
  endDate: string
  startDate: string
  fee: string
  makerBaseFee: number
  takerBaseFee: number
}

export interface MarketEvent {
  id: string
  title: string
  slug: string
  description: string
  active: boolean
  closed: boolean
  category: string
  markets: Market[]
  liquidity: number
  volume: number
  startDate: string
  endDate: string
  _status?: "live" | "upcoming" | "ended" | "unknown"
}

export type OrderSide = "BUY" | "SELL"
export type OrderType = "MARKET" | "LIMIT"
export type OrderStatus = "PENDING" | "FILLED" | "PARTIALLY_FILLED" | "CANCELLED"

export interface OrderRequest {
  token_id: string
  side: OrderSide
  type: OrderType
  amount: number
  price?: number
}

export interface EstimateRequest {
  token_id: string
  side: OrderSide
  type: OrderType
  amount: number
  price?: number
}

export interface OrderResult {
  order_id: string
  token_id: string
  side: OrderSide
  type: OrderType
  status: OrderStatus
  requested_amount: number
  filled_amount: number
  avg_price: number
  total_cost: number
  slippage_pct: number
  created_at: string
  filled_at: string | null
}

export interface EstimateResult {
  token_id: string
  side: OrderSide
  estimated_avg_price: number
  estimated_slippage_pct: number
  estimated_total_cost: number
  orderbook_depth_available: number
  probability_price: number
  potential_profit_per_share: number
  potential_loss_per_share: number
  complementary_price: number
  complementary_token_id: string
}

export interface Position {
  token_id: string
  market_question: string
  outcome: string
  side: OrderSide
  shares: number
  avg_cost: number
  current_price: number
  unrealized_pnl: number
  market_value: number
}

export interface AccountOverview {
  balance: number
  initial_balance: number
  total_positions_value: number
  total_unrealized_pnl: number
  total_realized_pnl: number
  total_pnl: number
  positions: Position[]
}

export interface TradeRecord {
  order_id: string
  token_id: string
  side: OrderSide
  type: OrderType
  amount: number
  avg_price: number
  total_cost: number
  slippage_pct: number
  timestamp: string
}

export interface TradeHistoryResponse {
  trades: TradeRecord[]
  total: number
  offset: number
  limit: number
}

export interface PriceHistoryPoint {
  t: number
  p: number
  [key: string]: unknown
}

// ── Realtime trade (inferred from orderbook diffs) ──────────────────────────

export interface RealtimeTrade {
  timestamp: string
  token_id: string
  side: string
  price: number
  size: number
  inferred: boolean
}

export interface RealtimeTradesResponse {
  trades: RealtimeTrade[]
  count: number
}

// ── Polymarket Data API trades (real on-chain) ───────────────────────────

export interface PolymarketTrade {
  proxyWallet: string
  side: string
  asset: string
  conditionId: string
  size: number
  price: number
  timestamp: number
  title: string
  slug: string
  icon: string
  eventSlug: string
  outcome: string
  outcomeIndex: number
  name: string
  pseudonym: string
  transactionHash: string
}

export interface PolymarketTradesResponse {
  trades: PolymarketTrade[]
  count: number
}

// ── Event status ────────────────────────────────────────────────────────────

export interface EventStatusResponse {
  slug: string
  status: "upcoming" | "live" | "ended" | "settled" | "unknown"
  ended_at: string | null
  seconds_remaining: number | null
}

export interface NextEventResponse {
  slug: string
  event: MarketEvent
  status: string
}

// ── Archives ────────────────────────────────────────────────────────────────

export interface ArchivedEvent {
  slug: string
  title: string
  market_id: string
  start_time: string
  end_time: string
  token_ids: string[]
  prices_count: number
  orderbooks_count: number
  trades_count: number
  archived_at: string
}

// ── Replay ──────────────────────────────────────────────────────────────────

export interface ReplayTimeline {
  slug: string
  start_time: string
  end_time: string
  total_snapshots: number
  total_trades: number
  price_range: { min: number; max: number }
  timestamps: string[]
}

export interface ReplaySnapshotTrade {
  timestamp: string
  token_id: string
  side: string
  price: number
  size: number
}

export interface ReplaySnapshot {
  timestamp: string
  mid_price: number
  best_bid: number
  best_ask: number
  spread: number
  bid_prices: string[]
  bid_sizes: string[]
  ask_prices: string[]
  ask_sizes: string[]
  trades: ReplaySnapshotTrade[]
}

export interface ReplaySession {
  session_id: string
  slug: string
  initial_balance: number
  balance: number
  positions: Record<string, { shares: number; avg_cost: number; side: string }>
  trades: ReplayTradeResult[]
}

export interface ReplayTradeResult {
  timestamp: string
  token_id: string
  side: string
  amount: number
  avg_price: number
  total_cost: number
  slippage_pct: number
  balance_after: number
}
