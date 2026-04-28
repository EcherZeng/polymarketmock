import { useParams, useNavigate } from "react-router-dom"
import { useSessionDetail } from "@/hooks/useTradeData"
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"
import { Separator } from "@/components/ui/separator"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { cn, fmtUsd, pnlColor, epochToIso, fmtDateTimeCst } from "@/lib/utils"
import { ArrowLeft } from "lucide-react"

export default function SessionDetailPage() {
  const { slug } = useParams<{ slug: string }>()
  const navigate = useNavigate()
  const { data, isLoading } = useSessionDetail(slug ?? "")

  if (isLoading) {
    return (
      <div className="flex flex-col gap-4">
        <Skeleton className="h-8 w-64" />
        <Skeleton className="h-48" />
        <Skeleton className="h-64" />
      </div>
    )
  }

  if (!data) {
    return <p className="py-8 text-center text-muted-foreground">Session 不存在</p>
  }

  const { session: s, trades } = data

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-center gap-3">
        <Button variant="ghost" size="sm" onClick={() => navigate("/sessions")}>
          <ArrowLeft data-icon="inline-start" />
          返回
        </Button>
        <h1 className="text-xl font-semibold tracking-tight font-mono">{s.slug}</h1>
      </div>

      {/* ── Session summary ──────── */}
      <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
        <Card>
          <CardHeader className="pb-2">
            <CardDescription>状态</CardDescription>
          </CardHeader>
          <CardContent>
            <Badge variant="outline">{s.state}</Badge>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardDescription>开始时间</CardDescription>
          </CardHeader>
          <CardContent>
            <p className="font-mono text-sm">{fmtDateTimeCst(epochToIso(s.start_epoch))}</p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardDescription>持续时间</CardDescription>
          </CardHeader>
          <CardContent>
            <p className="font-mono text-sm">{s.duration_s / 60} 分钟</p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardDescription>结算结果</CardDescription>
          </CardHeader>
          <CardContent>
            <p className="text-sm">{s.settlement_outcome || "未结算"}</p>
          </CardContent>
        </Card>
      </div>

      {/* PnL summary */}
      <div className="grid grid-cols-3 gap-4">
        <Card>
          <CardHeader className="pb-2">
            <CardDescription>交易 PnL</CardDescription>
          </CardHeader>
          <CardContent>
            <p className={cn("text-xl font-semibold font-mono", pnlColor(s.trade_pnl))}>
              {fmtUsd(s.trade_pnl)}
            </p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardDescription>结算 PnL</CardDescription>
          </CardHeader>
          <CardContent>
            <p className={cn("text-xl font-semibold font-mono", pnlColor(s.settlement_pnl))}>
              {fmtUsd(s.settlement_pnl)}
            </p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardDescription>总 PnL</CardDescription>
          </CardHeader>
          <CardContent>
            <p className={cn("text-xl font-semibold font-mono", pnlColor(s.total_pnl))}>
              {fmtUsd(s.total_pnl)}
            </p>
          </CardContent>
        </Card>
      </div>

      {s.error && (
        <Card className="border-red-200 dark:border-red-800">
          <CardHeader>
            <CardTitle className="text-base text-red-600 dark:text-red-400">错误信息</CardTitle>
          </CardHeader>
          <CardContent>
            <pre className="whitespace-pre-wrap text-xs">{s.error}</pre>
          </CardContent>
        </Card>
      )}

      <Separator />

      {/* ── Trades ────────────────── */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">交易记录</CardTitle>
          <CardDescription>本 Session 共 {trades.length} 笔交易</CardDescription>
        </CardHeader>
        <CardContent>
          {trades.length === 0 ? (
            <p className="py-4 text-center text-sm text-muted-foreground">无交易记录</p>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>时间</TableHead>
                  <TableHead>Order ID</TableHead>
                  <TableHead>方向</TableHead>
                  <TableHead className="text-right">数量</TableHead>
                  <TableHead className="text-right">均价</TableHead>
                  <TableHead className="text-right">成本</TableHead>
                  <TableHead className="text-right">手续费</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {trades.map((t) => (
                  <TableRow key={t.id}>
                    <TableCell className="font-mono text-xs">
                      {t.timestamp ? fmtDateTimeCst(t.timestamp) : "—"}
                    </TableCell>
                    <TableCell className="max-w-[100px] truncate font-mono text-xs">
                      {t.order_id}
                    </TableCell>
                    <TableCell>
                      <Badge variant="outline" className={t.side === "BUY" ? "text-green-600" : "text-red-600"}>
                        {t.side}
                      </Badge>
                    </TableCell>
                    <TableCell className="text-right font-mono">{t.filled_shares.toFixed(2)}</TableCell>
                    <TableCell className="text-right font-mono">{t.avg_price.toFixed(4)}</TableCell>
                    <TableCell className="text-right font-mono">{fmtUsd(t.total_cost)}</TableCell>
                    <TableCell className="text-right font-mono">{fmtUsd(t.fees)}</TableCell>
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
