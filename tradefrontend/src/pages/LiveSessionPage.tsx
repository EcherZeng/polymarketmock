import { useState } from "react"
import { useLiveWs } from "@/hooks/useLiveWs"
import { useConfig } from "@/hooks/useTradeData"
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Separator } from "@/components/ui/separator"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { cn, fmtUsd, fmtTimeCst } from "@/lib/utils"
import type { SessionState, TokenMarket } from "@/types"
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
  ReferenceLine,
} from "recharts"
import { Activity, Wifi, WifiOff, Timer, TrendingUp, TrendingDown, Settings2, X } from "lucide-react"

const stateColors: Record<SessionState, string> = {
  discovered: "bg-blue-100 text-blue-700 dark:bg-blue-900 dark:text-blue-300",
  preparing: "bg-yellow-100 text-yellow-700 dark:bg-yellow-900 dark:text-yellow-300",
  active: "bg-green-100 text-green-700 dark:bg-green-900 dark:text-green-300",
  closing: "bg-orange-100 text-orange-700 dark:bg-orange-900 dark:text-orange-300",
  settled: "bg-muted text-muted-foreground",
  skipped: "bg-muted text-muted-foreground",
  error: "bg-red-100 text-red-700 dark:bg-red-900 dark:text-red-300",
}

// ── Helpers ──────────────────────────────────────────────────────────────────

/** Parse session slug → start epoch (seconds) */
function parseSlugEpoch(slug: string | undefined): number | null {
  if (!slug) return null
  const m = slug.match(/(\d{10})$/)
  return m ? Number(m[1]) : null
}

/** Generate 15-minute tick values (epoch) every 3 minutes */
function generate15mTicks(startEpoch: number): number[] {
  const ticks: number[] = []
  for (let i = 0; i <= 15; i += 3) {
    ticks.push(startEpoch + i * 60)
  }
  return ticks
}

/** Convert ISO timestamp to epoch seconds */
function isoToEpoch(iso: string): number {
  return Math.floor(new Date(iso).getTime() / 1000)
}

/** Epoch → HH:mm label in CST */
function epochToLabel(ep: number): string {
  const d = new Date(ep * 1000)
  return d.toLocaleTimeString("zh-CN", {
    timeZone: "Asia/Shanghai",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  })
}

function formatTime(iso: string): string {
  if (!iso) return ""
  try {
    return fmtTimeCst(iso)
  } catch {
    return iso.slice(11, 19)
  }
}

// ── Strategy Detail Panel ────────────────────────────────────────────────────

