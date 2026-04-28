import { useConfigState } from "@/hooks/useTradeData"
import { useLiveWs } from "@/hooks/useLiveWs"
import { useMutation } from "@tanstack/react-query"
import { tradeApi } from "@/api/trade"
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
import { cn, fmtUsd, pnlColor, fmtDateTimeCst } from "@/lib/utils"
import type { SessionState } from "@/types"
import {
  Activity,
  Pause,
  Play,
  TrendingUp,
  TrendingDown,
  Wallet,
  Timer,
  Settings2,
  X,
  Layers,
} from "lucide-react"
import { useState } from "react"

const stateColors: Record<SessionState, string> = {
  pending: "bg-blue-100 text-blue-700 dark:bg-blue-900 dark:text-blue-300",
  active: "bg-green-100 text-green-700 dark:bg-green-900 dark:text-green-300",
  settling: "bg-orange-100 text-orange-700 dark:bg-orange-900 dark:text-orange-300",
  settled: "bg-muted text-muted-foreground",
}

function SessionSlotCard({ slot, label }: { slot: { slug: string; state: SessionState; time_remaining_s: number } | null; label: string }) {
  if (!slot) {
    return (
      <Card>
        <CardHeader>
          <CardDescription>{label}</CardDescription>
          <CardTitle className="text-muted-foreground">无活跃 Session</CardTitle>
        </CardHeader>
      </Card>
    )
  }
  const mins = Math.floor(slot.time_remaining_s / 60)
  const secs = Math.floor(slot.time_remaining_s % 60)
  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <CardDescription>{label}</CardDescription>
          <Badge className={cn("text-xs", stateColors[slot.state])}>{slot.state}</Badge>
        </div>
        <CardTitle className="text-base font-mono">{slot.slug}</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="flex items-center gap-2 text-sm text-muted-foreground">
          <Timer className="text-muted-foreground" />
          <span>剩余 {mins}:{String(secs).padStart(2, "0")}</span>
        </div>
      </CardContent>
    </Card>
  )
}

