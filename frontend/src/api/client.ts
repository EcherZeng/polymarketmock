import axios from "axios"
import type {
  AccountOverview,
  EstimateRequest,
  EstimateResult,
  Market,
  MarketEvent,
  Orderbook,
  OrderRequest,
  OrderResult,
  Position,
  PriceHistoryPoint,
  TradeHistoryResponse,
} from "@/types"

const api = axios.create({ baseURL: "/api" })

// ── Market Data ─────────────────────────────────────────────────────────────

export async function fetchMarkets(limit = 20, offset = 0): Promise<Market[]> {
  const { data } = await api.get("/markets", { params: { limit, offset } })
  return data
}

export async function fetchMarket(id: string): Promise<Market> {
  const { data } = await api.get(`/markets/${id}`)
  return data
}

export async function fetchEvents(limit = 20, offset = 0): Promise<MarketEvent[]> {
  const { data } = await api.get("/events", { params: { limit, offset } })
  return data
}

export async function fetchEvent(id: string): Promise<MarketEvent> {
  const { data } = await api.get(`/events/${id}`)
  return data
}

export async function fetchOrderbook(tokenId: string): Promise<Orderbook> {
  const { data } = await api.get("/orderbook", { params: { token_id: tokenId } })
  return data
}

export async function fetchMidpoint(tokenId: string): Promise<{ token_id: string; mid: number }> {
  const { data } = await api.get("/midpoint", { params: { token_id: tokenId } })
  return data
}

export async function searchEvents(
  q: string,
  activeOnly = true,
  limit = 20,
): Promise<MarketEvent[]> {
  const { data } = await api.get("/search/events", {
    params: { q, active_only: activeOnly, limit },
  })
  return data
}

export async function resolveSlug(slug: string): Promise<MarketEvent> {
  const { data } = await api.get(`/resolve/${slug}`)
  return data
}

export async function fetchBtcMarkets(): Promise<Record<string, MarketEvent[]>> {
  const { data } = await api.get("/btc/markets")
  return data
}

export async function fetchPricesHistory(
  tokenId: string,
  interval = "1m",
  fidelity = 60,
): Promise<PriceHistoryPoint[]> {
  const { data } = await api.get("/prices/history", {
    params: { token_id: tokenId, interval, fidelity },
  })
  return data
}

// ── Trading ─────────────────────────────────────────────────────────────────

export async function placeOrder(req: OrderRequest): Promise<OrderResult> {
  const { data } = await api.post("/trading/order", req)
  return data
}

export async function estimateOrder(req: EstimateRequest): Promise<EstimateResult> {
  const { data } = await api.post("/trading/estimate", req)
  return data
}

export async function fetchOrders(): Promise<OrderResult[]> {
  const { data } = await api.get("/trading/orders")
  return data
}

export async function fetchPendingOrders(): Promise<OrderResult[]> {
  const { data } = await api.get("/trading/orders/pending")
  return data
}

export async function cancelOrder(orderId: string): Promise<OrderResult> {
  const { data } = await api.delete(`/trading/orders/${orderId}`)
  return data
}

export async function fetchTradeHistory(
  offset = 0,
  limit = 50,
  tokenId?: string,
): Promise<TradeHistoryResponse> {
  const params: Record<string, unknown> = { offset, limit }
  if (tokenId) params.token_id = tokenId
  const { data } = await api.get("/trading/history", { params })
  return data
}

export async function settleMarket(
  marketId: string,
  winningOutcome: string,
): Promise<unknown> {
  const { data } = await api.post(`/trading/settle/${marketId}`, {
    winning_outcome: winningOutcome,
  })
  return data
}

// ── Account ─────────────────────────────────────────────────────────────────

export async function initAccount(balance: number): Promise<{ status: string; balance: number }> {
  const { data } = await api.post("/account/init", { balance })
  return data
}

export async function fetchAccount(): Promise<AccountOverview> {
  const { data } = await api.get("/account")
  return data
}

export async function fetchPositions(): Promise<Position[]> {
  const { data } = await api.get("/account/positions")
  return data
}

export async function fetchPosition(tokenId: string): Promise<Position> {
  const { data } = await api.get(`/account/positions/${tokenId}`)
  return data
}

// ── Backtest ────────────────────────────────────────────────────────────────

export async function fetchBacktestMarkets(): Promise<unknown[]> {
  const { data } = await api.get("/backtest/markets")
  return data
}

export async function fetchBacktestData(
  marketId: string,
  start?: string,
  end?: string,
): Promise<unknown[]> {
  const { data } = await api.get(`/backtest/data/${marketId}`, {
    params: { start, end },
  })
  return data
}
