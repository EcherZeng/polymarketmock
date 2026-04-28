import { useState, useMemo } from "react"
import { useLiveWs } from "@/hooks/useLiveWs"
import { useConfigState } from "@/hooks/useTradeData"
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
import type { SessionState, TokenMarket, WsSessionStatus } from "@/types"
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
import { Activity, Wifi, WifiOff, Timer, TrendingUp, TrendingDown, Settings2, X, Layers } from "lucide-react"

const stateColors: Record<SessionState, string> = {
  pending: "bg-blue-100 text-blue-700 dark:bg-blue-900 dark:text-blue-300",
  active: "bg-green-100 text-green-700 dark:bg-green-900 dark:text-green-300",
  settling: "bg-orange-100 text-orange-700 dark:bg-orange-900 dark:text-orange-300",
  settled: "bg-muted text-muted-foreground",
}

// ── Helpers ──────────────────────────────────────────────────────────────────

/** Parse session slug → start epoch (seconds) */
function parseSlugEpoch(slug: string | undefined): number | null {
  if (!slug) return null
  const m = slug.match(/(\d{10})$/)
  return m ? Number(m[1]) : null
}

/** Generate 15-minute tick values (epoch) every 1 minute */
function generate15mTicks(startEpoch: number): number[] {
  const ticks: number[] = []
  for (let i = 0; i <= 15; i += 1) {
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

function StrategyDetailPanel({ onClose, session }: { onClose: () => void; session: WsSessionStatus | null }) {
  const { data: config } = useConfigState()

  if (!config) return null

  const presetName = config.active_preset_name
  const presetType = config.active_preset_type ?? "none"
  const cs = session?.current_session

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <CardTitle className="text-base">策略详情</CardTitle>
          <Button variant="ghost" size="icon" onClick={onClose}><X className="h-4 w-4" /></Button>
        </div>
        <CardDescription>
          {presetName
            ? `当前${presetType === "composite" ? "复合" : "单一"}策略：${presetName}`
            : "尚未加载策略"}
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        {/* Active composite strategy with branch match highlight */}
        {presetType === "composite" && config.composite_config && (
          <div className="rounded-md border border-purple-200 dark:border-purple-800 p-3 space-y-2">
            <div className="flex items-center gap-2">
              <Layers className="h-4 w-4 text-purple-600" />
              <Badge variant="outline" className="font-mono text-xs">{config.composite_config.composite_name}</Badge>
              <span className="text-xs text-muted-foreground">
                W1={config.composite_config.btc_windows.btc_trend_window_1}m W2={config.composite_config.btc_windows.btc_trend_window_2}m
              </span>
            </div>
            <div className="space-y-1.5">
              {config.composite_config.branches.map((b, i) => {
                const isMatched = cs?.matched_branch === b.label
                return (
                  <div key={i} className={cn(
                    "rounded border px-2 py-1.5 space-y-0.5",
                    isMatched && "border-purple-400 bg-purple-50/50 dark:bg-purple-950/20",
                  )}>
                    <div className="flex items-center gap-2 text-xs">
                      <Badge
                        variant={isMatched ? "default" : "outline"}
                        className={cn("font-mono", isMatched && "bg-purple-600 text-white")}
                      >
                        {b.label} ≥{b.min_momentum}
                      </Badge>
                      <span className="text-muted-foreground font-mono">{b.preset_name}</span>
                      {isMatched && <span className="text-purple-600 text-xs font-medium">← 当前场次</span>}
                    </div>
                    {b.config && Object.keys(b.config).length > 0 && (
                      <div className="flex flex-wrap gap-x-2 gap-y-0.5 pl-1">
                        {Object.entries(b.config).map(([k, v]) => (
                          <span key={k} className="text-xs text-muted-foreground font-mono">
                            {k}={String(v)}
                          </span>
                        ))}
                      </div>
                    )}
                  </div>
                )
              })}
            </div>
          </div>
        )}

        {/* Single strategy params */}
        {presetType === "single" && config.current_config && Object.keys(config.current_config).length > 0 && (
          <div>
            <div className="flex items-center gap-2 mb-2">
              <Badge variant="outline" className="font-mono">{presetName}</Badge>
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

        {/* BTC trend status for current session */}
        {cs && cs.btc_trend_computed && (
          <div className="rounded-md border p-3 space-y-1">
            <p className="text-sm font-medium flex items-center gap-2">
              BTC 趋势判定
              {cs.btc_trend_passed ? (
                <Badge className="bg-green-100 text-green-700 dark:bg-green-900 dark:text-green-300 text-xs">通过</Badge>
              ) : (
                <Badge variant="destructive" className="text-xs">未通过 — 跳过</Badge>
              )}
            </p>
            <div className="grid grid-cols-3 gap-2 text-xs md:grid-cols-6">
              <div>
                <span className="text-muted-foreground">P₀</span>
                <p className="font-mono font-medium">{cs.btc_p0 != null ? `$${cs.btc_p0.toLocaleString(undefined, { minimumFractionDigits: 2 })}` : "—"}</p>
              </div>
              <div>
                <span className="text-muted-foreground">P<sub>W1</sub></span>
                <p className="font-mono font-medium">{cs.btc_p_w1 != null ? `$${cs.btc_p_w1.toLocaleString(undefined, { minimumFractionDigits: 2 })}` : "—"}</p>
              </div>
              <div>
                <span className="text-muted-foreground">P<sub>W2</sub></span>
                <p className="font-mono font-medium">{cs.btc_p_w2 != null ? `$${cs.btc_p_w2.toLocaleString(undefined, { minimumFractionDigits: 2 })}` : "—"}</p>
              </div>
              <div>
                <span className="text-muted-foreground">a₁ (P₀→W1)</span>
                <p className={cn("font-mono font-medium", cs.btc_a1 != null && cs.btc_a1 > 0 ? "text-green-600" : cs.btc_a1 != null && cs.btc_a1 < 0 ? "text-red-600" : "")}>
                  {cs.btc_a1 != null ? (cs.btc_a1 >= 0 ? "+" : "") + (cs.btc_a1 * 100).toFixed(4) + "%" : "—"}
                </p>
              </div>
              <div>
                <span className="text-muted-foreground">a₂ (W1→W2)</span>
                <p className={cn("font-mono font-medium", cs.btc_a2 != null && cs.btc_a2 > 0 ? "text-green-600" : cs.btc_a2 != null && cs.btc_a2 < 0 ? "text-red-600" : "")}>
                  {cs.btc_a2 != null ? (cs.btc_a2 >= 0 ? "+" : "") + (cs.btc_a2 * 100).toFixed(4) + "%" : "—"}
                </p>
              </div>
              <div>
                <span className="text-muted-foreground">|a₁+a₂| / 方向 / 分支</span>
                <p className="font-mono font-medium">
                  {cs.btc_amplitude != null ? (cs.btc_amplitude * 100).toFixed(4) + "%" : "—"}
                  {" "}{cs.btc_direction ?? "—"}
                  {cs.matched_branch ? ` · ${cs.matched_branch}` : ""}
                </p>
              </div>
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

  const { data: config } = useConfigState()

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

  // ── Real-time sita (momentum) computation ──────────────────────────
  const sitaInfo = useMemo(() => {
    if (!startEpoch) return null

    // Read w1/w2 from composite config or single-strategy config
    let w1: number | null = null
    let w2: number | null = null
    if (config?.composite_config) {
      w1 = config.composite_config.btc_windows.btc_trend_window_1
      w2 = config.composite_config.btc_windows.btc_trend_window_2
    } else if (config?.current_config) {
      const cw1 = config.current_config.btc_trend_window_1
      const cw2 = config.current_config.btc_trend_window_2
      if (typeof cw1 === "number" && typeof cw2 === "number") {
        w1 = cw1
        w2 = cw2
      }
    }
    if (w1 == null || w2 == null) return null

    const w1Epoch = startEpoch + w1 * 60
    const w2Epoch = startEpoch + w2 * 60
    const nowEpoch = Math.floor(Date.now() / 1000)
    const w1Passed = nowEpoch >= w1Epoch
    const w2Passed = nowEpoch >= w2Epoch

    // After backend has computed BTC trend (post w2), use authoritative
    // backend values (kline-open based, matching Strategy service).
    const cs = currentSlot
    if (cs?.btc_trend_computed && cs.btc_p0 != null) {
      const bp0 = cs.btc_p0
      const bpW1 = cs.btc_p_w1 ?? null
      const bpW2 = cs.btc_p_w2 ?? null
      const ba1 = cs.btc_a1 ?? null
      const ba2 = cs.btc_a2 ?? null
      const bAmp = ba1 != null && ba2 != null ? Math.abs(ba1 + ba2) : null
      const bDir = ba1 != null && ba2 != null && ba1 + ba2 !== 0 ? (ba1 + ba2 > 0 ? "up" : "down") : null
      return { w1Epoch, w2Epoch, p0: bp0, pW1: bpW1, pW2: bpW2, a1: ba1, a2: ba2, amplitude: bAmp, direction: bDir, w1Passed, w2Passed }
    }

    // Before backend computes: real-time estimate from WebSocket prices.
    // Use _closest price to each window boundary (matching Strategy's
    // _closest_open logic).
    const closestPrice = (targetEpoch: number): number | null => {
      let best: number | null = null
      let bestDist = Infinity
      for (const p of btcPrices) {
        const ep = isoToEpoch(p.timestamp)
        const dist = Math.abs(ep - targetEpoch)
        if (dist < bestDist) {
          bestDist = dist
          best = p.price
        }
      }
      return best
    }

    // P0 = price closest to session start
    const p0 = closestPrice(startEpoch)
    if (p0 == null || p0 === 0) return { w1Epoch, w2Epoch, p0: null, pW1: null, pW2: null, a1: null, a2: null, amplitude: null, direction: null, w1Passed, w2Passed }

    // P_W1: locked to closest price once W1 passes; else use latest
    let pW1: number | null = null
    if (w1Passed) {
      pW1 = closestPrice(w1Epoch)
    }

    // P_W2: locked to closest price once W2 passes; else null
    let pW2: number | null = null
    if (w2Passed) {
      pW2 = closestPrice(w2Epoch)
    }

    // a1: before W1 evolves with latest price; after W1 locked
    const a1Price = w1Passed && pW1 != null ? pW1 : latestBtc
    const a1 = p0 > 0 ? (a1Price - p0) / p0 : null

    // a2: not computed until W1; between W1→W2 evolves with latest; after W2 locked
    let a2: number | null = null
    if (w1Passed && pW1 != null && pW1 > 0) {
      const a2Price = w2Passed && pW2 != null ? pW2 : latestBtc
      a2 = (a2Price - pW1) / pW1
    }

    // amplitude = |a1 + a2| when both available
    const amplitude = a1 != null && a2 != null ? Math.abs(a1 + a2) : (a1 != null ? Math.abs(a1) : null)
    const direction = a1 != null && a2 != null && a1 + a2 !== 0 ? (a1 + a2 > 0 ? "up" : "down") : null

    return { w1Epoch, w2Epoch, p0, pW1, pW2, a1, a2, amplitude, direction, w1Passed, w2Passed }
  }, [btcPrices, startEpoch, config?.composite_config, config?.current_config, latestBtc, currentSlot])

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
          {config?.active_preset_name && (
            <Badge variant="outline" className="font-mono text-xs">
              {config.active_preset_type === "composite" ? "复合: " : ""}{config.active_preset_name}
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
      {showStrategy && <StrategyDetailPanel onClose={() => setShowStrategy(false)} session={session} />}

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
              {/* BTC trend status from backend */}
              {currentSlot.btc_trend_computed && (
                <div className="mt-2 flex items-center gap-2 text-xs flex-wrap">
                  <span className="text-muted-foreground">BTC趋势:</span>
                  {currentSlot.btc_trend_passed ? (
                    <Badge className="bg-green-100 text-green-700 dark:bg-green-900 dark:text-green-300 text-xs">
                      通过 {currentSlot.btc_direction === "UP" ? "↑" : "↓"} |a₁+a₂|={currentSlot.btc_amplitude != null ? (currentSlot.btc_amplitude * 100).toFixed(3) + "%" : ""}
                    </Badge>
                  ) : (
                    <Badge variant="destructive" className="text-xs">未通过 — 跳过</Badge>
                  )}
                  {currentSlot.btc_a1 != null && currentSlot.btc_a2 != null && (
                    <span className="font-mono text-muted-foreground">
                      a₁={((currentSlot.btc_a1) * 100).toFixed(4)}% a₂={((currentSlot.btc_a2) * 100).toFixed(4)}%
                    </span>
                  )}
                  {currentSlot.matched_branch && (
                    <Badge variant="outline" className="font-mono text-xs">{currentSlot.matched_branch}</Badge>
                  )}
                </div>
              )}
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
          {/* Real-time sita indicators */}
          {sitaInfo && sitaInfo.p0 != null && (
            <div className="mt-2 grid grid-cols-3 gap-2 rounded-md border p-2 text-xs md:grid-cols-7">
              <div>
                <span className="text-muted-foreground">P₀</span>
                <p className="font-mono font-medium">${sitaInfo.p0.toLocaleString(undefined, { minimumFractionDigits: 2 })}</p>
              </div>
              <div>
                <span className="text-muted-foreground">P<sub>W1</sub></span>
                <p className="font-mono font-medium">
                  {sitaInfo.pW1 != null ? `$${sitaInfo.pW1.toLocaleString(undefined, { minimumFractionDigits: 2 })}` : "等待..."}
                </p>
              </div>
              <div>
                <span className="text-muted-foreground">P<sub>W2</sub></span>
                <p className="font-mono font-medium">
                  {sitaInfo.pW2 != null ? `$${sitaInfo.pW2.toLocaleString(undefined, { minimumFractionDigits: 2 })}` : "等待..."}
                </p>
              </div>
              <div>
                <span className="text-muted-foreground">a₁ (P₀→P<sub>W1</sub>){!sitaInfo.w1Passed ? " 实时" : ""}</span>
                <p className={cn("font-mono font-medium", sitaInfo.a1 != null && sitaInfo.a1 > 0 ? "text-green-600" : sitaInfo.a1 != null && sitaInfo.a1 < 0 ? "text-red-600" : "")}>
                  {sitaInfo.a1 != null ? (sitaInfo.a1 >= 0 ? "+" : "") + (sitaInfo.a1 * 100).toFixed(4) + "%" : "—"}
                </p>
              </div>
              <div>
                <span className="text-muted-foreground">a₂ (P<sub>W1</sub>→P<sub>W2</sub>){sitaInfo.w1Passed && !sitaInfo.w2Passed ? " 实时" : ""}</span>
                <p className={cn("font-mono font-medium", sitaInfo.a2 != null && sitaInfo.a2 > 0 ? "text-green-600" : sitaInfo.a2 != null && sitaInfo.a2 < 0 ? "text-red-600" : "")}>
                  {sitaInfo.a2 != null ? (sitaInfo.a2 >= 0 ? "+" : "") + (sitaInfo.a2 * 100).toFixed(4) + "%" : "—"}
                </p>
              </div>
              <div>
                <span className="text-muted-foreground">合计动量 |a₁+a₂|</span>
                <p className="font-mono font-semibold">
                  {sitaInfo.amplitude != null ? (sitaInfo.amplitude * 100).toFixed(4) + "%" : "—"}
                </p>
              </div>
              <div>
                <span className="text-muted-foreground">方向</span>
                <p className="font-mono font-semibold">
                  {sitaInfo.direction ? (
                    <span className={cn(sitaInfo.direction === "up" ? "text-green-600" : "text-red-600")}>
                      {sitaInfo.direction === "up" ? "↑ UP" : "↓ DOWN"}
                    </span>
                  ) : "—"}
                </p>
              </div>
            </div>
          )}
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
                  labelFormatter={(ep) => epochToLabel(Number(ep))}
                  formatter={(value) => [`$${Number(value).toLocaleString(undefined, { minimumFractionDigits: 2 })}`, "BTC"]}
                  contentStyle={{ fontSize: 12 }}
                />
                {endEpoch && (
                  <ReferenceLine x={Math.floor(Date.now() / 1000)} stroke="hsl(var(--primary))" strokeDasharray="3 3" strokeWidth={1} />
                )}
                {/* Window reference lines */}
                {sitaInfo?.w1Epoch && (
                  <ReferenceLine x={sitaInfo.w1Epoch} stroke="#8b5cf6" strokeDasharray="5 3" strokeWidth={1.5} label={{ value: "W1", position: "top", fontSize: 10, fill: "#8b5cf6" }} />
                )}
                {sitaInfo?.w2Epoch && (
                  <ReferenceLine x={sitaInfo.w2Epoch} stroke="#a855f7" strokeDasharray="5 3" strokeWidth={1.5} label={{ value: "W2", position: "top", fontSize: 10, fill: "#a855f7" }} />
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
                  labelFormatter={(ep) => epochToLabel(Number(ep))}
                  formatter={(value, name) => [
                    value != null ? Number(value).toFixed(4) : "—",
                    String(name),
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
