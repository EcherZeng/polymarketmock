import { useEffect, useRef, useState, useCallback } from "react"
import type {
  PriceLevel,
  WsBookEvent,
  WsBestBidAskEvent,
  WsLastTradeEvent,
  WsTickSizeChangeEvent,
  WsMarketResolvedEvent,
  WsMarketEvent,
} from "@/types"

interface OrderbookState {
  bids: PriceLevel[]
  asks: PriceLevel[]
  timestamp: string
  hash: string
  lastTradePrice: string
}

interface MarketWsState {
  orderbook: OrderbookState | null
  bestBidAsk: WsBestBidAskEvent | null
  lastTrade: WsLastTradeEvent | null
  trades: WsLastTradeEvent[]
  tickSize: string | null
  marketResolved: WsMarketResolvedEvent | null
  connected: boolean
}

const MAX_TRADES = 100
const PING_INTERVAL = 30_000
const RECONNECT_BASE = 1_000
const RECONNECT_MAX = 30_000

function getWsUrl(): string {
  const proto = window.location.protocol === "https:" ? "wss:" : "ws:"
  return `${proto}//${window.location.host}/ws/market`
}

export default function useMarketWebSocket(assetIds: string[]): MarketWsState {
  const wsRef = useRef<WebSocket | null>(null)
  const pingRef = useRef<ReturnType<typeof setInterval> | null>(null)
  const reconnectRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const backoffRef = useRef(RECONNECT_BASE)
  const mountedRef = useRef(true)
  const assetIdsRef = useRef<string[]>(assetIds)

  // Orderbook maintained via book + price_change events
  const obMapRef = useRef<Map<string, { bids: Map<string, string>; asks: Map<string, string> }> >(new Map())

  const [state, setState] = useState<MarketWsState>({
    orderbook: null,
    bestBidAsk: null,
    lastTrade: null,
    trades: [],
    tickSize: null,
    marketResolved: null,
    connected: false,
  })

  const tradesRef = useRef<WsLastTradeEvent[]>([])

  // ── Orderbook helpers ──────────────────────────────────────

  const sortedLevels = useCallback(
    (map: Map<string, string>, descending: boolean): PriceLevel[] => {
      const arr = Array.from(map.entries()).map(([price, size]) => ({ price, size }))
      arr.sort((a, b) =>
        descending
          ? parseFloat(b.price) - parseFloat(a.price)
          : parseFloat(a.price) - parseFloat(b.price),
      )
      return arr
    },
    [],
  )

  const applyBook = useCallback(
    (assetId: string, event: WsBookEvent) => {
      const bids = new Map<string, string>()
      const asks = new Map<string, string>()
      for (const lv of event.bids) bids.set(lv.price, lv.size)
      for (const lv of event.asks) asks.set(lv.price, lv.size)
      obMapRef.current.set(assetId, { bids, asks })

      setState((prev) => ({
        ...prev,
        orderbook: {
          bids: sortedLevels(bids, true),
          asks: sortedLevels(asks, false),
          timestamp: event.timestamp,
          hash: event.hash,
          lastTradePrice: prev.orderbook?.lastTradePrice ?? "",
        },
      }))
    },
    [sortedLevels],
  )

  const applyPriceChange = useCallback(
    (changes: WsMarketEvent & { event_type: "price_change" }) => {
      for (const pc of changes.price_changes) {
        const entry = obMapRef.current.get(pc.asset_id)
        if (!entry) continue

        const map = pc.side === "BUY" ? entry.bids : entry.asks
        if (parseFloat(pc.size) === 0) {
          map.delete(pc.price)
        } else {
          map.set(pc.price, pc.size)
        }

        // Only update state if this asset is one we're tracking (first in list)
        if (pc.asset_id === assetIdsRef.current[0]) {
          setState((prev) => ({
            ...prev,
            orderbook: {
              bids: sortedLevels(entry.bids, true),
              asks: sortedLevels(entry.asks, false),
              timestamp: changes.timestamp,
              hash: prev.orderbook?.hash ?? "",
              lastTradePrice: prev.orderbook?.lastTradePrice ?? "",
            },
          }))
        }
      }
    },
    [sortedLevels],
  )

  // ── WebSocket connection ───────────────────────────────────

  const connect = useCallback(() => {
    if (!mountedRef.current || assetIdsRef.current.length === 0) return

    const ws = new WebSocket(getWsUrl())
    wsRef.current = ws

    ws.onopen = () => {
      if (!mountedRef.current) return
      backoffRef.current = RECONNECT_BASE
      setState((prev) => ({ ...prev, connected: true }))

      // Subscribe
      ws.send(JSON.stringify({ type: "subscribe", asset_ids: assetIdsRef.current }))

      // Start ping
      pingRef.current = setInterval(() => {
        if (ws.readyState === WebSocket.OPEN) ws.send("PING")
      }, PING_INTERVAL)
    }

    ws.onmessage = (ev) => {
      if (!mountedRef.current) return
      const text = typeof ev.data === "string" ? ev.data : ""
      if (text === "PONG") return

      let data: WsMarketEvent
      try {
        data = JSON.parse(text)
      } catch {
        return
      }

      switch (data.event_type) {
        case "book":
          applyBook(data.asset_id, data)
          break
        case "price_change":
          applyPriceChange(data)
          break
        case "last_trade_price": {
          const trade = data as WsLastTradeEvent
          tradesRef.current = [trade, ...tradesRef.current].slice(0, MAX_TRADES)
          setState((prev) => ({
            ...prev,
            lastTrade: trade,
            trades: tradesRef.current,
            orderbook: prev.orderbook
              ? { ...prev.orderbook, lastTradePrice: trade.price }
              : prev.orderbook,
          }))
          break
        }
        case "best_bid_ask":
          setState((prev) => ({ ...prev, bestBidAsk: data as WsBestBidAskEvent }))
          break
        case "tick_size_change":
          setState((prev) => ({
            ...prev,
            tickSize: (data as WsTickSizeChangeEvent).new_tick_size,
          }))
          break
        case "market_resolved":
          setState((prev) => ({
            ...prev,
            marketResolved: data as WsMarketResolvedEvent,
          }))
          break
      }
    }

    ws.onclose = () => {
      cleanup()
      if (!mountedRef.current) return
      setState((prev) => ({ ...prev, connected: false }))
      // Reconnect with backoff
      const delay = backoffRef.current
      backoffRef.current = Math.min(delay * 2, RECONNECT_MAX)
      reconnectRef.current = setTimeout(connect, delay)
    }

    ws.onerror = () => {
      // onclose will fire after onerror
    }
  }, [applyBook, applyPriceChange])

  const cleanup = useCallback(() => {
    if (pingRef.current) {
      clearInterval(pingRef.current)
      pingRef.current = null
    }
  }, [])

  // ── Effect: connect/disconnect on assetIds change ──────────

  useEffect(() => {
    mountedRef.current = true
    assetIdsRef.current = assetIds

    // If already connected, update subscription dynamically
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(
        JSON.stringify({ type: "subscribe", asset_ids: assetIds }),
      )
      return
    }

    // Fresh connect
    connect()

    return () => {
      mountedRef.current = false
      cleanup()
      if (reconnectRef.current) {
        clearTimeout(reconnectRef.current)
        reconnectRef.current = null
      }
      if (wsRef.current) {
        wsRef.current.onclose = null // prevent reconnect
        wsRef.current.close()
        wsRef.current = null
      }
    }
  }, [assetIds.join(",")]) // eslint-disable-line react-hooks/exhaustive-deps

  return state
}
