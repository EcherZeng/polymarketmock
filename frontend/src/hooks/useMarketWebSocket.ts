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

export interface OrderbookState {
  bids: PriceLevel[]
  asks: PriceLevel[]
  timestamp: string
  hash: string
  lastTradePrice: string
}

interface MarketWsState {
  /** Per-token orderbooks (keyed by asset_id) */
  orderbooks: Record<string, OrderbookState>
  /** Per-token best bid/ask (keyed by asset_id) */
  bestBidAsks: Record<string, WsBestBidAskEvent>
  /** Legacy: first token's orderbook (backward compat) */
  orderbook: OrderbookState | null
  /** Legacy: most recent best_bid_ask event (backward compat) */
  bestBidAsk: WsBestBidAskEvent | null
  lastTrade: WsLastTradeEvent | null
  trades: WsLastTradeEvent[]
  tickSize: string | null
  marketResolved: WsMarketResolvedEvent | null
  connected: boolean
  eventEnded: boolean
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

  const eventEndedRef = useRef(false)

  const [state, setState] = useState<MarketWsState>({
    orderbooks: {},
    bestBidAsks: {},
    orderbook: null,
    bestBidAsk: null,
    lastTrade: null,
    trades: [],
    tickSize: null,
    marketResolved: null,
    connected: false,
    eventEnded: false,
  })

  const tradesRef = useRef<WsLastTradeEvent[]>([])
  const dataCheckRef = useRef<ReturnType<typeof setInterval> | null>(null)
  const gotDataRef = useRef(false)

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

      const newOb: OrderbookState = {
        bids: sortedLevels(bids, true),
        asks: sortedLevels(asks, false),
        timestamp: event.timestamp,
        hash: event.hash,
        lastTradePrice: "",
      }
      setState((prev) => {
        newOb.lastTradePrice = prev.orderbooks[assetId]?.lastTradePrice ?? ""
        return {
          ...prev,
          orderbooks: { ...prev.orderbooks, [assetId]: newOb },
          orderbook: assetId === assetIdsRef.current[0] ? newOb : prev.orderbook,
        }
      })
    },
    [sortedLevels],
  )

  const applyPriceChange = useCallback(
    (changes: WsMarketEvent & { event_type: "price_change" }) => {
      const affectedIds = new Set<string>()
      for (const pc of changes.price_changes) {
        const entry = obMapRef.current.get(pc.asset_id)
        if (!entry) continue

        const map = pc.side === "BUY" ? entry.bids : entry.asks
        if (parseFloat(pc.size) === 0) {
          map.delete(pc.price)
        } else {
          map.set(pc.price, pc.size)
        }
        affectedIds.add(pc.asset_id)
      }

      if (affectedIds.size === 0) return

      setState((prev) => {
        const newObs = { ...prev.orderbooks }
        let newOrderbook = prev.orderbook
        for (const aid of affectedIds) {
          const entry = obMapRef.current.get(aid)
          if (!entry) continue
          const ob: OrderbookState = {
            bids: sortedLevels(entry.bids, true),
            asks: sortedLevels(entry.asks, false),
            timestamp: changes.timestamp,
            hash: newObs[aid]?.hash ?? "",
            lastTradePrice: newObs[aid]?.lastTradePrice ?? "",
          }
          newObs[aid] = ob
          if (aid === assetIdsRef.current[0]) newOrderbook = ob
        }
        return { ...prev, orderbooks: newObs, orderbook: newOrderbook }
      })
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

      // Start data-arrival checker
      gotDataRef.current = false
      if (dataCheckRef.current) clearInterval(dataCheckRef.current)
      dataCheckRef.current = setInterval(() => {
        if (gotDataRef.current) {
          // already logged on first data, just cleanup
          if (dataCheckRef.current) { clearInterval(dataCheckRef.current); dataCheckRef.current = null }
        } else {
          console.log("[WS] 没有数据")
        }
      }, 1_000)

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

      // Log first data arrival then stop checking
      if (!gotDataRef.current) {
        gotDataRef.current = true
        console.log("[WS] 已有数据", data.event_type)
        if (dataCheckRef.current) { clearInterval(dataCheckRef.current); dataCheckRef.current = null }
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
          setState((prev) => {
            const newObs = { ...prev.orderbooks }
            if (newObs[trade.asset_id]) {
              newObs[trade.asset_id] = { ...newObs[trade.asset_id], lastTradePrice: trade.price }
            }
            return {
              ...prev,
              lastTrade: trade,
              trades: tradesRef.current,
              orderbooks: newObs,
              orderbook: prev.orderbook
                ? { ...prev.orderbook, lastTradePrice: trade.price }
                : prev.orderbook,
            }
          })
          break
        }
        case "best_bid_ask": {
          const bba = data as WsBestBidAskEvent
          setState((prev) => ({
            ...prev,
            bestBidAsks: { ...prev.bestBidAsks, [bba.asset_id]: bba },
            bestBidAsk: bba,
          }))
          break
        }
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
        case "event_ended":
          eventEndedRef.current = true
          setState((prev) => ({
            ...prev,
            eventEnded: true,
            connected: false,
          }))
          console.log("[WS] 场次已结束，连接将关闭")
          break
      }
    }

    ws.onclose = (ev) => {
      cleanup()
      if (!mountedRef.current) return
      setState((prev) => ({ ...prev, connected: false }))
      // Server closes with reason="event_ended" — treat same as event_ended msg
      if (ev.reason === "event_ended" || ev.code === 1000) {
        eventEndedRef.current = true
        setState((prev) => ({ ...prev, eventEnded: true }))
      }
      // Don't reconnect if event has ended
      if (eventEndedRef.current) return
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
    if (dataCheckRef.current) {
      clearInterval(dataCheckRef.current)
      dataCheckRef.current = null
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
