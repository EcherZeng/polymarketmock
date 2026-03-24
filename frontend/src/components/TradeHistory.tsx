import { useQuery } from "@tanstack/react-query"
import { Badge } from "@/components/ui/badge"
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { Skeleton } from "@/components/ui/skeleton"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { fetchTradeHistory } from "@/api/client"

export default function TradeHistory() {
  const { data, isLoading } = useQuery({
    queryKey: ["tradeHistory"],
    queryFn: () => fetchTradeHistory(0, 20),
    refetchInterval: 10_000,
  })

  if (isLoading) {
    return (
      <Card>
        <CardHeader>
          <Skeleton className="h-5 w-1/3" />
        </CardHeader>
        <CardContent>
          <Skeleton className="h-32 w-full" />
        </CardContent>
      </Card>
    )
  }

  const trades = data?.trades ?? []

  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-sm">Recent Trades</CardTitle>
      </CardHeader>
      <CardContent>
        {trades.length === 0 ? (
          <p className="text-center text-xs text-muted-foreground py-4">
            No trades yet
          </p>
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="text-xs">Time</TableHead>
                <TableHead className="text-xs">Side</TableHead>
                <TableHead className="text-xs text-right">Shares</TableHead>
                <TableHead className="text-xs text-right">Price</TableHead>
                <TableHead className="text-xs text-right">Cost</TableHead>
                <TableHead className="text-xs text-right">Slip</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {trades.map((t) => (
                <TableRow key={t.order_id}>
                  <TableCell className="text-xs text-muted-foreground">
                    {new Date(t.timestamp).toLocaleTimeString()}
                  </TableCell>
                  <TableCell className="text-xs">
                    <Badge variant={t.side === "BUY" ? "default" : "secondary"}>
                      {t.side}
                    </Badge>
                  </TableCell>
                  <TableCell className="text-xs text-right">
                    {t.amount.toFixed(2)}
                  </TableCell>
                  <TableCell className="text-xs text-right">
                    {(t.avg_price * 100).toFixed(1)}¢
                  </TableCell>
                  <TableCell className="text-xs text-right">
                    ${t.total_cost.toFixed(4)}
                  </TableCell>
                  <TableCell className="text-xs text-right text-muted-foreground">
                    {t.slippage_pct.toFixed(3)}%
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </CardContent>
    </Card>
  )
}
