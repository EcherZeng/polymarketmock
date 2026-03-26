import { useState, useEffect, useCallback, useRef, useMemo } from "react"
import { useParams, Link, useNavigate } from "react-router-dom"
import { useQuery } from "@tanstack/react-query"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"
import { Separator } from "@/components/ui/separator"
import { Alert, AlertDescription } from "@/components/ui/alert"
import PolymarketEmbed from "@/components/PolymarketEmbed"
import EventMarketCard from "@/components/EventMarketCard"
import MarketInfo from "@/components/MarketInfo"
import OrderbookView from "@/components/OrderbookView"
import PriceChart from "@/components/PriceChart"
import TradingPanel from "@/components/TradingPanel"
import PositionTable from "@/components/PositionTable"
import ActivityFeed from "@/components/ActivityFeed"
import useMarketWebSocket from "@/hooks/useMarketWebSocket"
import { resolveSlug, fetchEventStatus, fetchNextEvent, watchEvent } from "@/api/client"
import type { Market, MarketEvent, EventStatusResponse, NextEventResponse } from "@/types"

function parseTokenIds(raw: unknown): string[] {
  if (Array.isArray(raw)) return raw.filter(Boolean)
  if (typeof raw === "string") {
    try {
      const parsed = JSON.parse(raw)
      if (Array.isArray(parsed)) return parsed.filter(Boolean)
    } catch { /* not JSON */ }
    return raw.split(",").map((t) => t.trim()).filter(Boolean)
  }
  return []
}

function parseOutcomes(raw: unknown): string[] {
  if (Array.isArray(raw)) return raw
  if (typeof raw === "string") {
    try { return JSON.parse(raw) } catch { return [] }
  }
  return []
}

