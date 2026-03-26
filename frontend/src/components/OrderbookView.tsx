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

interface OrderbookViewProps {
  tokenId: string
  /** WS-driven orderbook (if provided, HTTP polling is disabled) */
  wsOrderbook?: {
    bids: PriceLevel[]
    asks: PriceLevel[]
    lastTradePrice: string
  } | null
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

export default function OrderbookView({ tokenId, wsOrderbook, wsConnected }: OrderbookViewProps) {
  // HTTP polling fallback — disabled only when WS has actually delivered data
  const hasWsBook = !!(wsConnected && wsOrderbook)
  const { data: book, isLoading } = useQuery({
    queryKey: ["orderbook", tokenId],
    queryFn: () => fetchOrderbook(tokenId),
    refetchInterval: hasWsBook ? false : 5_000,
    enabled: !hasWsBook,
  })

  // Prefer WS data, fall back to HTTP
  const bidsRaw = wsOrderbook?.bids ?? book?.bids ?? []
  const asksRaw = wsOrderbook?.asks ?? book?.asks ?? []
  const lastTradePrice = wsOrderbook?.lastTradePrice ?? book?.last_trade_price ?? ""
  const hasData = bidsRaw.length > 0 || asksRaw.length > 0

  if (isLoading && !hasWsBook) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="text-sm">Orderbook</CardTitle>
        </CardHeader>
        <CardContent>
          <Skeleton className="h-48 w-full" />
        </CardContent>
      </Card>
    )
  }

  if (!hasData) return null

  const asks = [...asksRaw].slice(0, 15).reverse()
  const bids = bidsRaw.slice(0, 15)

  const allSizes = [
    ...asks.map((l) => parseFloat(l.size)),
    ...bids.map((l) => parseFloat(l.size)),
  ]
  const maxSize = Math.max(...allSizes, 1)

  return (
    <Card>
      <CardHeader className="pb-2">
        <div className="flex items-center justify-between">
          <CardTitle className="text-sm">Orderbook</CardTitle>
          <span className="text-xs text-muted-foreground">
            Spread: {((parseFloat(asks[asks.length - 1]?.price ?? "0") - parseFloat(bids[0]?.price ?? "0")) * 100).toFixed(1)}¢
          </span>
        </div>
        <div className="flex justify-between text-[10px] text-muted-foreground px-2">
          <span>Price</span>
          <span>Size</span>
        </div>
      </CardHeader>
      <CardContent className="p-0">
        <ScrollArea className="h-72">
          <div className="flex flex-col">
            {asks.map((level, i) => (
              <LevelRow key={`a-${i}`} level={level} maxSize={maxSize} side="ask" />
            ))}
            <div className="border-y bg-muted/50 px-2 py-1 text-center text-xs font-medium">
              {lastTradePrice
                ? `Last: ${(parseFloat(lastTradePrice) * 100).toFixed(1)}¢`
                : "–"}
            </div>
            {bids.map((level, i) => (
              <LevelRow key={`b-${i}`} level={level} maxSize={maxSize} side="bid" />
            ))}
          </div>
        </ScrollArea>
      </CardContent>
    </Card>
  )
}
