import { useState, useCallback, useRef, useEffect, useMemo } from "react"
import { useParams, Link } from "react-router-dom"
import { useQuery, useMutation, keepPreviousData } from "@tanstack/react-query"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Separator } from "@/components/ui/separator"
import { Skeleton } from "@/components/ui/skeleton"
import { ScrollArea } from "@/components/ui/scroll-area"
import { Alert, AlertDescription } from "@/components/ui/alert"
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { cn } from "@/lib/utils"
import ReplayControls from "@/components/ReplayControls"
import {
  fetchReplayTimeline,
  fetchReplaySnapshot,
  createReplaySession,
  executeReplayTrade,
  fetchArchive,
} from "@/api/client"
import type {
  ReplayTimeline,
  ReplaySnapshot,
  ReplaySession,
  ArchivedEvent,
} from "@/types"

function fmtTs(iso: string): string {
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

// ── Orderbook level row with depth bar (mirrors OrderbookView) ──────────────

function LevelRow({
  price,
  size,
  maxSize,
  side,
}: {
  price: number
  size: number
  maxSize: number
  side: "bid" | "ask"
}) {
  const pct = maxSize > 0 ? (size / maxSize) * 100 : 0
  return (
    <div className="relative flex items-center justify-between px-2 py-0.5 text-xs font-mono">
      <div
        className={cn(
          "absolute inset-y-0 opacity-15",
          side === "bid" ? "right-0 bg-chart-2" : "left-0 bg-chart-1",
        )}
        style={{ width: `${pct}%` }}
      />
      <span
        className={cn(
          "relative z-10",
          side === "bid" ? "text-emerald-600" : "text-rose-600",
        )}
      >
        {(price * 100).toFixed(1)}¢
      </span>
      <span className="relative z-10 text-muted-foreground">
        {size.toFixed(0)}
      </span>
    </div>
  )
}

// ── Price mini-chart (canvas, no extra deps) ────────────────────────────────

interface PriceMiniChartProps {
  timeline: ReplayTimeline
  currentIndex: number
  midPrice: number
}

function PriceMiniChart({ timeline, currentIndex, midPrice }: PriceMiniChartProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const [priceHistory, setPriceHistory] = useState<{ idx: number; mid: number }[]>([])

  useEffect(() => {
    if (!midPrice || midPrice === 0) return
    setPriceHistory((prev) => {
      if (prev.length > 0 && prev[prev.length - 1].idx === currentIndex) return prev
      const trimmed = prev.filter((p) => p.idx <= currentIndex)
      return [...trimmed, { idx: currentIndex, mid: midPrice }]
    })
  }, [currentIndex, midPrice])

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas || priceHistory.length < 2) return
    const ctx = canvas.getContext("2d")
    if (!ctx) return

    const dpr = window.devicePixelRatio || 1
    const w = canvas.clientWidth
    const h = canvas.clientHeight
    canvas.width = w * dpr
    canvas.height = h * dpr
    ctx.scale(dpr, dpr)
    ctx.clearRect(0, 0, w, h)

    const prices = priceHistory.map((p) => p.mid)
    const minP = Math.min(...prices)
    const maxP = Math.max(...prices)
    const range = maxP - minP || 0.001
    const total = timeline.timestamps.length

    ctx.beginPath()
    ctx.strokeStyle = "#3b82f6"
    ctx.lineWidth = 1.5
    priceHistory.forEach((point, i) => {
      const x = (point.idx / Math.max(total - 1, 1)) * w
      const y = h - ((point.mid - minP) / range) * (h - 8) - 4
      if (i === 0) ctx.moveTo(x, y)
      else ctx.lineTo(x, y)
    })
    ctx.stroke()

    // Current position marker
    const cx = (currentIndex / Math.max(total - 1, 1)) * w
    ctx.beginPath()
    ctx.strokeStyle = "#ef4444"
    ctx.lineWidth = 1
    ctx.setLineDash([3, 3])
    ctx.moveTo(cx, 0)
    ctx.lineTo(cx, h)
    ctx.stroke()
    ctx.setLineDash([])

    // Labels
    ctx.fillStyle = "#888"
    ctx.font = "10px monospace"
    ctx.textAlign = "left"
    ctx.fillText(`${(maxP * 100).toFixed(1)}¢`, 2, 12)
    ctx.fillText(`${(minP * 100).toFixed(1)}¢`, 2, h - 2)
  }, [priceHistory, currentIndex, timeline.timestamps.length])

  return (
    <canvas
      ref={canvasRef}
      className="h-32 w-full"
      style={{ display: "block" }}
    />
  )
}

