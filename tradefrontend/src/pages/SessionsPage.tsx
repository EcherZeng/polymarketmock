import { useSessions } from "@/hooks/useTradeData"
import { useNavigate } from "react-router-dom"
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Skeleton } from "@/components/ui/skeleton"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { cn, fmtUsd, pnlColor, epochToIso, fmtDateTimeCst } from "@/lib/utils"
import type { SessionState } from "@/types"

const stateLabel: Record<SessionState, string> = {
  pending: "等待中",
  active: "交易中",
  settling: "结算中",
  settled: "已结算",
}

export default function SessionsPage() {
  const navigate = useNavigate()
  const { data: sessions, isLoading } = useSessions(100)

  return (
    <div className="flex flex-col gap-6">
      <h1 className="text-2xl font-semibold tracking-tight">Session 历史</h1>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">全部 Sessions</CardTitle>
          <CardDescription>按时间倒序排列</CardDescription>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <div className="flex flex-col gap-2">
              {[1, 2, 3, 4, 5].map((i) => (
                <Skeleton key={i} className="h-10" />
              ))}
            </div>
          ) : !sessions || sessions.length === 0 ? (
            <p className="py-4 text-center text-sm text-muted-foreground">暂无 Session 记录</p>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Slug</TableHead>
                  <TableHead>开始时间</TableHead>
                  <TableHead>状态</TableHead>
                  <TableHead className="text-right">交易 PnL</TableHead>
                  <TableHead className="text-right">结算 PnL</TableHead>
                  <TableHead className="text-right">总 PnL</TableHead>
                  <TableHead>结算</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {sessions.map((s) => (
                  <TableRow
                    key={s.slug}
                    className="cursor-pointer hover:bg-muted/50"
                    onClick={() => navigate(`/sessions/${encodeURIComponent(s.slug)}`)}
                  >
                    <TableCell className="max-w-[180px] truncate font-mono text-xs">
                      {s.slug}
                    </TableCell>
                    <TableCell className="font-mono text-xs">
                      {fmtDateTimeCst(epochToIso(s.start_epoch))}
                    </TableCell>
                    <TableCell>
                      <Badge variant="outline" className="text-xs">
                        {stateLabel[s.state] ?? s.state}
                      </Badge>
                    </TableCell>
                    <TableCell className={cn("text-right font-mono", pnlColor(s.trade_pnl))}>
                      {fmtUsd(s.trade_pnl)}
                    </TableCell>
                    <TableCell className={cn("text-right font-mono", pnlColor(s.settlement_pnl))}>
                      {fmtUsd(s.settlement_pnl)}
                    </TableCell>
                    <TableCell className={cn("text-right font-mono font-semibold", pnlColor(s.total_pnl))}>
                      {fmtUsd(s.total_pnl)}
                    </TableCell>
                    <TableCell className="text-xs">{s.settlement_outcome || "—"}</TableCell>
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
