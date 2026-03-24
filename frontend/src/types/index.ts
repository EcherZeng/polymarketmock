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
