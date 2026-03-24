import { useState, useEffect } from "react"
import { useParams, Link } from "react-router-dom"
import { useQuery } from "@tanstack/react-query"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"
import { Separator } from "@/components/ui/separator"
import PolymarketEmbed from "@/components/PolymarketEmbed"
import EventMarketCard from "@/components/EventMarketCard"
import MarketInfo from "@/components/MarketInfo"
import OrderbookView from "@/components/OrderbookView"
import PriceChart from "@/components/PriceChart"
import TradingPanel from "@/components/TradingPanel"
import PositionTable from "@/components/PositionTable"
import ActivityFeed from "@/components/ActivityFeed"
import { resolveSlug } from "@/api/client"
import type { Market, MarketEvent } from "@/types"

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
  const [selectedMarket, setSelectedMarket] = useState<Market | null>(null)
  const [selectedTokenId, setSelectedTokenId] = useState("")
  const [selectedOutcomeIdx, setSelectedOutcomeIdx] = useState(0)

  const { data: event, isLoading, error } = useQuery<MarketEvent>({
    queryKey: ["event", slug],
    queryFn: () => resolveSlug(slug!),
    enabled: !!slug,
    staleTime: 30_000,
  })

  // Auto-select first market when event loads
  useEffect(() => {
    if (event?.markets?.[0] && !selectedMarket) {
      const m = event.markets[0]
      setSelectedMarket(m)
      const tokens = parseTokenIds(m.clobTokenIds)
      if (tokens[0]) {
        setSelectedTokenId(tokens[0])
        setSelectedOutcomeIdx(0)
      }
    }
  }, [event?.id])

  function handleSelectMarket(m: Market) {
    setSelectedMarket(m)
    const tokens = parseTokenIds(m.clobTokenIds)
    if (tokens[0]) {
      setSelectedTokenId(tokens[0])
      setSelectedOutcomeIdx(0)
    }
  }

  function handleSelectOutcome(idx: number) {
    if (!selectedMarket) return
    const tokens = parseTokenIds(selectedMarket.clobTokenIds)
    if (tokens[idx]) {
      setSelectedTokenId(tokens[idx])
      setSelectedOutcomeIdx(idx)
    }
  }

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

  const tokens = selectedMarket ? parseTokenIds(selectedMarket.clobTokenIds) : []
  const outcomes = selectedMarket ? parseOutcomes(selectedMarket.outcomes) : []

  return (
    <div className="flex flex-col gap-4">
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
            {event.active && !event.closed ? (
              <Badge variant="default">Active</Badge>
            ) : (
              <Badge variant="secondary">Closed</Badge>
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
          {selectedMarket && <MarketInfo marketId={selectedMarket.id} />}

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

          {/* Outcome token selector */}
          {selectedMarket && tokens.length > 1 && (
            <div className="flex items-center gap-2">
              <span className="text-sm text-muted-foreground">Outcome:</span>
              {outcomes.map((name, i) => (
                <Button
                  key={tokens[i] ?? i}
                  variant={selectedOutcomeIdx === i ? "default" : "outline"}
                  size="sm"
                  onClick={() => handleSelectOutcome(i)}
                >
                  {name}
                </Button>
              ))}
            </div>
          )}

          {/* Orderbook + Price chart side by side on large screens */}
          {selectedTokenId && (
            <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
              <OrderbookView tokenId={selectedTokenId} />
              <PriceChart tokenId={selectedTokenId} />
            </div>
          )}

          {/* Activity Feed — simulated trades */}
          {selectedTokenId && (
            <ActivityFeed tokenId={selectedTokenId} />
          )}
        </div>

        {/* Right column: trading panel + positions (sticky) */}
        <div className="flex flex-col gap-4 lg:col-span-4 lg:sticky lg:top-4 lg:self-start">
          {selectedTokenId && <TradingPanel tokenId={selectedTokenId} />}
          <PositionTable />
        </div>
      </div>
    </div>
  )
}
