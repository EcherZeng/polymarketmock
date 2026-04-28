import { useEffect, useRef, useCallback, useState } from "react"
import type {
  WsMessage,
  BtcPricePoint,
  MarketSnapshot,
  WsSessionStatus,
  WsPortfolio,
  WsPnlData,
  TradeRow,
} from "@/types"

const MAX_BTC_POINTS = 900

interface UseLiveWsReturn {
  connected: boolean
  session: WsSessionStatus | null
  portfolio: WsPortfolio | null
  pnl: WsPnlData | null
  btcPrices: BtcPricePoint[]
  market: MarketSnapshot | null
  /** Up token price series — [{timestamp, mid_price, best_bid, best_ask}] */
  upPrices: { timestamp: string; mid: number; bid: number; ask: number }[]
  /** Down token price series */
  downPrices: { timestamp: string; mid: number; bid: number; ask: number }[]
  trades: TradeRow[]
}

export function useLiveWs(): UseLiveWsReturn {
  const wsRef = useRef<WebSocket | null>(null)
  const reconnectTimer = useRef<ReturnType<typeof setTimeout>>(undefined)
  // Track current session slug to detect rotation
  const currentSlugRef = useRef<string | null>(null)

  const [connected, setConnected] = useState(false)
  const [session, setSession] = useState<WsSessionStatus | null>(null)
  const [portfolio, setPortfolio] = useState<WsPortfolio | null>(null)
  const [pnl, setPnl] = useState<WsPnlData | null>(null)
  const [btcPrices, setBtcPrices] = useState<BtcPricePoint[]>([])
  const [market, setMarket] = useState<MarketSnapshot | null>(null)
  const [upPrices, setUpPrices] = useState<{ timestamp: string; mid: number; bid: number; ask: number }[]>([])
  const [downPrices, setDownPrices] = useState<{ timestamp: string; mid: number; bid: number; ask: number }[]>([])
  const [trades, setTrades] = useState<TradeRow[]>([])

  const handleMessage = useCallback((evt: MessageEvent) => {
    try {
      const msg: WsMessage = JSON.parse(evt.data)
      const ts = msg.ts || new Date().toISOString()

      switch (msg.type) {
        case "session": {
          const status = msg.data as WsSessionStatus
          // Detect session rotation: slug changed → clear all session-scoped data
          const newSlug = status.current_session?.slug ?? null
          if (currentSlugRef.current && newSlug && newSlug !== currentSlugRef.current) {
            setBtcPrices([])
            setUpPrices([])
            setDownPrices([])
            setTrades([])
            setMarket(null)
          }
          currentSlugRef.current = newSlug
          setSession(status)
          // Extract portfolio from session event
          if (status.portfolio) {
            setPortfolio(status.portfolio)
          }
          break
        }

        case "pnl": {
          setPnl(msg.data as WsPnlData)
          break
        }

        case "btc_price": {
          const pt = msg.data as BtcPricePoint
          setBtcPrices((prev) => {
            const next = [...prev, pt]
            return next.length > MAX_BTC_POINTS ? next.slice(-MAX_BTC_POINTS) : next
          })
          break
        }

        case "btc_history": {
          const history = msg.data as BtcPricePoint[]
          setBtcPrices(history.slice(-MAX_BTC_POINTS))
          break
        }

        case "market": {
          const snap = msg.data as MarketSnapshot
          setMarket(snap)
          // Extract up/down price series from token data
          const tokens = Object.values(snap.tokens)
          for (const t of tokens) {
            const point = { timestamp: ts, mid: t.mid_price, bid: t.best_bid, ask: t.best_ask }
            if (t.outcome === "Up") {
              setUpPrices((prev) => [...prev, point])
            } else if (t.outcome === "Down") {
              setDownPrices((prev) => [...prev, point])
            }
          }
          break
        }

        case "trade": {
          const trade = msg.data as TradeRow
          setTrades((prev) => [trade, ...prev].slice(0, 50))
          break
        }

        case "trades": {
          const list = msg.data as TradeRow[]
          setTrades(list)
          break
        }

        case "price_history": {
          // Initial price history from snapshots — build up/down series
          const _snapshots = msg.data as Array<{
            token_id: string; mid_price: number; best_bid: number; best_ask: number; timestamp: string
          }>
          // Group by outcome (need slug context from session to map token to outcome)
          // For now store raw; the page can map via market snapshot
          break
        }

        case "poly_price_history": {
          // Session-scoped Poly Up/Down price history cache (like btc_history)
          // Data format: { token_id: [{mid, bid, ask, anchor, outcome, timestamp}, ...] }
          const historyMap = msg.data as Record<string, Array<{
            mid: number; bid: number; ask: number; anchor: number; outcome: string; timestamp: string
          }>>
          const upPoints: { timestamp: string; mid: number; bid: number; ask: number }[] = []
          const downPoints: { timestamp: string; mid: number; bid: number; ask: number }[] = []
          for (const points of Object.values(historyMap)) {
            for (const pt of points) {
              const mapped = { timestamp: pt.timestamp, mid: pt.mid, bid: pt.bid, ask: pt.ask }
              if (pt.outcome === "Up") {
                upPoints.push(mapped)
              } else if (pt.outcome === "Down") {
                downPoints.push(mapped)
              }
            }
          }
          if (upPoints.length > 0) setUpPrices(upPoints)
          if (downPoints.length > 0) setDownPrices(downPoints)
          break
        }

        case "ping":
          // Server keepalive, no action needed
          break
      }
    } catch {
      // Ignore malformed messages
    }
  }, [])

  const connect = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) return

    const proto = window.location.protocol === "https:" ? "wss:" : "ws:"
    const url = `${proto}//${window.location.host}/trade-api/ws/live`
    const ws = new WebSocket(url)

    ws.onopen = () => {
      setConnected(true)
    }

    ws.onclose = () => {
      setConnected(false)
      wsRef.current = null
      // Reconnect after 2s
      reconnectTimer.current = setTimeout(connect, 2000)
    }

    ws.onerror = () => {
      ws.close()
    }

    ws.onmessage = handleMessage
    wsRef.current = ws
  }, [handleMessage])

  useEffect(() => {
    connect()
    return () => {
      clearTimeout(reconnectTimer.current)
      wsRef.current?.close()
    }
  }, [connect])

  return { connected, session, portfolio, pnl, btcPrices, market, upPrices, downPrices, trades }
}
