import { useQuery } from "@tanstack/react-query"
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { ScrollArea } from "@/components/ui/scroll-area"
import { Skeleton } from "@/components/ui/skeleton"
import { cn } from "@/lib/utils"
import { fetchOrderbook } from "@/api/client"
import type { PriceLevel } from "@/types"
import type { OrderbookState } from "@/hooks/useMarketWebSocket"

interface OrderbookViewProps {
  /** All token IDs for this market (e.g. [upTokenId, downTokenId]) */
  tokens: string[]
  /** Outcome labels matching tokens (e.g. ["Up", "Down"]) */
  outcomes: string[]
  /** Per-token WS orderbook state (keyed by token id) */
  wsOrderbooks?: Record<string, OrderbookState>
  wsConnected?: boolean
}

function LevelRow({
  level,
  maxSize,
  side,
}: {
  level: PriceLevel
  maxSize: number
  side: "bid" | "ask"
}) {
  const price = parseFloat(level.price)
  const size = parseFloat(level.size)
  const pct = maxSize > 0 ? (size / maxSize) * 100 : 0

  return (
    <div className="relative flex items-center justify-between px-2 py-0.5 text-xs font-mono">
      <div
        className={cn(
          "absolute inset-y-0 opacity-25",
          side === "bid" ? "right-0 bg-chart-2" : "left-0 bg-chart-1",
        )}
        style={{ width: `${pct}%` }}
      />
      <span className="relative z-10">{(price * 100).toFixed(1)}¢</span>
      <span className="relative z-10 text-muted-foreground">
        {size.toFixed(2)}
      </span>
    </div>
  )
}

function TokenOrderbook({
  tokenId,
  label,
  wsOrderbook,
  wsConnected,
}: {
  tokenId: string
  label: string
  wsOrderbook?: OrderbookState | null
  wsConnected?: boolean
}) {
  const hasWsBook = !!(wsConnected && wsOrderbook)
  const { data: book, isLoading } = useQuery({
    queryKey: ["orderbook", tokenId],
    queryFn: () => fetchOrderbook(tokenId),
    refetchInterval: hasWsBook ? false : 5_000,
    enabled: !!tokenId && !hasWsBook,
  })

  const bidsRaw = wsOrderbook?.bids ?? book?.bids ?? []
  const asksRaw = wsOrderbook?.asks ?? book?.asks ?? []
  const lastTradePrice = wsOrderbook?.lastTradePrice ?? book?.last_trade_price ?? ""
  const hasData = bidsRaw.length > 0 || asksRaw.length > 0

  if (isLoading && !hasWsBook) {
    return <Skeleton className="h-36 w-full" />
  }
  if (!hasData) {
    return (
      <div className="px-2 py-3 text-center text-xs text-muted-foreground">
        {label}: 暂无挂单
      </div>
    )
  }

  const asks = [...asksRaw].slice(0, 10).reverse()
  const bids = bidsRaw.slice(0, 10)

  const allSizes = [
    ...asks.map((l) => parseFloat(l.size)),
    ...bids.map((l) => parseFloat(l.size)),
  ]
  const maxSize = Math.max(...allSizes, 1)

  const spread = asks.length > 0 && bids.length > 0
    ? ((parseFloat(asks[asks.length - 1]?.price ?? "0") - parseFloat(bids[0]?.price ?? "0")) * 100).toFixed(1)
    : "–"

  return (
    <div className="flex flex-col">
      <div className="flex items-center justify-between px-2 py-1 bg-muted/30">
        <span className="text-xs font-semibold">{label}</span>
        <span className="text-[10px] text-muted-foreground">Spread: {spread}¢</span>
      </div>
      {asks.map((level, i) => (
        <LevelRow key={`a-${i}`} level={level} maxSize={maxSize} side="ask" />
      ))}
      <div className="border-y bg-muted/50 px-2 py-0.5 text-center text-[10px] font-medium">
        {lastTradePrice
          ? `Last: ${(parseFloat(lastTradePrice) * 100).toFixed(1)}¢`
          : "–"}
      </div>
      {bids.map((level, i) => (
        <LevelRow key={`b-${i}`} level={level} maxSize={maxSize} side="bid" />
      ))}
    </div>
  )
}

export default function OrderbookView({ tokens, outcomes, wsOrderbooks, wsConnected }: OrderbookViewProps) {
  if (tokens.length === 0) return null

  return (
    <Card>
      <CardHeader className="pb-2">
        <div className="flex items-center justify-between">
          <CardTitle className="text-sm">Orderbook</CardTitle>
        </div>
        <div className="flex justify-between text-[10px] text-muted-foreground px-2">
          <span>Price</span>
          <span>Size</span>
        </div>
      </CardHeader>
      <CardContent className="p-0">
        <ScrollArea className="max-h-[540px]">
          <div className="flex flex-col divide-y">
            {tokens.map((tid, i) => (
              <TokenOrderbook
                key={tid}
                tokenId={tid}
                label={outcomes[i] ?? `Token ${i + 1}`}
                wsOrderbook={wsOrderbooks?.[tid]}
                wsConnected={wsConnected}
              />
            ))}
          </div>
        </ScrollArea>
      </CardContent>
    </Card>
  )
}
