import { useState, useCallback } from "react"
import { useParams, Link } from "react-router-dom"
import { useQuery, useMutation } from "@tanstack/react-query"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Separator } from "@/components/ui/separator"
import { Skeleton } from "@/components/ui/skeleton"
import { Alert, AlertDescription } from "@/components/ui/alert"
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
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

  // Load snapshot for current timestamp
  const currentTs = timeline?.timestamps[currentIndex] ?? ""
  const { data: snapshot } = useQuery<ReplaySnapshot>({
    queryKey: ["replaySnapshot", slug, currentTs],
    queryFn: () => fetchReplaySnapshot(slug!, currentTs),
    enabled: !!slug && !!currentTs,
    staleTime: Infinity,
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
        <p className="text-muted-foreground">
          没有找到该场次的归档数据
        </p>
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
      </div>

      {/* ── Replay Controls ─────────────────────────────────── */}
      <ReplayControls
        timeline={timeline}
        currentIndex={currentIndex}
        onSeek={handleSeek}
      />

      {/* ── Main layout ─────────────────────────────────────── */}
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-12">
        {/* Left: orderbook snapshot + price info */}
        <div className="flex flex-col gap-4 lg:col-span-8">
          {/* Price info */}
          {snapshot && (
            <div className="grid grid-cols-4 gap-2">
              <Card>
                <CardContent className="p-3 text-center">
                  <div className="text-xs text-muted-foreground">Mid</div>
                  <div className="text-lg font-bold tabular-nums">
                    {(snapshot.mid_price * 100).toFixed(1)}¢
                  </div>
                </CardContent>
              </Card>
              <Card>
                <CardContent className="p-3 text-center">
                  <div className="text-xs text-muted-foreground">Best Bid</div>
                  <div className="text-lg font-bold tabular-nums text-emerald-600">
                    {(snapshot.best_bid * 100).toFixed(1)}¢
                  </div>
                </CardContent>
              </Card>
              <Card>
                <CardContent className="p-3 text-center">
                  <div className="text-xs text-muted-foreground">Best Ask</div>
                  <div className="text-lg font-bold tabular-nums text-rose-600">
                    {(snapshot.best_ask * 100).toFixed(1)}¢
                  </div>
                </CardContent>
              </Card>
              <Card>
                <CardContent className="p-3 text-center">
                  <div className="text-xs text-muted-foreground">Spread</div>
                  <div className="text-lg font-bold tabular-nums">
                    {(snapshot.spread * 100).toFixed(2)}¢
                  </div>
                </CardContent>
              </Card>
            </div>
          )}

          {/* Orderbook snapshot */}
          {snapshot && (
            <div className="grid grid-cols-2 gap-4">
              {/* Bids */}
              <Card>
                <CardHeader className="pb-2">
                  <CardTitle className="text-sm text-emerald-600">
                    Bids (买单)
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead className="text-xs">价格</TableHead>
                        <TableHead className="text-xs text-right">数量</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {snapshot.bid_prices.slice(0, 10).map((p, i) => (
                        <TableRow key={`bid-${i}`}>
                          <TableCell className="text-xs font-mono text-emerald-600">
                            {(parseFloat(p) * 100).toFixed(1)}¢
                          </TableCell>
                          <TableCell className="text-xs text-right font-mono">
                            {parseFloat(snapshot.bid_sizes[i] ?? "0").toFixed(0)}
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </CardContent>
              </Card>

              {/* Asks */}
              <Card>
                <CardHeader className="pb-2">
                  <CardTitle className="text-sm text-rose-600">
                    Asks (卖单)
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead className="text-xs">价格</TableHead>
                        <TableHead className="text-xs text-right">数量</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {snapshot.ask_prices.slice(0, 10).map((p, i) => (
                        <TableRow key={`ask-${i}`}>
                          <TableCell className="text-xs font-mono text-rose-600">
                            {(parseFloat(p) * 100).toFixed(1)}¢
                          </TableCell>
                          <TableCell className="text-xs text-right font-mono">
                            {parseFloat(snapshot.ask_sizes[i] ?? "0").toFixed(0)}
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </CardContent>
              </Card>
            </div>
          )}
        </div>

        {/* Right: replay trading panel */}
        <div className="flex flex-col gap-4 lg:col-span-4 lg:sticky lg:top-4 lg:self-start">
          {/* Session creation / info */}
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
                    <label className="text-xs text-muted-foreground">
                      份数
                    </label>
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
                      variant="secondary"
                      size="sm"
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
                        <div
                          key={tid}
                          className="flex justify-between text-xs"
                        >
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
                      <div className="max-h-40 overflow-y-auto">
                        {session.trades.map((t, i) => (
                          <div
                            key={i}
                            className="flex items-center justify-between py-0.5 text-xs"
                          >
                            <span className="font-mono text-muted-foreground">
                              {fmtTs(t.timestamp)}
                            </span>
                            <Badge
                              variant={
                                t.side === "BUY" ? "default" : "secondary"
                              }
                              className="text-xs"
                            >
                              {t.side}
                            </Badge>
                            <span className="font-mono">
                              {t.amount.toFixed(1)} @ {(t.avg_price * 100).toFixed(1)}¢
                            </span>
                          </div>
                        ))}
                      </div>
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
