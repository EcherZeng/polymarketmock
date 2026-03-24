import { useState } from "react"
import { useQuery } from "@tanstack/react-query"
import { Button } from "@/components/ui/button"
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Skeleton } from "@/components/ui/skeleton"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { Badge } from "@/components/ui/badge"
import { fetchTradeHistory, fetchBacktestMarkets } from "@/api/client"

export default function HistoryPage() {
  const [offset, setOffset] = useState(0)
  const limit = 50

  const { data: tradeData, isLoading: tradesLoading } = useQuery({
    queryKey: ["tradeHistory", offset, limit],
    queryFn: () => fetchTradeHistory(offset, limit),
  })

  const { data: btMarkets } = useQuery({
    queryKey: ["backtestMarkets"],
    queryFn: fetchBacktestMarkets,
  })

  const trades = tradeData?.trades ?? []
  const total = tradeData?.total ?? 0

  return (
    <div className="flex flex-col gap-6">
      {/* Trade History */}
      <Card>
        <CardHeader>
          <CardTitle>Trade History</CardTitle>
        </CardHeader>
        <CardContent>
          {tradesLoading ? (
            <Skeleton className="h-48 w-full" />
          ) : trades.length === 0 ? (
            <p className="text-center text-sm text-muted-foreground py-8">
              No trade history yet. Place some orders on the Trading page.
            </p>
          ) : (
            <>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Time</TableHead>
                    <TableHead>Order ID</TableHead>
                    <TableHead>Side</TableHead>
                    <TableHead>Type</TableHead>
                    <TableHead className="text-right">Shares</TableHead>
                    <TableHead className="text-right">Avg Price</TableHead>
                    <TableHead className="text-right">Total Cost</TableHead>
                    <TableHead className="text-right">Slippage</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {trades.map((t) => (
                    <TableRow key={t.order_id}>
                      <TableCell className="text-xs">
                        {new Date(t.timestamp).toLocaleString()}
                      </TableCell>
                      <TableCell className="text-xs font-mono max-w-20 truncate">
                        {t.order_id.slice(0, 8)}…
                      </TableCell>
                      <TableCell>
                        <Badge variant={t.side === "BUY" ? "default" : "secondary"}>
                          {t.side}
                        </Badge>
                      </TableCell>
                      <TableCell className="text-xs">{t.type}</TableCell>
                      <TableCell className="text-right text-xs">
                        {t.amount.toFixed(2)}
                      </TableCell>
                      <TableCell className="text-right text-xs">
                        {(t.avg_price * 100).toFixed(2)}¢
                      </TableCell>
                      <TableCell className="text-right text-xs">
                        ${t.total_cost.toFixed(4)}
                      </TableCell>
                      <TableCell className="text-right text-xs text-muted-foreground">
                        {t.slippage_pct.toFixed(3)}%
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
              <div className="mt-4 flex items-center justify-between">
                <span className="text-xs text-muted-foreground">
                  Showing {offset + 1}–{Math.min(offset + limit, total)} of {total}
                </span>
                <div className="flex gap-2">
                  <Button
                    variant="outline"
                    size="sm"
                    disabled={offset === 0}
                    onClick={() => setOffset(Math.max(0, offset - limit))}
                  >
                    Previous
                  </Button>
                  <Button
                    variant="outline"
                    size="sm"
                    disabled={offset + limit >= total}
                    onClick={() => setOffset(offset + limit)}
                  >
                    Next
                  </Button>
                </div>
              </div>
            </>
          )}
        </CardContent>
      </Card>

      {/* Available Backtest Markets */}
      <Card>
        <CardHeader>
          <CardTitle>Available Historical Data</CardTitle>
        </CardHeader>
        <CardContent>
          {!btMarkets || (btMarkets as unknown[]).length === 0 ? (
            <p className="text-center text-sm text-muted-foreground py-8">
              No historical data collected yet. Data collection starts when you
              watch a market on the Trading page.
            </p>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Market ID</TableHead>
                  <TableHead>Token ID</TableHead>
                  <TableHead>Earliest</TableHead>
                  <TableHead>Latest</TableHead>
                  <TableHead className="text-right">Data Points</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {(btMarkets as Array<Record<string, unknown>>).map((m, i) => (
                  <TableRow key={i}>
                    <TableCell className="text-xs font-mono max-w-24 truncate">
                      {String(m.market_id).slice(0, 12)}…
                    </TableCell>
                    <TableCell className="text-xs font-mono max-w-24 truncate">
                      {String(m.token_id).slice(0, 12)}…
                    </TableCell>
                    <TableCell className="text-xs">
                      {String(m.earliest_data)}
                    </TableCell>
                    <TableCell className="text-xs">
                      {String(m.latest_data)}
                    </TableCell>
                    <TableCell className="text-right text-xs">
                      {String(m.data_points)}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>
    </div>
  )
}