// ── Main page ───────────────────────────────────────────────────────────────

export default function ReplayPage() {
  const { slug } = useParams<{ slug: string }>()
  const [currentIndex, setCurrentIndex] = useState(0)
  const [session, setSession] = useState<ReplaySession | null>(null)
  const [tradeAmount, setTradeAmount] = useState("")

  // Load archive meta
  const { data: archive } = useQuery<ArchivedEvent>({
    queryKey: ["archive", slug],
    queryFn: () => fetchArchive(slug!),
    enabled: !!slug,
  })

  // Load timeline
  const { data: timeline, isLoading: timelineLoading } = useQuery<ReplayTimeline>({
    queryKey: ["replayTimeline", slug],
    queryFn: () => fetchReplayTimeline(slug!),
    enabled: !!slug,
  })

  // Load snapshot — keepPreviousData prevents flickering on index change
  const currentTs = timeline?.timestamps[currentIndex] ?? ""
  const { data: snapshot } = useQuery<ReplaySnapshot>({
    queryKey: ["replaySnapshot", slug, currentTs],
    queryFn: () => fetchReplaySnapshot(slug!, currentTs),
    enabled: !!slug && !!currentTs,
    staleTime: Infinity,
    placeholderData: keepPreviousData,
  })

  // Create replay session
  const createSessionMutation = useMutation({
    mutationFn: () => createReplaySession(slug!, 10000),
    onSuccess: (data) => setSession(data),
  })

  // Execute trade in replay
  const tradeMutation = useMutation({
    mutationFn: (params: { side: string }) => {
      if (!session || !currentTs || !archive?.token_ids?.[0]) {
        return Promise.reject(new Error("Missing session/timestamp/token"))
      }
      return executeReplayTrade(
        slug!,
        session.session_id,
        currentTs,
        archive.token_ids[0],
        params.side,
        parseFloat(tradeAmount),
      )
    },
    onSuccess: (trade) => {
      if (session) {
        setSession({
          ...session,
          balance: trade.balance_after,
          trades: [...session.trades, trade],
        })
      }
      setTradeAmount("")
    },
  })

  const handleSeek = useCallback((index: number) => {
    setCurrentIndex(index)
  }, [])

  // ── Derived orderbook data ───────────────────────────────
  const { asks, bids, maxSize } = useMemo(() => {
    const bidPrices = snapshot?.bid_prices ?? []
    const bidSizes = snapshot?.bid_sizes ?? []
    const askPrices = snapshot?.ask_prices ?? []
    const askSizes = snapshot?.ask_sizes ?? []

    const b = bidPrices.slice(0, 15).map((p, i) => ({
      price: parseFloat(String(p)),
      size: parseFloat(String(bidSizes[i] ?? "0")),
    }))
    const a = askPrices
      .slice(0, 15)
      .map((p, i) => ({
        price: parseFloat(String(p)),
        size: parseFloat(String(askSizes[i] ?? "0")),
      }))
      .reverse()

    const allSizes = [...a.map((l) => l.size), ...b.map((l) => l.size)]
    return { asks: a, bids: b, maxSize: Math.max(...allSizes, 1) }
  }, [snapshot?.bid_prices, snapshot?.bid_sizes, snapshot?.ask_prices, snapshot?.ask_sizes])

  const trades = snapshot?.trades ?? []
  const recentTrades = useMemo(
    () => trades.slice(-30).reverse(),
    [trades],
  )

  // ── Loading state ────────────────────────────────────────
  if (timelineLoading) {
    return (
      <div className="flex flex-col gap-4">
        <Skeleton className="h-8 w-64" />
        <Skeleton className="h-32 w-full rounded-lg" />
        <Skeleton className="h-[400px] w-full rounded-lg" />
      </div>
    )
  }

  if (!timeline || timeline.timestamps.length === 0) {
    return (
      <div className="flex flex-col items-center gap-4 py-12">
        <p className="text-muted-foreground">没有找到该场次的归档数据</p>
        <Button variant="outline" asChild>
          <Link to="/">返回事件列表</Link>
        </Button>
      </div>
    )
  }

  const mid = snapshot?.mid_price ?? 0
  const bestBid = snapshot?.best_bid ?? 0
  const bestAsk = snapshot?.best_ask ?? 0
  const spread = snapshot?.spread ?? 0

  return (
    <div className="flex flex-col gap-4">
      {/* ── Header ──────────────────────────────────────────── */}
      <div className="flex items-center gap-2">
        <Button variant="ghost" size="sm" asChild className="px-2">
          <Link to="/">← Events</Link>
        </Button>
        <Separator orientation="vertical" className="h-4" />
        <h1 className="text-lg font-semibold">回放: {archive?.title ?? slug}</h1>
        <Badge variant="secondary">历史回放</Badge>
        <Badge variant="outline" className="font-mono text-xs">
          {timeline.total_snapshots} 快照 · {timeline.total_trades} 成交
        </Badge>
      </div>

      {/* ── Replay Controls ─────────────────────────────────── */}
      <ReplayControls
        timeline={timeline}
        currentIndex={currentIndex}
        onSeek={handleSeek}
      />

      {/* ── Main layout ─────────────────────────────────────── */}
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-12">
        {/* ─── Left column (8/12) ─────────────────────────────── */}
        <div className="flex flex-col gap-4 lg:col-span-8">

          {/* 1) Price indicators — single compact card */}
          <Card>
            <CardContent className="p-4">
              <div className="grid grid-cols-4 gap-4 text-center">
                <div>
                  <div className="text-xs text-muted-foreground">Mid</div>
                  <div className="text-xl font-bold font-mono tabular-nums">
                    {mid ? `${(mid * 100).toFixed(1)}¢` : "—"}
                  </div>
                </div>
                <div>
                  <div className="text-xs text-muted-foreground">Best Bid</div>
                  <div className="text-xl font-bold font-mono tabular-nums text-emerald-600">
                    {bestBid ? `${(bestBid * 100).toFixed(1)}¢` : "—"}
                  </div>
                </div>
                <div>
                  <div className="text-xs text-muted-foreground">Best Ask</div>
                  <div className="text-xl font-bold font-mono tabular-nums text-rose-600">
                    {bestAsk ? `${(bestAsk * 100).toFixed(1)}¢` : "—"}
                  </div>
                </div>
                <div>
                  <div className="text-xs text-muted-foreground">Spread</div>
                  <div className="text-xl font-bold font-mono tabular-nums">
                    {spread ? `${(spread * 100).toFixed(2)}¢` : "—"}
                  </div>
                </div>
              </div>
            </CardContent>
          </Card>

          {/* 2) Price mini-chart */}
          <Card>
            <CardHeader className="pb-2">
              <div className="flex items-center justify-between">
                <CardTitle className="text-sm">价格走势</CardTitle>
                {mid > 0 && (
                  <span className="text-xs font-mono text-muted-foreground tabular-nums">
                    当前 {(mid * 100).toFixed(1)}¢
                  </span>
                )}
              </div>
            </CardHeader>
            <CardContent className="p-3 pt-0">
              <PriceMiniChart
                timeline={timeline}
                currentIndex={currentIndex}
                midPrice={mid}
              />
            </CardContent>
          </Card>

          {/* 3) Orderbook with depth bars */}
          <Card>
            <CardHeader className="pb-2">
              <div className="flex items-center justify-between">
                <CardTitle className="text-sm">Orderbook</CardTitle>
                <span className="text-xs text-muted-foreground">
                  Spread: {spread ? `${(spread * 100).toFixed(1)}¢` : "—"}
                </span>
              </div>
              <div className="flex justify-between px-2 text-[10px] text-muted-foreground">
                <span>Price</span>
                <span>Size</span>
              </div>
            </CardHeader>
            <CardContent className="p-0">
              <ScrollArea className="h-72">
                <div className="flex flex-col">
                  {asks.length > 0 ? (
                    asks.map((level, i) => (
                      <LevelRow
                        key={`a-${i}`}
                        price={level.price}
                        size={level.size}
                        maxSize={maxSize}
                        side="ask"
                      />
                    ))
                  ) : (
                    <div className="py-6 text-center text-xs text-muted-foreground">
                      暂无卖单数据
                    </div>
                  )}
                  {/* Mid price separator */}
                  <div className="border-y bg-muted/50 px-2 py-1 text-center text-xs font-medium tabular-nums">
                    Mid: {mid ? `${(mid * 100).toFixed(1)}¢` : "—"}
                  </div>
                  {bids.length > 0 ? (
                    bids.map((level, i) => (
                      <LevelRow
                        key={`b-${i}`}
                        price={level.price}
                        size={level.size}
                        maxSize={maxSize}
                        side="bid"
                      />
                    ))
                  ) : (
                    <div className="py-6 text-center text-xs text-muted-foreground">
                      暂无买单数据
                    </div>
                  )}
                </div>
              </ScrollArea>
            </CardContent>
          </Card>

          {/* 4) Trades activity */}
          <Card>
            <CardHeader className="pb-2">
              <div className="flex items-center justify-between">
                <CardTitle className="text-sm">交易活动</CardTitle>
                <Badge variant="outline" className="text-xs font-mono">
                  {trades.length}
                </Badge>
              </div>
            </CardHeader>
            <CardContent className="p-0">
              {recentTrades.length > 0 ? (
                <ScrollArea className="h-48">
                  <div className="flex flex-col">
                    {recentTrades.map((t, i) => (
                      <div
                        key={`trade-${i}`}
                        className="flex items-center justify-between border-b px-3 py-1 text-xs last:border-b-0"
                      >
                        <span className="font-mono text-muted-foreground w-16">
                          {fmtTs(t.timestamp)}
                        </span>
                        <Badge
                          variant={t.side === "BUY" ? "default" : "secondary"}
                          className={cn(
                            "text-xs px-1.5 py-0",
                            t.side === "BUY"
                              ? "bg-emerald-600 hover:bg-emerald-700"
                              : "bg-rose-600 hover:bg-rose-700 text-white",
                          )}
                        >
                          {t.side === "BUY" ? "↑买" : "↓卖"}
                        </Badge>
                        <span className="font-mono text-right w-16">
                          {(t.price * 100).toFixed(1)}¢
                        </span>
                        <span className="font-mono text-right text-muted-foreground w-12">
                          {t.size.toFixed(0)}
                        </span>
                      </div>
                    ))}
                  </div>
                </ScrollArea>
              ) : (
                <div className="py-6 text-center text-xs text-muted-foreground">
                  暂无交易数据
                </div>
              )}
            </CardContent>
          </Card>
        </div>

        {/* ─── Right column (4/12) — replay trading panel ─────── */}
        <div className="flex flex-col gap-4 lg:col-span-4 lg:sticky lg:top-4 lg:self-start">
          {!session ? (
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm">回放交易</CardTitle>
              </CardHeader>
              <CardContent>
                <p className="mb-3 text-xs text-muted-foreground">
                  创建独立交易会话，在历史场景中模拟交易
                </p>
                <Button
                  className="w-full"
                  onClick={() => createSessionMutation.mutate()}
                  disabled={createSessionMutation.isPending}
                >
                  创建回放会话 ($10,000)
                </Button>
              </CardContent>
            </Card>
          ) : (
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm">回放交易</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="flex flex-col gap-3">
                  {/* Balance */}
                  <div className="flex justify-between text-sm">
                    <span className="text-muted-foreground">余额</span>
                    <span className="font-mono font-medium">
                      ${session.balance.toFixed(2)}
                    </span>
                  </div>

                  <Separator />

                  {/* Trade form */}
                  <div className="flex flex-col gap-1.5">
                    <label className="text-xs text-muted-foreground">份数</label>
                    <Input
                      type="number"
                      placeholder="0"
                      min={0}
                      step={1}
                      value={tradeAmount}
                      onChange={(e) => setTradeAmount(e.target.value)}
                    />
                  </div>

                  <div className="grid grid-cols-2 gap-2">
                    <Button
                      size="sm"
                      className="bg-emerald-600 hover:bg-emerald-700 text-white"
                      disabled={
                        !tradeAmount ||
                        parseFloat(tradeAmount) <= 0 ||
                        tradeMutation.isPending
                      }
                      onClick={() => tradeMutation.mutate({ side: "BUY" })}
                    >
                      买入
                    </Button>
                    <Button
                      size="sm"
                      className="bg-rose-600 hover:bg-rose-700 text-white"
                      disabled={
                        !tradeAmount ||
                        parseFloat(tradeAmount) <= 0 ||
                        tradeMutation.isPending
                      }
                      onClick={() => tradeMutation.mutate({ side: "SELL" })}
                    >
                      卖出
                    </Button>
                  </div>

                  {tradeMutation.isError && (
                    <Alert variant="destructive">
                      <AlertDescription className="text-xs">
                        {(tradeMutation.error as Error).message}
                      </AlertDescription>
                    </Alert>
                  )}

                  {/* Positions */}
                  {Object.keys(session.positions).length > 0 && (
                    <>
                      <Separator />
                      <div className="text-xs font-medium">持仓</div>
                      {Object.entries(session.positions).map(([tid, pos]) => (
                        <div key={tid} className="flex justify-between text-xs">
                          <span className="truncate text-muted-foreground">
                            {tid.slice(0, 8)}…
                          </span>
                          <span className="font-mono">
                            {pos.shares.toFixed(2)} @ {(pos.avg_cost * 100).toFixed(1)}¢
                          </span>
                        </div>
                      ))}
                    </>
                  )}

                  {/* Trade history */}
                  {session.trades.length > 0 && (
                    <>
                      <Separator />
                      <div className="text-xs font-medium">
                        交易记录 ({session.trades.length})
                      </div>
                      <ScrollArea className="max-h-40">
                        {session.trades.map((t, i) => (
                          <div
                            key={i}
                            className="flex items-center justify-between py-0.5 text-xs"
                          >
                            <span className="font-mono text-muted-foreground">
                              {fmtTs(t.timestamp)}
                            </span>
                            <Badge
                              variant={t.side === "BUY" ? "default" : "secondary"}
                              className={cn(
                                "text-xs",
                                t.side === "BUY"
                                  ? "bg-emerald-600"
                                  : "bg-rose-600 text-white",
                              )}
                            >
                              {t.side}
                            </Badge>
                            <span className="font-mono">
                              {t.amount.toFixed(1)} @ {(t.avg_price * 100).toFixed(1)}¢
                            </span>
                          </div>
                        ))}
                      </ScrollArea>
                    </>
                  )}
                </div>
              </CardContent>
            </Card>
          )}
        </div>
      </div>
    </div>
  )
}