export default function DashboardPage() {
  const { connected, session, portfolio, pnl, trades } = useLiveWs()
  const { data: config } = useConfigState()
  const [showStrategy, setShowStrategy] = useState(false)

  const statusLoading = !session && !connected

  const pauseMut = useMutation({ mutationFn: tradeApi.pause })
  const resumeMut = useMutation({ mutationFn: tradeApi.resume })

  return (
    <div className="flex flex-col gap-6">
      {/* ── Top Bar ─────────────────────────── */}
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold tracking-tight">仪表盘</h1>
        <div className="flex items-center gap-2">
          <Button variant="outline" size="sm" onClick={() => setShowStrategy(!showStrategy)}>
            <Settings2 className="mr-1 h-4 w-4" />
            策略详情
          </Button>
          {statusLoading ? (
            <Skeleton className="h-9 w-24" />
          ) : session?.paused ? (
            <Button
              size="sm"
              onClick={() => resumeMut.mutate()}
              disabled={resumeMut.isPending}
            >
              <Play data-icon="inline-start" />
              恢复
            </Button>
          ) : (
            <Button
              variant="outline"
              size="sm"
              onClick={() => pauseMut.mutate()}
              disabled={pauseMut.isPending}
            >
              <Pause data-icon="inline-start" />
              暂停
            </Button>
          )}
        </div>
      </div>

      {/* ── Strategy Detail Panel ──────────── */}
      {showStrategy && config && (
        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <CardTitle className="text-base">策略详情</CardTitle>
              <Button variant="ghost" size="icon" onClick={() => setShowStrategy(false)}>
                <X className="h-4 w-4" />
              </Button>
            </div>
            <CardDescription>
              {config.active_preset_name
                ? `当前${config.active_preset_type === "composite" ? "复合" : "单一"}策略：${config.active_preset_name}`
                : "尚未加载策略 — 前往「策略配置」页面选择"}
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            {/* Composite strategy branches */}
            {config.active_preset_type === "composite" && config.composite_config && (
              <div className="rounded-md border border-purple-200 dark:border-purple-800 p-3 space-y-2">
                <div className="flex items-center gap-2">
                  <Layers className="h-4 w-4 text-purple-600" />
                  <Badge variant="outline" className="font-mono text-xs">{config.composite_config.composite_name}</Badge>
                  <span className="text-xs text-muted-foreground">
                    W1={config.composite_config.btc_windows.btc_trend_window_1}m W2={config.composite_config.btc_windows.btc_trend_window_2}m
                  </span>
                </div>
                <div className="space-y-1">
                  {config.composite_config.branches.map((b, i) => (
                    <div key={i} className="flex items-center gap-2 text-xs">
                      <Badge variant="outline" className="font-mono">{b.label} ≥{b.min_momentum}</Badge>
                      <span className="text-muted-foreground font-mono">{b.preset_name}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}
            {/* Single strategy params */}
            {config.active_preset_type === "single" && config.current_config && Object.keys(config.current_config).length > 0 && (
              <div>
                <div className="flex items-center gap-2 mb-2">
                  <Badge variant="outline" className="font-mono">{config.active_preset_name}</Badge>
                </div>
                <div className="grid grid-cols-2 gap-x-4 gap-y-1 text-sm">
                  {Object.entries(config.current_config).map(([k, v]) => (
                    <div key={k} className="contents">
                      <span className="text-muted-foreground font-mono">{k}</span>
                      <span className="text-right font-mono font-medium">{String(v)}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </CardContent>
        </Card>
      )}

      {/* ── Status & Session Cards ─────────── */}
      {statusLoading ? (
        <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
          {[1, 2, 3].map((i) => (
            <Skeleton key={i} className="h-32" />
          ))}
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
          {/* System status */}
          <Card>
            <CardHeader>
              <CardDescription>系统状态</CardDescription>
              <CardTitle className="flex items-center gap-2">
                <Activity className="text-primary" />
                {session?.paused ? (
                  <Badge variant="outline">已暂停</Badge>
                ) : (
                  <Badge className="bg-green-100 text-green-700 dark:bg-green-900 dark:text-green-300">
                    运行中
                  </Badge>
                )}
              </CardTitle>
            </CardHeader>
          </Card>

          {/* Current session */}
          <SessionSlotCard slot={session?.current_session ?? null} label="当前 Session" />

          {/* Next session */}
          <SessionSlotCard slot={session?.next_session ?? null} label="下一个 Session" />
        </div>
      )}

      {/* ── PnL & Balance Summary ─────────── */}
      <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
        <Card>
          <CardHeader className="pb-2">
            <CardDescription className="flex items-center gap-1">
              <Wallet /> 余额
            </CardDescription>
          </CardHeader>
          <CardContent>
            <p className="text-2xl font-semibold">{fmtUsd(portfolio?.balance ?? 0)}</p>
            <p className="text-xs text-muted-foreground">
              初始: {fmtUsd(portfolio?.initial_balance ?? 0)}
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardDescription className="flex items-center gap-1">
              <TrendingUp /> 收益率
            </CardDescription>
          </CardHeader>
          <CardContent>
            {(() => {
              const init = portfolio?.initial_balance ?? 0
              const totalPnl = pnl?.total.total_pnl ?? 0
              const rate = init > 0 ? totalPnl / init : 0
              return (
                <>
                  <p className={cn("text-2xl font-semibold", pnlColor(rate))}>
                    {(rate >= 0 ? "+" : "") + (rate * 100).toFixed(2)}%
                  </p>
                  <p className="text-xs text-muted-foreground">
                    {pnl?.total.total_sessions ?? 0} 场
                  </p>
                </>
              )
            })()}
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardDescription className="flex items-center gap-1">
              <TrendingDown /> 胜/负
            </CardDescription>
          </CardHeader>
          <CardContent>
            <p className="text-2xl font-semibold">
              <span className="text-green-600 dark:text-green-400">{pnl?.total.winning_sessions ?? 0}</span>
              {" / "}
              <span className="text-red-600 dark:text-red-400">{pnl?.total.losing_sessions ?? 0}</span>
            </p>
            <p className="text-xs text-muted-foreground">
              胜率: {pnl?.total.total_sessions
                ? ((pnl.total.winning_sessions / pnl.total.total_sessions) * 100).toFixed(1)
                : "0.0"}%
            </p>
          </CardContent>
        </Card>
      </div>

      <Separator />

      {/* ── Recent PnL List ───────────────── */}
      {pnl?.recent && pnl.recent.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">近期场次收益</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex flex-wrap gap-2">
              {pnl.recent.map((item) => (
                <Badge key={item.slug} variant="outline" className={cn("font-mono text-xs", pnlColor(item.total_pnl))}>
                  {item.slug.replace("btc-updown-15m-", "").slice(-6)} {fmtUsd(item.total_pnl)}
                </Badge>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {/* ── Recent Trades Table ───────────── */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">最近交易</CardTitle>
          <CardDescription>最近 20 笔交易记录</CardDescription>
        </CardHeader>
        <CardContent>
          {!trades || trades.length === 0 ? (
            <p className="py-4 text-center text-sm text-muted-foreground">暂无交易记录</p>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>时间</TableHead>
                  <TableHead>Session</TableHead>
                  <TableHead>方向</TableHead>
                  <TableHead className="text-right">数量</TableHead>
                  <TableHead className="text-right">均价</TableHead>
                  <TableHead className="text-right">成本</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {trades.slice(0, 20).map((t, i) => (
                  <TableRow key={t.id ?? i}>
                    <TableCell className="font-mono text-xs">
                      {t.timestamp ? fmtDateTimeCst(t.timestamp) : "—"}
                    </TableCell>
                    <TableCell className="max-w-[120px] truncate font-mono text-xs">
                      {(t.session_slug ?? "").replace("btc-updown-15m-", "")}
                    </TableCell>
                    <TableCell>
                      <Badge variant="outline" className={t.side === "BUY" ? "text-green-600" : "text-red-600"}>
                        {t.side}
                      </Badge>
                    </TableCell>
                    <TableCell className="text-right font-mono">{t.filled_shares.toFixed(2)}</TableCell>
                    <TableCell className="text-right font-mono">{t.avg_price.toFixed(4)}</TableCell>
                    <TableCell className="text-right font-mono">{fmtUsd(t.total_cost)}</TableCell>
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
