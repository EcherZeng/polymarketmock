import { useQuery } from "@tanstack/react-query"
import { Badge } from "@/components/ui/badge"
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { Skeleton } from "@/components/ui/skeleton"
import { fetchMarket } from "@/api/client"
import type { Market } from "@/types"

interface MarketInfoProps {
  marketId: string
}

export default function MarketInfo({ marketId }: MarketInfoProps) {
  const { data: market, isLoading } = useQuery<Market>({
    queryKey: ["market", marketId],
    queryFn: () => fetchMarket(marketId),
    refetchInterval: 30_000,
  })

  if (isLoading) {
    return (
      <Card>
        <CardHeader>
          <Skeleton className="h-5 w-3/4" />
          <Skeleton className="h-4 w-1/2" />
        </CardHeader>
        <CardContent>
          <Skeleton className="h-20 w-full" />
        </CardContent>
      </Card>
    )
  }

  if (!market) return null

  // outcomePrices / outcomes may be arrays (normalized) or JSON strings (legacy)
  const prices: string[] = Array.isArray(market.outcomePrices)
    ? market.outcomePrices
    : (() => { try { return JSON.parse(market.outcomePrices as unknown as string) } catch { return [] } })()
  const outcomes: string[] = Array.isArray(market.outcomes)
    ? market.outcomes
    : (() => { try { return JSON.parse(market.outcomes as unknown as string) } catch { return [] } })()

  const yesPrice = prices[0]
    ? (parseFloat(prices[0]) * 100).toFixed(1)
    : "–"
  const noPrice = prices[1]
    ? (parseFloat(prices[1]) * 100).toFixed(1)
    : "–"

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center gap-2">
          <CardTitle className="text-base">{market.question}</CardTitle>
          <Badge variant={market.active ? "default" : "secondary"}>
            {market.active ? "Active" : "Closed"}
          </Badge>
        </div>
        <CardDescription>ID: {market.id}</CardDescription>
      </CardHeader>
      <CardContent>
        <div className="grid grid-cols-2 gap-4 text-sm">
          <div className="flex flex-col gap-1">
            <span className="text-muted-foreground">{outcomes[0] ?? "Yes"}</span>
            <span className="text-2xl font-bold text-chart-2">{yesPrice}¢</span>
          </div>
          <div className="flex flex-col gap-1">
            <span className="text-muted-foreground">{outcomes[1] ?? "No"}</span>
            <span className="text-2xl font-bold text-chart-1">{noPrice}¢</span>
          </div>
        </div>
        <div className="mt-4 grid grid-cols-3 gap-2 text-xs text-muted-foreground">
          <div>
            <div>Volume 24h</div>
            <div className="font-medium text-foreground">
              ${market.volume24hr?.toLocaleString() ?? "–"}
            </div>
          </div>
          <div>
            <div>Liquidity</div>
            <div className="font-medium text-foreground">
              ${market.liquidity?.toLocaleString() ?? "–"}
            </div>
          </div>
          <div>
            <div>Spread</div>
            <div className="font-medium text-foreground">
              {((market.spread ?? 0) * 100).toFixed(1)}¢
            </div>
          </div>
        </div>
      </CardContent>
    </Card>
  )
}
