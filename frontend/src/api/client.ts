import axios from "axios"
import type {
  AccountOverview,
  ArchivedEvent,
  EstimateRequest,
  EstimateResult,
  EventStatusResponse,
  Market,
  MarketEvent,
  NextEventResponse,
  Orderbook,
  OrderRequest,
  OrderResult,
  PolymarketTradesResponse,
  Position,
  PriceHistoryPoint,
  RealtimeTradesResponse,
  ReplaySession,
  ReplaySnapshot,
  ReplayTimeline,
  ReplayTradeResult,
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

// ── Realtime Trade Feed ─────────────────────────────────────────────────────

export async function fetchRealtimeTrades(
  tokenId: string,
  limit = 30,
  since = 0,
): Promise<RealtimeTradesResponse> {
  const { data } = await api.get("/trades/realtime", {
    params: { token_id: tokenId, limit, since },
  })
  return data
}

export async function fetchLiveTrades(
  marketId: string,
  limit = 30,
  offset = 0,
): Promise<PolymarketTradesResponse> {
  const { data } = await api.get("/trades/live", {
    params: { market_id: marketId, limit, offset },
  })
  return data
}

// ── Event Lifecycle ─────────────────────────────────────────────────────────

export async function fetchEventStatus(slug: string): Promise<EventStatusResponse> {
  const { data } = await api.get(`/event/status/${slug}`)
  return data
}

export async function fetchNextEvent(slug: string): Promise<NextEventResponse> {
  const { data } = await api.get(`/event/next/${slug}`)
  return data
}

// ── Archives ────────────────────────────────────────────────────────────────

export async function fetchArchives(): Promise<ArchivedEvent[]> {
  const { data } = await api.get("/archives")
  return data
}

export async function fetchArchive(slug: string): Promise<ArchivedEvent> {
  const { data } = await api.get(`/archives/${slug}`)
  return data
}

// ── Watch / Recording ────────────────────────────────────────────────────────

export async function watchEvent(
  slug: string,
): Promise<{ watched_tokens: string[]; recording_started: boolean }> {
  const { data } = await api.post(`/watch/event/${slug}`)
  return data
}

export async function getWatchedMarkets(): Promise<{ watched: Record<string, string> }> {
  const { data } = await api.get("/watched")
  return data
}

// ── Replay ──────────────────────────────────────────────────────────────────

export async function fetchReplayTimeline(slug: string): Promise<ReplayTimeline> {
  const { data } = await api.get(`/backtest/replay/${slug}/timeline`)
  return data
}

export async function fetchReplaySnapshot(
  slug: string,
  timestamp: string,
): Promise<ReplaySnapshot> {
  const { data } = await api.get(`/backtest/replay/${slug}/snapshot`, {
    params: { t: timestamp },
  })
  return data
}

export async function createReplaySession(
  slug: string,
  initialBalance = 10000,
): Promise<ReplaySession> {
  const { data } = await api.post(`/backtest/replay/${slug}/session`, {
    initial_balance: initialBalance,
  })
  return data
}

export async function executeReplayTrade(
  slug: string,
  sessionId: string,
  timestamp: string,
  tokenId: string,
  side: string,
  amount: number,
): Promise<ReplayTradeResult> {
  const { data } = await api.post(`/backtest/replay/${slug}/trade`, {
    session_id: sessionId,
    timestamp,
    token_id: tokenId,
    side,
    amount,
  })
  return data
}
