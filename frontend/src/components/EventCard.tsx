import { useNavigate } from "react-router-dom"
import { Badge } from "@/components/ui/badge"
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { cn } from "@/lib/utils"
import type { MarketEvent } from "@/types"

interface EventCardProps {
  event: MarketEvent
}

function parseOutcomes(raw: unknown): string[] {
  if (Array.isArray(raw)) return raw
  if (typeof raw === "string") {
    try { return JSON.parse(raw) } catch { return [] }
  }
  return []
}

function parsePrices(raw: unknown): string[] {
  if (Array.isArray(raw)) return raw
  if (typeof raw === "string") {
    try { return JSON.parse(raw) } catch { return [] }
  }
  return []
}

function fmtVolume(v: number): string {
  if (v >= 1_000_000) return `$${(v / 1_000_000).toFixed(1)}M`
  if (v >= 1_000) return `$${(v / 1_000).toFixed(1)}K`
  return `$${v.toFixed(0)}`
}

function fmtTime(iso: string | undefined): string {
  if (!iso) return ""
  try {
    return new Date(iso).toLocaleTimeString("zh-CN", {
      hour: "2-digit",
      minute: "2-digit",
      hour12: false,
    })
  } catch {
    return ""
  }
}

const STATUS_BADGE: Record<
  string,
  { label: string; variant: "default" | "secondary" | "destructive" | "outline" }
> = {
  live: { label: "LIVE", variant: "destructive" },
  upcoming: { label: "即将开始", variant: "default" },
  ended: { label: "已结束", variant: "secondary" },
  unknown: { label: "—", variant: "outline" },
}

export default function EventCard({ event }: EventCardProps) {
  const navigate = useNavigate()
  const market = event.markets?.[0]
  const outcomes = market ? parseOutcomes(market.outcomes) : []
  const prices = market ? parsePrices(market.outcomePrices) : []
  const status = event._status ?? (event.active && !event.closed ? "upcoming" : "ended")
  const sc = STATUS_BADGE[status] ?? STATUS_BADGE.unknown
  const isLive = status === "live"
  const isEnded = status === "ended"

  return (
    <Card
      className={cn(
        "cursor-pointer transition-colors",
        isLive
          ? "border-destructive/50 bg-destructive/5 hover:bg-destructive/10"
          : isEnded
            ? "opacity-70 hover:opacity-90 hover:bg-accent/50"
            : "hover:bg-accent/50",
      )}
      onClick={() => navigate(`/event/${event.slug}`)}
    >
      <CardHeader className="pb-2">
        <div className="flex items-start justify-between gap-2">
          <CardTitle className="text-sm font-medium leading-snug">
            {event.title}
          </CardTitle>
          <Badge variant={sc.variant} className="shrink-0 text-xs">
            {sc.label}
          </Badge>
        </div>
        <div className="text-xs text-muted-foreground">
          {fmtTime(event.startDate)} – {fmtTime(event.endDate)}
        </div>
      </CardHeader>
      <CardContent className="flex flex-col gap-2">
        {/* Outcome prices — large display like Polymarket */}
        {outcomes.length > 0 && (
          <div className="flex items-center gap-3">
            {outcomes.map((name, i) => {
              const pct = prices[i]
                ? (parseFloat(prices[i]) * 100).toFixed(0)
                : "—"
              return (
                <div key={name} className="flex items-baseline gap-1">
                  <span
                    className={cn(
                      "text-xl font-bold",
                      i === 0 ? "text-chart-2" : "text-chart-1",
                    )}
                  >
                    {pct}%
                  </span>
                  <span className="text-xs text-muted-foreground">{name}</span>
                </div>
              )
            })}
          </div>
        )}

        {/* Stats row */}
        <div className="flex items-center gap-3 text-xs text-muted-foreground">
          <span>Vol {fmtVolume(event.volume ?? 0)}</span>
          <span>·</span>
          <span>Liq {fmtVolume(event.liquidity ?? 0)}</span>
          {market?.spread != null && market.spread > 0 && (
            <>
              <span>·</span>
              <span>Spread {(market.spread * 100).toFixed(1)}¢</span>
            </>
          )}
        </div>
      </CardContent>
    </Card>
  )
}