function StrategyDetailPanel({ onClose }: { onClose: () => void }) {
  const { data: config } = useConfig()
  if (!config) return null

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <CardTitle className="text-base">策略详情</CardTitle>
          <Button variant="ghost" size="icon" onClick={onClose}><X className="h-4 w-4" /></Button>
        </div>
        <CardDescription>当前运行的实时交易策略及其参数</CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        {config.strategy && config.strategy.length > 0 && (
          <div>
            <p className="text-sm text-muted-foreground mb-1">策略名称</p>
            <div className="flex flex-wrap gap-2">
              {config.strategy.map((s) => (
                <Badge key={s.name} variant="outline" className="font-mono">{s.name}</Badge>
              ))}
            </div>
            {config.strategy.map((s) => (
              s.description && (
                <p key={s.name} className="text-xs text-muted-foreground mt-1">{s.description} · v{s.version}</p>
              )
            ))}
          </div>
        )}
        {config.current_config && Object.keys(config.current_config).length > 0 && (
          <div>
            <p className="text-sm text-muted-foreground mb-2">当前参数</p>
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
  )
}

// ── Exported for reuse in DashboardPage ──────────────────────────────────────
export { StrategyDetailPanel }

// ── Main Page ────────────────────────────────────────────────────────────────

export default function LiveSessionPage() {
  const { connected, session, btcPrices, market, upPrices, downPrices, trades } = useLiveWs()
  const [showStrategy, setShowStrategy] = useState(false)

  const { data: config } = useConfig()

  const currentSlot = session?.current_session
  const nextSlot = session?.next_session

  // Determine 15-minute time window from current session slug
  const startEpoch = parseSlugEpoch(currentSlot?.slug)
  const endEpoch = startEpoch ? startEpoch + 900 : null

  // X-axis ticks (every 3 min for 15 min window)
  const xTicks = startEpoch ? generate15mTicks(startEpoch) : []
  const xDomain: [number, number] | undefined =
    startEpoch && endEpoch ? [startEpoch, endEpoch] : undefined

  // BTC chart data — map to epoch, filter to 15-min window
  const btcChartData = btcPrices
    .filter((p) => {
      if (!startEpoch || !endEpoch) return true
      const ep = isoToEpoch(p.timestamp)
      return ep >= startEpoch && ep <= endEpoch
    })
    .map((p) => ({ epoch: isoToEpoch(p.timestamp), price: p.price }))

  const latestBtc = btcPrices.length > 0 ? btcPrices[btcPrices.length - 1].price : 0

  // Poly chart data — merge up/down with epoch, filter to 15-min window
  const epochSet = new Set<number>()
  for (const p of upPrices) {
    const ep = isoToEpoch(p.timestamp)
    if (startEpoch && endEpoch && (ep < startEpoch || ep > endEpoch)) continue
    epochSet.add(ep)
  }
  for (const p of downPrices) {
    const ep = isoToEpoch(p.timestamp)
    if (startEpoch && endEpoch && (ep < startEpoch || ep > endEpoch)) continue
    epochSet.add(ep)
  }
  const sortedEpochs = [...epochSet].sort((a, b) => a - b)
  const upMap = new Map(upPrices.map((p) => [isoToEpoch(p.timestamp), p]))
  const downMap = new Map(downPrices.map((p) => [isoToEpoch(p.timestamp), p]))

  const polyChartData = sortedEpochs.map((ep) => {
    const up = upMap.get(ep)
    const down = downMap.get(ep)
    return {
      epoch: ep,
      up_mid: up?.mid ?? null,
      up_bid: up?.bid ?? null,
      up_ask: up?.ask ?? null,
      down_mid: down?.mid ?? null,
      down_bid: down?.bid ?? null,
      down_ask: down?.ask ?? null,
    }
  })

  // Token entries for price table
  const tokenEntries: { tokenId: string; data: TokenMarket }[] = market
    ? Object.entries(market.tokens).map(([tokenId, data]) => ({ tokenId, data }))
    : []

  return (
    <div className="flex flex-col gap-6">
      {/* ── Header ─────────────────────────── */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <h1 className="text-2xl font-semibold tracking-tight">实时场次监控</h1>
          {config?.strategy && config.strategy.length > 0 && (
            <Badge variant="outline" className="font-mono text-xs">
              {config.strategy.map((s) => s.name).join(", ")}
            </Badge>
          )}
          {config?.executor_mode && (
            <Badge className={cn(
              "text-xs",
              config.executor_mode === "real"
                ? "bg-red-100 text-red-700 dark:bg-red-900 dark:text-red-300"
                : "bg-blue-100 text-blue-700 dark:bg-blue-900 dark:text-blue-300",
            )}>
              {config.executor_mode === "real" ? "真实" : "模拟"}
            </Badge>
          )}
        </div>
        <div className="flex items-center gap-2">
          <Button variant="outline" size="sm" onClick={() => setShowStrategy(!showStrategy)}>
            <Settings2 className="mr-1 h-4 w-4" />
            策略详情
          </Button>
          {connected ? (
            <Badge className="bg-green-100 text-green-700 dark:bg-green-900 dark:text-green-300">
              <Wifi className="mr-1 h-3 w-3" /> 已连接
            </Badge>
          ) : (
            <Badge variant="destructive">
              <WifiOff className="mr-1 h-3 w-3" /> 断开
            </Badge>
          )}
        </div>
      </div>

      {/* ── Strategy Detail Panel ──────────── */}
      {showStrategy && <StrategyDetailPanel onClose={() => setShowStrategy(false)} />}

      {/* ── Session Status Cards ───────────── */}
      <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
        <Card>
          <CardHeader>
            <CardDescription>系统状态</CardDescription>
            <CardTitle className="flex items-center gap-2 text-base">
              <Activity className="h-4 w-4 text-primary" />
              {session?.paused ? (
                <Badge variant="outline">已暂停</Badge>
              ) : session?.running !== false ? (
                <Badge className="bg-green-100 text-green-700 dark:bg-green-900 dark:text-green-300">运行中</Badge>
              ) : (
                <Badge variant="outline">未运行</Badge>
              )}
              {session?.ws_connected && (
                <Badge variant="outline" className="text-xs">WS上游已连</Badge>
              )}
            </CardTitle>
          </CardHeader>
        </Card>

        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <CardDescription>当前 Session</CardDescription>
              {currentSlot && (
                <Badge className={cn("text-xs", stateColors[currentSlot.state])}>{currentSlot.state}</Badge>
              )}
            </div>
            <CardTitle className="text-sm font-mono">
              {currentSlot?.slug ?? "无活跃 Session"}
            </CardTitle>
          </CardHeader>
          {currentSlot && (
            <CardContent>
              <div className="flex items-center gap-2 text-sm text-muted-foreground">
                <Timer className="h-4 w-4" />
                <span>
                  剩余 {Math.floor(currentSlot.time_remaining_s / 60)}:
                  {String(Math.floor(currentSlot.time_remaining_s % 60)).padStart(2, "0")}
                </span>
                <span className="ml-auto">交易 {currentSlot.trades} 笔</span>
              </div>
            </CardContent>
          )}
        </Card>

        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <CardDescription>下一 Session</CardDescription>
              {nextSlot && (
                <Badge className={cn("text-xs", stateColors[nextSlot.state])}>{nextSlot.state}</Badge>
              )}
            </div>
            <CardTitle className="text-sm font-mono">
              {nextSlot?.slug ?? "等待发现"}
            </CardTitle>
          </CardHeader>
          {nextSlot && (
            <CardContent>
              <div className="flex items-center gap-2 text-sm text-muted-foreground">
                <Timer className="h-4 w-4" />
                <span>
                  距开始 {Math.floor(nextSlot.time_remaining_s / 60)}:
                  {String(Math.floor(nextSlot.time_remaining_s % 60)).padStart(2, "0")}
                </span>
              </div>
            </CardContent>
          )}
        </Card>
      </div>

      {/* ── BTC Price Chart (15-min fixed X-axis) ── */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <CardTitle className="text-base">BTC 实时价格</CardTitle>
              <CardDescription>Binance BTCUSDT · WebSocket · 15分钟窗口</CardDescription>
            </div>
            <span className="text-2xl font-semibold font-mono tabular-nums">
              ${latestBtc > 0 ? latestBtc.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 }) : "—"}
            </span>
          </div>
        </CardHeader>
        <CardContent>
          {btcChartData.length === 0 ? (
            <div className="flex h-48 items-center justify-center text-muted-foreground">
              等待 BTC 价格数据...
            </div>
          ) : (
            <ResponsiveContainer width="100%" height={280}>
              <LineChart data={btcChartData}>
                <CartesianGrid strokeDasharray="3 3" className="stroke-muted" />
                <XAxis
                  dataKey="epoch"
                  type="number"
                  domain={xDomain || ["dataMin", "dataMax"]}
                  ticks={xTicks.length > 0 ? xTicks : undefined}
                  tickFormatter={epochToLabel}
                  tick={{ fontSize: 10 }}
                />
                <YAxis
                  domain={["auto", "auto"]}
                  tick={{ fontSize: 10 }}
                  width={80}
                  tickFormatter={(v: number) => `$${v.toLocaleString()}`}
                />
                <Tooltip
                  labelFormatter={(ep: number) => epochToLabel(ep)}
                  formatter={(value: number) => [`$${value.toLocaleString(undefined, { minimumFractionDigits: 2 })}`, "BTC"]}
                  contentStyle={{ fontSize: 12 }}
                />
                {endEpoch && (
                  <ReferenceLine x={Math.floor(Date.now() / 1000)} stroke="hsl(var(--primary))" strokeDasharray="3 3" strokeWidth={1} />
                )}
                <Line type="monotone" dataKey="price" stroke="#f97316" strokeWidth={2} dot={false} isAnimationActive={false} />
              </LineChart>
            </ResponsiveContainer>
          )}
        </CardContent>
      </Card>

      {/* ── Poly Up/Down Price Chart (15-min fixed X-axis) ── */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Poly Up / Down 价格</CardTitle>
          <CardDescription>场次代币实时中间价 · 15分钟窗口</CardDescription>
        </CardHeader>
        <CardContent>
          {polyChartData.length === 0 ? (
            <div className="flex h-48 items-center justify-center text-muted-foreground">
              等待场次市场数据...
            </div>
          ) : (
            <ResponsiveContainer width="100%" height={280}>
              <LineChart data={polyChartData}>
                <CartesianGrid strokeDasharray="3 3" className="stroke-muted" />
                <XAxis
                  dataKey="epoch"
                  type="number"
                  domain={xDomain || ["dataMin", "dataMax"]}
                  ticks={xTicks.length > 0 ? xTicks : undefined}
                  tickFormatter={epochToLabel}
                  tick={{ fontSize: 10 }}
                />
                <YAxis
                  domain={[0, 1]}
                  tick={{ fontSize: 10 }}
                  width={50}
                  tickFormatter={(v: number) => v.toFixed(2)}
                />
                <Tooltip
                  labelFormatter={(ep: number) => epochToLabel(ep)}
                  formatter={(value: number | null, name: string) => [
                    value !== null ? value.toFixed(4) : "—",
                    name,
                  ]}
                  contentStyle={{ fontSize: 12 }}
                />
                <Legend />
                {endEpoch && (
                  <ReferenceLine x={Math.floor(Date.now() / 1000)} stroke="hsl(var(--primary))" strokeDasharray="3 3" strokeWidth={1} />
                )}
                <Line type="monotone" dataKey="up_mid" name="Up Mid" stroke="#22c55e" strokeWidth={2} dot={false} isAnimationActive={false} connectNulls />
                <Line type="monotone" dataKey="up_bid" name="Up Bid" stroke="#86efac" strokeWidth={1} strokeDasharray="3 3" dot={false} isAnimationActive={false} connectNulls />
                <Line type="monotone" dataKey="up_ask" name="Up Ask" stroke="#4ade80" strokeWidth={1} strokeDasharray="3 3" dot={false} isAnimationActive={false} connectNulls />
                <Line type="monotone" dataKey="down_mid" name="Down Mid" stroke="#ef4444" strokeWidth={2} dot={false} isAnimationActive={false} connectNulls />
                <Line type="monotone" dataKey="down_bid" name="Down Bid" stroke="#fca5a5" strokeWidth={1} strokeDasharray="3 3" dot={false} isAnimationActive={false} connectNulls />
                <Line type="monotone" dataKey="down_ask" name="Down Ask" stroke="#f87171" strokeWidth={1} strokeDasharray="3 3" dot={false} isAnimationActive={false} connectNulls />
              </LineChart>
            </ResponsiveContainer>
          )}
        </CardContent>
      </Card>

      {/* ── Up / Down Price Table ─────────────── */}
      <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
        {tokenEntries.map(({ tokenId, data }) => (
          <Card key={tokenId}>
            <CardHeader>
              <div className="flex items-center gap-2">
                {data.outcome === "Up" ? (
                  <TrendingUp className="h-4 w-4 text-green-600" />
                ) : (
                  <TrendingDown className="h-4 w-4 text-red-600" />
                )}
                <CardTitle className="text-base">{data.outcome} Token</CardTitle>
              </div>
              <CardDescription className="font-mono text-xs truncate">{tokenId}</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-2 gap-y-2 text-sm">
                <span className="text-muted-foreground">中间价</span>
                <span className="text-right font-mono font-semibold">{data.mid_price.toFixed(4)}</span>
                <span className="text-muted-foreground">Best Bid</span>
                <span className="text-right font-mono text-green-600">{data.best_bid.toFixed(4)}</span>
                <span className="text-muted-foreground">Best Ask</span>
                <span className="text-right font-mono text-red-600">{data.best_ask.toFixed(4)}</span>
                <span className="text-muted-foreground">Spread</span>
                <span className="text-right font-mono">{data.spread.toFixed(4)}</span>
                <span className="text-muted-foreground">锚定价</span>
                <span className="text-right font-mono">{data.anchor_price.toFixed(4)}</span>
              </div>

              <Separator className="my-3" />

              <div className="grid grid-cols-2 gap-4 text-xs">
                <div>
                  <p className="mb-1 font-medium text-green-600">Bids</p>
                  {data.bid_levels.length === 0 ? (
                    <p className="text-muted-foreground">无数据</p>
                  ) : (
                    <table className="w-full">
                      <tbody>
                        {data.bid_levels.map(([price, size], i) => (
                          <tr key={i}>
                            <td className="font-mono text-green-600">{price.toFixed(3)}</td>
                            <td className="text-right font-mono">{size.toFixed(1)}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  )}
                </div>
                <div>
                  <p className="mb-1 font-medium text-red-600">Asks</p>
                  {data.ask_levels.length === 0 ? (
                    <p className="text-muted-foreground">无数据</p>
                  ) : (
                    <table className="w-full">
                      <tbody>
                        {data.ask_levels.map(([price, size], i) => (
                          <tr key={i}>
                            <td className="font-mono text-red-600">{price.toFixed(3)}</td>
                            <td className="text-right font-mono">{size.toFixed(1)}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  )}
                </div>
              </div>
            </CardContent>
          </Card>
        ))}
        {tokenEntries.length === 0 && (
          <Card className="col-span-full">
            <CardContent className="py-8 text-center text-muted-foreground">
              等待活跃场次市场数据...
            </CardContent>
          </Card>
        )}
      </div>

      <Separator />

      {/* ── Trades Table ──────────────────────── */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">实时交易记录</CardTitle>
          <CardDescription>当前场次交易 · 实时推送</CardDescription>
        </CardHeader>
        <CardContent>
          {trades.length === 0 ? (
            <p className="py-4 text-center text-sm text-muted-foreground">暂无交易记录</p>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>时间</TableHead>
                  <TableHead>方向</TableHead>
                  <TableHead>Token</TableHead>
                  <TableHead className="text-right">数量</TableHead>
                  <TableHead className="text-right">均价</TableHead>
                  <TableHead className="text-right">成本</TableHead>
                  <TableHead className="text-right">手续费</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {trades.map((t, i) => (
                  <TableRow key={t.id ?? i}>
                    <TableCell className="font-mono text-xs">
                      {t.timestamp ? formatTime(t.timestamp) : "—"}
                    </TableCell>
                    <TableCell>
                      <Badge variant="outline" className={t.side === "BUY" ? "text-green-600" : "text-red-600"}>
                        {t.side}
                      </Badge>
                    </TableCell>
                    <TableCell className="max-w-[80px] truncate font-mono text-xs">
                      {t.token_id?.slice(-8) ?? "—"}
                    </TableCell>
                    <TableCell className="text-right font-mono">
                      {typeof t.filled_shares === "number" ? t.filled_shares.toFixed(2) : "—"}
                    </TableCell>
                    <TableCell className="text-right font-mono">
                      {typeof t.avg_price === "number" ? t.avg_price.toFixed(4) : "—"}
                    </TableCell>
                    <TableCell className="text-right font-mono">
                      {typeof t.total_cost === "number" ? fmtUsd(t.total_cost) : "—"}
                    </TableCell>
                    <TableCell className="text-right font-mono">
                      {typeof t.fees === "number" ? fmtUsd(t.fees, 4) : "—"}
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
