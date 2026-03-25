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
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip"
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

    // Bids: highest price first (already sorted from API)
    const b = bidPrices.slice(0, 15).map((p, i) => ({
      price: parseFloat(String(p)),
      size: parseFloat(String(bidSizes[i] ?? "0")),
    }))
    // Asks: lowest price first (already sorted from API)
    const a = askPrices.slice(0, 15).map((p, i) => ({
      price: parseFloat(String(p)),
      size: parseFloat(String(askSizes[i] ?? "0")),
    }))

    const allSizes = [...a.map((l) => l.size), ...b.map((l) => l.size)]
    return { asks: a, bids: b, maxSize: Math.max(...allSizes, 1) }
  }, [snapshot?.bid_prices, snapshot?.bid_sizes, snapshot?.ask_prices, snapshot?.ask_sizes])

  const trades = snapshot?.trades ?? []
  const recentTrades = useMemo(
    () => trades.slice(-30).reverse(),
    [trades],
  )

  // Map token_id to outcome label (UP/DOWN or Yes/No)
  const tokenIds = archive?.token_ids ?? []
  const outcomeLabel = useCallback(
    (tokenId: string) => {
      const idx = tokenIds.indexOf(tokenId)
      if (idx === 0) return "UP"
      if (idx === 1) return "DOWN"
      return tokenId.slice(0, 6) + "…"
    },
    [tokenIds],
  )
  const outcomeBadgeClass = useCallback(
    (tokenId: string) => {
      const idx = tokenIds.indexOf(tokenId)
      if (idx === 0) return "bg-emerald-100 text-emerald-700 border-emerald-300"
      if (idx === 1) return "bg-rose-100 text-rose-700 border-rose-300"
      return ""
    },
    [tokenIds],
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

          {/* 3) Orderbook — side-by-side Bids | Asks */}
          <Card>
            <CardHeader className="pb-2">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-1.5">
                  <CardTitle className="text-sm">挂单深度</CardTitle>
                  <TooltipProvider>
                    <Tooltip>
                      <TooltipTrigger asChild>
                        <span className="inline-flex h-4 w-4 cursor-help items-center justify-center rounded-full border text-[10px] text-muted-foreground">?</span>
                      </TooltipTrigger>
                      <TooltipContent side="right" className="max-w-md text-left">
                        <p className="font-medium">Orderbook 挂单深度</p>
                        <p className="mt-1">显示当前时间点市场上<b>尚未成交</b>的挂单。</p>
                        <p className="mt-1"><span className="text-emerald-400">Bids (买单)</span>：其他用户愿意以该价格买入的挂单量。</p>
                        <p><span className="text-rose-400">Asks (卖单)</span>：其他用户愿意以该价格卖出的挂单量。</p>
                        <p className="mt-1 text-muted">深度条宽度 = 该档位挂单量 ÷ 最大档位挂单量 × 100%</p>
                        <p className="mt-1 text-muted">Spread = Best Ask - Best Bid（买卖价差）</p>
                      </TooltipContent>
                    </Tooltip>
                  </TooltipProvider>
                </div>
                <span className="text-xs text-muted-foreground tabular-nums">
                  Spread: {spread ? `${(spread * 100).toFixed(1)}¢` : "—"}
                </span>
              </div>
            </CardHeader>
            <CardContent className="p-0">
              <div className="grid grid-cols-2 divide-x">
                {/* Bids (left) */}
                <div>
                  <div className="flex items-center justify-between border-b bg-muted/30 px-2 py-1">
                    <span className="text-[10px] font-medium text-emerald-600">Bids (买单)</span>
                    <div className="flex gap-6 text-[10px] text-muted-foreground">
                      <span>Price</span>
                      <span>Size</span>
                    </div>
                  </div>
                  <ScrollArea className="h-64">
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
                      <div className="py-8 text-center text-xs text-muted-foreground">
                        暂无买单
                      </div>
                    )}
                  </ScrollArea>
                </div>
                {/* Asks (right) */}
                <div>
                  <div className="flex items-center justify-between border-b bg-muted/30 px-2 py-1">
                    <span className="text-[10px] font-medium text-rose-600">Asks (卖单)</span>
                    <div className="flex gap-6 text-[10px] text-muted-foreground">
                      <span>Price</span>
                      <span>Size</span>
                    </div>
                  </div>
                  <ScrollArea className="h-64">
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
                      <div className="py-8 text-center text-xs text-muted-foreground">
                        暂无卖单
                      </div>
                    )}
                  </ScrollArea>
                </div>
              </div>
              {/* Mid price bar */}
              <div className="border-t bg-muted/50 px-2 py-1 text-center text-xs font-medium tabular-nums">
                Mid: {mid ? `${(mid * 100).toFixed(1)}¢` : "—"}
              </div>
            </CardContent>
          </Card>

          {/* 4) Trades activity — with outcome (UP/DOWN) */}
          <Card>
            <CardHeader className="pb-2">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-1.5">
                  <CardTitle className="text-sm">推断成交</CardTitle>
                  <TooltipProvider>
                    <Tooltip>
                      <TooltipTrigger asChild>
                        <span className="inline-flex h-4 w-4 cursor-help items-center justify-center rounded-full border text-[10px] text-muted-foreground">?</span>
                      </TooltipTrigger>
                      <TooltipContent side="right" className="max-w-md text-left">
                        <p className="font-medium">推断成交 (Inferred Trades)</p>
                        <p className="mt-1">通过对比相邻两次 Orderbook 快照（间隔 ~1秒）的差异推断出的真实成交。</p>
                        <p className="mt-1 font-medium">计算规则：</p>
                        <p>• Ask 侧挂单量减少 → 有人买入 (BUY)</p>
                        <p>• Bid 侧挂单量减少 → 有人卖出 (SELL)</p>
                        <p className="mt-1"><b>均价</b> = Σ(消耗量 × 该档价格) ÷ Σ消耗量</p>
                        <p><b>数量</b> = 被消耗的总份额（跨多个价位累计）</p>
                        <p className="mt-1 text-muted">注意：数量可能远大于当前 Orderbook 单档挂单量，因为成交发生在上一秒快照中存在而当前已被消耗的挂单上。</p>
                      </TooltipContent>
                    </Tooltip>
                  </TooltipProvider>
                </div>
                <Badge variant="outline" className="text-xs font-mono">
                  {trades.length}
                </Badge>
              </div>
              {/* Column legend */}
              <div className="flex items-center gap-2 px-3 text-[10px] text-muted-foreground mt-1">
                <span className="w-14 shrink-0">时间</span>
                <span className="w-12 shrink-0 text-center">标的</span>
                <span className="w-12 shrink-0 text-center">方向</span>
                <span className="flex-1 text-right">均价</span>
                <span className="w-12 shrink-0 text-right">数量</span>
              </div>
            </CardHeader>
            <CardContent className="p-0">
              {recentTrades.length > 0 ? (
                <ScrollArea className="h-48">
                  <div className="flex flex-col">
                    {recentTrades.map((t, i) => (
                      <div
                        key={`trade-${i}`}
                        className="flex items-center gap-2 border-b px-3 py-1 text-xs last:border-b-0"
                      >
                        <span className="font-mono text-muted-foreground w-14 shrink-0">
                          {fmtTs(t.timestamp)}
                        </span>
                        <Badge
                          variant="outline"
                          className={cn(
                            "text-[10px] w-12 shrink-0 justify-center px-0 py-0",
                            outcomeBadgeClass(t.token_id),
                          )}
                        >
                          {outcomeLabel(t.token_id)}
                        </Badge>
                        <Badge
                          variant={t.side === "BUY" ? "default" : "secondary"}
                          className={cn(
                            "text-xs w-12 shrink-0 justify-center px-0 py-0",
                            t.side === "BUY"
                              ? "bg-emerald-600 hover:bg-emerald-700"
                              : "bg-rose-600 hover:bg-rose-700 text-white",
                          )}
                        >
                          {t.side === "BUY" ? "↑买" : "↓卖"}
                        </Badge>
                        <span className="font-mono text-right flex-1">
                          {(t.price * 100).toFixed(1)}¢
                        </span>
                        <span className="font-mono text-right text-muted-foreground w-12 shrink-0">
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
