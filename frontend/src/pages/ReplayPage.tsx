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
import OrderbookView from "@/components/OrderbookView"
import PriceChart from "@/components/PriceChart"
import { useReplayStream } from "@/hooks/useReplayStream"
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
  PriceLevel,
} from "@/types"
import type { StaticOrderbookData } from "@/components/OrderbookView"

import { fmtTimeCst } from "@/lib/utils"

function fmtTs(iso: string): string {
  return fmtTimeCst(iso)
}

// ── Main page ───────────────────────────────────────────────────────────────

export default function ReplayPage() {
  const { slug } = useParams<{ slug: string }>()
  const [currentIndex, setCurrentIndex] = useState(0)
  const [playing, setPlaying] = useState(false)
  const [speed, setSpeed] = useState("1")
  const [playStartIndex, setPlayStartIndex] = useState(0)
  const [session, setSession] = useState<ReplaySession | null>(null)
  const [tradeAmount, setTradeAmount] = useState("")
  const currentIndexRef = useRef(currentIndex)
  currentIndexRef.current = currentIndex

  // Load archive meta (retry every 3s if not ready — archival may still be in progress)
  const { data: archive } = useQuery<ArchivedEvent>({
    queryKey: ["archive", slug],
    queryFn: () => fetchArchive(slug!),
    enabled: !!slug,
    retry: 10,
    retryDelay: 3_000,
  })

  // Load timeline (retry similarly)
  const { data: timeline, isLoading: timelineLoading } = useQuery<ReplayTimeline>({
    queryKey: ["replayTimeline", slug],
    queryFn: () => fetchReplayTimeline(slug!),
    enabled: !!slug,
    retry: 10,
    retryDelay: 3_000,
  })

  // ── SSE stream (active during playback) ──────────────────
  const {
    snapshot: streamSnapshot,
    streamIndex,
    connected,
  } = useReplayStream({
    slug,
    startIndex: playStartIndex,
    speed: parseFloat(speed),
    playing,
  })

  // Update currentIndex from stream
  useEffect(() => {
    if (playing && streamIndex !== currentIndex) {
      setCurrentIndex(streamIndex)
    }
  }, [playing, streamIndex])

  // Auto-stop at end
  useEffect(() => {
    if (playing && timeline && streamIndex >= timeline.timestamps.length - 1) {
      setPlaying(false)
    }
  }, [playing, streamIndex, timeline])

  // ── Single snapshot (when paused / seeking) ──────────────
  const currentTs = timeline?.timestamps[currentIndex] ?? ""
  const { data: fetchedSnapshot } = useQuery<ReplaySnapshot>({
    queryKey: ["replaySnapshot", slug, currentTs],
    queryFn: () => fetchReplaySnapshot(slug!, currentTs),
    enabled: !!slug && !!currentTs && !playing,
    staleTime: Infinity,
    placeholderData: keepPreviousData,
  })

  // Use stream snapshot when playing, fetched when paused
  const snapshot = playing ? (streamSnapshot ?? fetchedSnapshot) : fetchedSnapshot

  // ── Playback controls ────────────────────────────────────
  const handlePlayingChange = useCallback(
    (play: boolean) => {
      if (play) {
        setPlayStartIndex(currentIndexRef.current)
      }
      setPlaying(play)
    },
    [],
  )

  const handleSpeedChange = useCallback(
    (newSpeed: string) => {
      setSpeed(newSpeed)
      if (playing) {
        // Reconnect from current position with new speed
        setPlayStartIndex(currentIndexRef.current)
      }
    },
    [playing],
  )

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
    setPlaying(false)
    setCurrentIndex(index)
  }, [])

  // ── Derived values ───────────────────────────────────────
  // Token IDs: prefer from snapshot (per-token data), fallback to archive/timeline
  const tokenIds = snapshot?.token_ids ?? timeline?.token_ids ?? archive?.token_ids ?? []
  const replayTokens = tokenIds.length >= 2 ? [tokenIds[0], tokenIds[1]] : tokenIds.length === 1 ? [tokenIds[0]] : []
  // Use real outcome labels from archive meta, fallback to UP/DOWN
  const archiveOutcomes = archive?.outcomes ?? []
  const replayOutcomes = replayTokens.map((_, i) =>
    i < archiveOutcomes.length ? archiveOutcomes[i] : (i === 0 ? "Up" : "Down")
  )

  // Per-token data from snapshot
  const tokensData = snapshot?.tokens ?? {}

  // Per-token mid prices for outcome probability display
  const token0Data = tokensData[replayTokens[0] ?? ""] ?? {}
  const token1Data = tokensData[replayTokens[1] ?? ""] ?? {}
  const mid0 = token0Data.mid_price ?? 0
  const mid1 = token1Data.mid_price ?? 0
  // First token's data for the price indicator row
  const mid = mid0
  const bestBid = token0Data.best_bid ?? 0
  const bestAsk = token0Data.best_ask ?? 0
  const spread = token0Data.spread ?? 0

  // Build staticBooks for OrderbookView (per-token)
  const staticBooks = useMemo<Record<string, StaticOrderbookData>>(() => {
    const result: Record<string, StaticOrderbookData> = {}
    for (const tid of replayTokens) {
      const td = tokensData[tid]
      if (!td) continue
      const bids: PriceLevel[] = (td.bid_prices ?? []).map((p: string, i: number) => ({
        price: String(p),
        size: String((td.bid_sizes ?? [])[i] ?? "0"),
      }))
      const asks: PriceLevel[] = (td.ask_prices ?? []).map((p: string, i: number) => ({
        price: String(p),
        size: String((td.ask_sizes ?? [])[i] ?? "0"),
      }))
      result[tid] = {
        bids,
        asks,
        lastTradePrice: td.mid_price ? String(td.mid_price) : undefined,
      }
    }
    return result
  }, [tokensData, replayTokens.join(",")])

  // Build replayMid for PriceChart (per-token)
  const replayMid = useMemo<Record<string, number>>(() => {
    const result: Record<string, number> = {}
    for (const tid of replayTokens) {
      const m = tokensData[tid]?.mid_price
      if (m && m > 0) result[tid] = m
    }
    return result
  }, [tokensData, replayTokens.join(",")])

  const trades = snapshot?.trades ?? []
  const recentTrades = useMemo(
    () => trades.slice(-30).reverse(),
    [trades],
  )

  // Map token_id to outcome label using real outcome names
  const outcomeLabel = useCallback(
    (tokenId: string) => {
      const idx = tokenIds.indexOf(tokenId)
      if (idx >= 0 && idx < replayOutcomes.length) return replayOutcomes[idx]
      return tokenId.slice(0, 6) + "…"
    },
    [tokenIds, replayOutcomes],
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

      {/* ── Data availability info ──────────────────────────── */}
      {timeline.data_summary && (
        <div className="flex flex-wrap items-center gap-2 text-xs">
          <span className="text-muted-foreground">数据:</span>
          <Badge variant={timeline.data_summary.prices.count > 0 ? "default" : "secondary"} className="text-xs font-mono">
            价格 {timeline.data_summary.prices.count}
          </Badge>
          <Badge variant={timeline.data_summary.orderbooks.count > 0 ? "default" : "secondary"} className="text-xs font-mono">
            盘口 {timeline.data_summary.orderbooks.count}
          </Badge>
          <Badge variant={timeline.data_summary.live_trades.count > 0 ? "default" : "secondary"} className="text-xs font-mono">
            成交 {timeline.data_summary.live_trades.count}
          </Badge>
          {timeline.data_summary.prices.start && (
            <span className="text-muted-foreground font-mono">
              · 数据自 {fmtTs(timeline.data_summary.prices.start)} 开始
            </span>
          )}
        </div>
      )}

      {/* ── Replay Controls ─────────────────────────────────── */}
      <ReplayControls
        timeline={timeline}
        currentIndex={currentIndex}
        playing={playing}
        speed={speed}
        connected={connected}
        onSeek={handleSeek}
        onPlayingChange={handlePlayingChange}
        onSpeedChange={handleSpeedChange}
      />

      {/* ── Main layout ─────────────────────────────────────── */}
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-12">
        {/* ─── Left column (8/12) ─────────────────────────────── */}
        <div className="flex flex-col gap-4 lg:col-span-8">

          {/* 1) Outcome probabilities + price indicators */}
          <Card>
            <CardContent className="p-4">
              {/* Outcome probability overview */}
              {replayOutcomes.length >= 2 && (mid0 > 0 || mid1 > 0) && (
                <div className="mb-3 grid grid-cols-2 gap-2 text-center">
                  <div className="rounded-md px-2 py-1.5 bg-emerald-500/10">
                    <div className="text-xs text-muted-foreground">{replayOutcomes[0]}</div>
                    <div className="text-lg font-bold tabular-nums">
                      {mid0 ? `${(mid0 * 100).toFixed(1)}¢` : "—"}
                    </div>
                  </div>
                  <div className="rounded-md px-2 py-1.5 bg-rose-500/10">
                    <div className="text-xs text-muted-foreground">{replayOutcomes[1]}</div>
                    <div className="text-lg font-bold tabular-nums">
                      {mid1 ? `${(mid1 * 100).toFixed(1)}¢` : "—"}
                    </div>
                  </div>
                </div>
              )}
              <div className="grid grid-cols-4 gap-4 text-center">
                <div>
                  <div className="text-xs text-muted-foreground">{replayOutcomes[0] ?? "Token 1"} Mid</div>
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

          {/* 2) Price chart (TradingView Lightweight Charts) */}
          <PriceChart
            tokens={replayTokens}
            outcomes={replayOutcomes}
            replayMid={replayMid}
            replayTimestamp={currentTs}
          />

          {/* 3) Orderbook (shared component) */}
          <OrderbookView
            tokens={replayTokens}
            outcomes={replayOutcomes}
            staticBooks={staticBooks}
          />

          {/* 4) Trades activity — real on-chain trades */}
          <Card>
            <CardHeader className="pb-2">
              <div className="flex items-center justify-between">
                <CardTitle className="text-sm">成交记录</CardTitle>
                <Badge variant="outline" className="text-xs font-mono">
                  {trades.length}
                </Badge>
              </div>
              {/* Column legend */}
              <div className="flex items-center gap-2 px-3 text-[10px] text-muted-foreground mt-1">
                <span className="w-14 shrink-0">时间</span>
                <span className="w-12 shrink-0 text-center">标的</span>
                <span className="w-12 shrink-0 text-center">方向</span>
                <span className="flex-1 text-right">价格</span>
                <span className="w-12 shrink-0 text-right">数量</span>
                <span className="w-20 shrink-0 text-right">TxHash</span>
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
                        <span className="font-mono text-right text-muted-foreground w-20 shrink-0 truncate" title={t.transaction_hash}>
                          {t.transaction_hash ? t.transaction_hash.slice(0, 8) + "…" : "—"}
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
                  {/* Outcome probability overview */}
                  {replayOutcomes.length >= 2 && (mid0 > 0 || mid1 > 0) && (
                    <>
                      <div className="grid grid-cols-2 gap-2 text-center">
                        <div className="rounded-md px-2 py-1.5 bg-emerald-500/10 ring-1 ring-emerald-500/30">
                          <div className="text-xs text-muted-foreground">{replayOutcomes[0]}</div>
                          <div className="text-lg font-bold tabular-nums">
                            {mid0 ? `${(mid0 * 100).toFixed(1)}¢` : "—"}
                          </div>
                        </div>
                        <div className="rounded-md px-2 py-1.5 bg-rose-500/10 ring-1 ring-rose-500/30">
                          <div className="text-xs text-muted-foreground">{replayOutcomes[1]}</div>
                          <div className="text-lg font-bold tabular-nums">
                            {mid1 ? `${(mid1 * 100).toFixed(1)}¢` : "—"}
                          </div>
                        </div>
                      </div>
                      <Separator />
                    </>
                  )}

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
                          <Badge
                            variant="outline"
                            className={cn(
                              "text-[10px] px-1 py-0",
                              outcomeBadgeClass(tid),
                            )}
                          >
                            {outcomeLabel(tid)}
                          </Badge>
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
