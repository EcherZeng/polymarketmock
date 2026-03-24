import { Badge } from "@/components/ui/badge"
import { cn } from "@/lib/utils"
import type { Market } from "@/types"

interface EventMarketCardProps {
  market: Market
  selected: boolean
  onSelect: (market: Market) => void
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

export default function EventMarketCard({ market, selected, onSelect }: EventMarketCardProps) {
  const outcomes = parseOutcomes(market.outcomes)
  const prices = parsePrices(market.outcomePrices)

  return (
    <div
      className={cn(
        "flex flex-col gap-2 rounded-lg border p-3 text-sm cursor-pointer transition-colors",
        selected
          ? "border-primary bg-primary/5 ring-1 ring-primary/20"
          : "hover:bg-accent/50",
      )}
      onClick={() => onSelect(market)}
    >
      <div className="font-medium leading-snug">{market.question}</div>

      {/* Outcome prices */}
      <div className="flex flex-wrap gap-2">
        {outcomes.map((name, i) => {
          const price = prices[i] ? (parseFloat(prices[i]) * 100).toFixed(0) : "—"
          return (
            <Badge
              key={name}
              variant="outline"
              className={cn(
                "text-xs",
                i === 0 ? "text-chart-2 border-chart-2" : "text-chart-1 border-chart-1",
              )}
            >
              {name} {price}¢
            </Badge>
          )
        })}
      </div>

      {/* Stats */}
      <div className="flex items-center gap-3 text-xs text-muted-foreground">
        <span>Vol {fmtVolume(market.volume24hr ?? 0)}</span>
        <span>·</span>
        <span>Liq {fmtVolume(market.liquidity ?? 0)}</span>
        {market.spread > 0 && (
          <>
            <span>·</span>
            <span>Spread {(market.spread * 100).toFixed(1)}¢</span>
          </>
        )}
        {market.active && !market.closed ? (
          <Badge variant="default" className="ml-auto text-xs">Active</Badge>
        ) : (
          <Badge variant="secondary" className="ml-auto text-xs">Closed</Badge>
        )}
      </div>
    </div>
  )
}
