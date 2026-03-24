import { useState } from "react"
import { useQuery } from "@tanstack/react-query"
import { Badge } from "@/components/ui/badge"
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { Skeleton } from "@/components/ui/skeleton"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { fetchRealtimeTrades, fetchTradeHistory } from "@/api/client"
import type { RealtimeTrade, TradeRecord } from "@/types"

interface ActivityFeedProps {
  tokenId: string
  enabled?: boolean
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

export default function ActivityFeed({ tokenId, enabled = true }: ActivityFeedProps) {
  const [tab, setTab] = useState("market")

  const { data: realtimeData, isLoading: realtimeLoading } = useQuery({
    queryKey: ["realtimeTrades", tokenId],
    queryFn: () => fetchRealtimeTrades(tokenId, 30),
    enabled: !!tokenId && enabled && tab === "market",
    refetchInterval: 1_000,
  })

  const { data: myData, isLoading: myLoading } = useQuery({
    queryKey: ["activityFeed", tokenId],
    queryFn: () => fetchTradeHistory(0, 20, tokenId),
    enabled: !!tokenId && enabled && tab === "mine",
    refetchInterval: 3_000,
  })

  const realtimeTrades: RealtimeTrade[] = realtimeData?.trades ?? []
  const myTrades: TradeRecord[] = myData?.trades ?? []

  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-sm">Activity</CardTitle>
      </CardHeader>
      <CardContent>
        <Tabs value={tab} onValueChange={setTab}>
          <TabsList className="w-full">
            <TabsTrigger value="market" className="flex-1 text-xs">
              市场成交
            </TabsTrigger>
            <TabsTrigger value="mine" className="flex-1 text-xs">
              我的交易
            </TabsTrigger>
          </TabsList>

          <TabsContent value="market" className="mt-2">
            {realtimeLoading ? (
              <div className="flex flex-col gap-2">
                {Array.from({ length: 5 }).map((_, i) => (
                  <Skeleton key={i} className="h-6 w-full" />
                ))}
              </div>
            ) : realtimeTrades.length === 0 ? (
              <p className="py-4 text-center text-xs text-muted-foreground">
                等待市场成交数据…
              </p>
            ) : (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead className="w-20 text-xs">时间</TableHead>
                    <TableHead className="w-14 text-xs">方向</TableHead>
                    <TableHead className="text-right text-xs">份额</TableHead>
                    <TableHead className="text-right text-xs">价格</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {realtimeTrades.map((t, i) => (
                    <TableRow
                      key={`${t.timestamp}-${i}`}
                      className="animate-in fade-in-0 duration-300"
                    >
                      <TableCell className="text-xs text-muted-foreground">
                        {fmtTime(t.timestamp)}
                      </TableCell>
                      <TableCell>
                        <Badge
                          variant={t.side === "BUY" ? "default" : "secondary"}
                          className="text-xs"
                        >
                          {t.side === "BUY" ? "↑买" : t.side === "SELL" ? "↓卖" : "—"}
                        </Badge>
                      </TableCell>
                      <TableCell className="text-right text-xs">
                        {t.size > 0 ? t.size.toFixed(0) : "—"}
                      </TableCell>
                      <TableCell className="text-right text-xs font-mono">
                        {(t.price * 100).toFixed(1)}¢
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            )}
          </TabsContent>

          <TabsContent value="mine" className="mt-2">
            {myLoading ? (
              <div className="flex flex-col gap-2">
                {Array.from({ length: 5 }).map((_, i) => (
                  <Skeleton key={i} className="h-6 w-full" />
                ))}
              </div>
            ) : myTrades.length === 0 ? (
              <p className="py-4 text-center text-xs text-muted-foreground">
                暂无交易记录
              </p>
            ) : (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead className="w-20 text-xs">时间</TableHead>
                    <TableHead className="w-14 text-xs">方向</TableHead>
                    <TableHead className="text-right text-xs">份额</TableHead>
                    <TableHead className="text-right text-xs">价格</TableHead>
                    <TableHead className="text-right text-xs">成本</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {myTrades.map((t) => (
                    <TableRow key={t.order_id + t.timestamp}>
                      <TableCell className="text-xs text-muted-foreground">
                        {fmtTime(t.timestamp)}
                      </TableCell>
                      <TableCell>
                        <Badge
                          variant={t.side === "BUY" ? "default" : "secondary"}
                          className="text-xs"
                        >
                          {t.side}
                        </Badge>
                      </TableCell>
                      <TableCell className="text-right text-xs">
                        {t.amount.toFixed(2)}
                      </TableCell>
                      <TableCell className="text-right text-xs">
                        {(t.avg_price * 100).toFixed(1)}¢
                      </TableCell>
                      <TableCell className="text-right text-xs">
                        ${t.total_cost.toFixed(2)}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            )}
          </TabsContent>
        </Tabs>
      </CardContent>
    </Card>
  )
}
