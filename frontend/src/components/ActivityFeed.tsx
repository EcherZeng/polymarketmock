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
import type { TradeRecord } from "@/types"

interface ActivityFeedProps {
  tokenId: string
}

function fmtTime(iso: string): string {
  try {
    return new Date(iso).toLocaleTimeString("zh-CN", {
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
      hour12: false,
    })
  } catch {
    return iso
  }
}

export default function ActivityFeed({ tokenId }: ActivityFeedProps) {
  const { data, isLoading } = useQuery({
    queryKey: ["activityFeed", tokenId],
    queryFn: () => fetchTradeHistory(0, 20, tokenId),
    enabled: !!tokenId,
    refetchInterval: 10_000,
  })

  const trades: TradeRecord[] = data?.trades ?? []

  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-sm">Activity</CardTitle>
      </CardHeader>
      <CardContent>
        {isLoading ? (
          <div className="flex flex-col gap-2">
            {Array.from({ length: 5 }).map((_, i) => (
              <Skeleton key={i} className="h-6 w-full" />
            ))}
          </div>
        ) : trades.length === 0 ? (
          <p className="py-4 text-center text-sm text-muted-foreground">
            No trades yet
          </p>
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="w-20">Time</TableHead>
                <TableHead className="w-14">Side</TableHead>
                <TableHead className="text-right">Shares</TableHead>
                <TableHead className="text-right">Price</TableHead>
                <TableHead className="text-right">Cost</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {trades.map((t) => (
                <TableRow key={t.order_id + t.timestamp}>
                  <TableCell className="text-xs">{fmtTime(t.timestamp)}</TableCell>
                  <TableCell>
                    <Badge
                      variant={t.side === "BUY" ? "default" : "secondary"}
                      className="text-xs"
                    >
                      {t.side}
                    </Badge>
                  </TableCell>
                  <TableCell className="text-right">{t.amount.toFixed(2)}</TableCell>
                  <TableCell className="text-right">
                    {(t.avg_price * 100).toFixed(1)}¢
                  </TableCell>
                  <TableCell className="text-right">
                    ${t.total_cost.toFixed(2)}
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