export default function EventDetailPage() {
  const { slug } = useParams<{ slug: string }>()
  const navigate = useNavigate()
  const [selectedMarket, setSelectedMarket] = useState<Market | null>(null)
  const [selectedTokenId, setSelectedTokenId] = useState("")

  const { data: event, isLoading, error } = useQuery<MarketEvent>({
    queryKey: ["event", slug],
    queryFn: () => resolveSlug(slug!),
    enabled: !!slug,
    staleTime: 30_000,
  })

  // ── Event lifecycle polling ───────────────────────────────
  const { data: eventStatus } = useQuery<EventStatusResponse>({
    queryKey: ["eventStatus", slug],
    queryFn: () => fetchEventStatus(slug!),
    enabled: !!slug,
    refetchInterval: 5_000,
  })

  const isEnded = eventStatus?.status === "ended" || eventStatus?.status === "settled"

  // ── Auto-record: watch event when LIVE ─────────────
  const [isRecording, setIsRecording] = useState(false)
  const watchedRef = useRef(false)

  useEffect(() => {
    if (!slug || !event || isEnded || watchedRef.current) return
    if (eventStatus?.status !== "live") return
    watchedRef.current = true
    watchEvent(slug)
      .then(() => setIsRecording(true))
      .catch(() => { /* non-critical */ })
  }, [slug, event?.id, eventStatus?.status])

  // ── Client-side countdown (synced from server every 5s) ────
  const [countdown, setCountdown] = useState<number | null>(null)
  const countdownRef = useRef<number | null>(null)

  // Sync from server
  useEffect(() => {
    if (eventStatus?.seconds_remaining != null && eventStatus.seconds_remaining > 0) {
      setCountdown(Math.floor(eventStatus.seconds_remaining))
      countdownRef.current = Math.floor(eventStatus.seconds_remaining)
    } else {
      setCountdown(null)
      countdownRef.current = null
    }
  }, [eventStatus?.seconds_remaining])

  // Tick every second
  useEffect(() => {
    const id = window.setInterval(() => {
      setCountdown((prev) => {
        if (prev == null || prev <= 0) return null
        const next = prev - 1
        countdownRef.current = next
        return next
      })
    }, 1_000)
    return () => window.clearInterval(id)
  }, [])

  const { data: nextEvent } = useQuery<NextEventResponse>({
    queryKey: ["nextEvent", slug],
    queryFn: () => fetchNextEvent(slug!),
    enabled: !!slug && isEnded,
    staleTime: 10_000,
  })

  // Auto-select first market when event loads
  useEffect(() => {
    if (event?.markets?.[0] && !selectedMarket) {
      const m = event.markets[0]
      setSelectedMarket(m)
      const tokens = parseTokenIds(m.clobTokenIds)
      if (tokens[0]) {
        setSelectedTokenId(tokens[0])
      }
    }
  }, [event?.id])

  // Reset selection when slug changes (navigation to next event)
  useEffect(() => {
    setSelectedMarket(null)
    setSelectedTokenId("")
  }, [slug])

  function handleSelectMarket(m: Market) {
    setSelectedMarket(m)
    const tokens = parseTokenIds(m.clobTokenIds)
    if (tokens[0]) {
      setSelectedTokenId(tokens[0])
    }
  }

  const handleSwitchToken = useCallback(
    (tokenId: string) => {
      if (!selectedMarket) return
      const tokens = parseTokenIds(selectedMarket.clobTokenIds)
      const idx = tokens.indexOf(tokenId)
      if (idx >= 0) {
        setSelectedTokenId(tokenId)
      }
    },
    [selectedMarket],
  )

  // ── Derived values (must be before early returns for hooks below) ──
  const tokens = selectedMarket ? parseTokenIds(selectedMarket.clobTokenIds) : []
  const outcomes = selectedMarket ? parseOutcomes(selectedMarket.outcomes) : []

  // ── WebSocket real-time data ──────────────────────────────
  const wsAssetIds = useMemo(() => tokens.filter(Boolean), [tokens.join(",")])
  const ws = useMarketWebSocket(wsAssetIds)

  if (isLoading) {
    return (
      <div className="flex flex-col gap-4">
        <Skeleton className="h-8 w-64" />
        <Skeleton className="h-[300px] w-full rounded-lg" />
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-12">
          <div className="flex flex-col gap-4 lg:col-span-8">
            <Skeleton className="h-24 rounded-lg" />
            <Skeleton className="h-24 rounded-lg" />
          </div>
          <div className="flex flex-col gap-4 lg:col-span-4">
            <Skeleton className="h-48 rounded-lg" />
          </div>
        </div>
      </div>
    )
  }

  if (error || !event) {
    return (
      <div className="flex flex-col items-center gap-4 py-12">
        <p className="text-muted-foreground">
          {error ? "Failed to load event" : "Event not found"}
        </p>
        <Button variant="outline" asChild>
          <Link to="/">Back to Events</Link>
        </Button>
      </div>
    )
  }

  return (
    <div className="flex flex-col gap-4">
      {/* ── Ended event banner ───────────────────────────────── */}
      {isEnded && (
        <Alert className="border-rose-500/50 bg-rose-500/5">
          <AlertDescription className="flex items-center justify-between">
            <span className="text-sm font-medium">
              🏁 本场已结束
              {eventStatus?.ended_at && (
                <span className="ml-2 text-muted-foreground text-xs">
                  {new Date(eventStatus.ended_at).toLocaleString("zh-CN")}
                </span>
              )}
            </span>
            <div className="flex items-center gap-2">
              <Button variant="outline" size="sm" asChild>
                <Link to={`/replay/${slug}`}>回放此场次</Link>
              </Button>
              {nextEvent?.slug && (
                <Button
                  size="sm"
                  className="animate-pulse bg-emerald-600 hover:bg-emerald-700"
                  onClick={() => navigate(`/event/${nextEvent.slug}`)}
                >
                  跳转到最新场次 →
                </Button>
              )}
            </div>
          </AlertDescription>
        </Alert>
      )}

      {/* ── Event Header ─────────────────────────────────────── */}
      <div className="flex flex-col gap-1">
        <div className="flex items-center gap-2">
          <Button variant="ghost" size="sm" asChild className="px-2">
            <Link to="/">← Events</Link>
          </Button>
        </div>
        <div className="flex items-start justify-between gap-2">
          <h1 className="text-xl font-semibold leading-tight">{event.title}</h1>
          <div className="flex shrink-0 gap-1">
            {isRecording && (
              <Badge variant="destructive" className="animate-pulse gap-1">
                <span className="inline-block h-2 w-2 rounded-full bg-white" />
                录制中
              </Badge>
            )}
            {isEnded ? (
              <Badge variant="secondary">已结束</Badge>
            ) : eventStatus?.status === "live" ? (
              <Badge variant="default">LIVE</Badge>
            ) : eventStatus?.status === "upcoming" ? (
              <Badge variant="outline">即将开始</Badge>
            ) : event.active && !event.closed ? (
              <Badge variant="default">Active</Badge>
            ) : (
              <Badge variant="secondary">Closed</Badge>
            )}
            {countdown != null && countdown > 0 && (
              <Badge variant="outline" className="tabular-nums">
                {Math.floor(countdown / 60)}:
                {String(countdown % 60).padStart(2, "0")}
              </Badge>
            )}
          </div>
        </div>
        {event.description && (
          <p className="text-sm text-muted-foreground line-clamp-2">
            {event.description}
          </p>
        )}
      </div>

      {/* ── Polymarket Embed ─────────────────────────────────── */}
      <PolymarketEmbed slug={slug!} />

      <Separator />

      {/* ── Main 2-column layout ─────────────────────────────── */}
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-12">
        {/* Left column: markets list + selected market details */}
        <div className="flex flex-col gap-4 lg:col-span-8">
          {/* Market info card — prices, volume, liquidity, spread */}
          {selectedMarket && <MarketInfo marketId={selectedMarket.id} tokenId={selectedTokenId || undefined} wsBestBidAsk={ws.bestBidAsk} wsConnected={ws.connected} />}

          {/* Sub-markets list */}
          {event.markets.length > 1 && (
            <div className="flex flex-col gap-2">
              <h2 className="text-sm font-medium text-muted-foreground">
                Markets ({event.markets.length})
              </h2>
              <div className="flex flex-col gap-2">
                {event.markets.map((m) => (
                  <EventMarketCard
                    key={m.id}
                    market={m}
                    selected={selectedMarket?.id === m.id}
                    onSelect={handleSelectMarket}
                  />
                ))}
              </div>
            </div>
          )}

          {/* Orderbook (UP left, DOWN right) then Price chart below */}
          {tokens.length > 0 && (
            <div className="flex flex-col gap-4">
              <OrderbookView tokens={tokens} outcomes={outcomes} wsOrderbooks={ws.orderbooks} wsConnected={ws.connected} />
              <PriceChart tokens={tokens} outcomes={outcomes} wsBestBidAsks={ws.bestBidAsks} wsConnected={ws.connected} />
            </div>
          )}

          {/* Activity Feed */}
          {selectedTokenId && selectedMarket && (
            <ActivityFeed
              tokenId={selectedTokenId}
              marketId={selectedMarket.id}
              conditionId={selectedMarket.conditionId}
              enabled={!isEnded}
              wsTrades={ws.trades}
              wsConnected={ws.connected}
            />
          )}
        </div>

        {/* Right column: trading panel + positions (sticky) */}
        <div className="flex flex-col gap-4 lg:col-span-4 lg:sticky lg:top-4 lg:self-start">
          {selectedTokenId && !isEnded && (
            <TradingPanel
              tokenId={selectedTokenId}
              outcomes={outcomes}
              tokenIds={tokens}
              onSwitchToken={handleSwitchToken}
              wsBestBidAsk={ws.bestBidAsk}
              wsConnected={ws.connected}
            />
          )}
          {selectedTokenId && isEnded && (
            <Alert>
              <AlertDescription className="text-center text-sm">
                本场已结束，无法交易
              </AlertDescription>
            </Alert>
          )}
          <PositionTable />
        </div>
      </div>
    </div>
  )
}
