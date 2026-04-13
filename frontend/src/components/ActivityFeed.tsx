import { useState, useRef, useMemo, useEffect } from "react"
import { useQuery } from "@tanstack/react-query"
import { Badge } from "@/components/ui/badge"
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { Skeleton } from "@/components/ui/skeleton"
import { ScrollArea } from "@/components/ui/scroll-area"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { fetchLiveTrades, fetchTradeHistory } from "@/api/client"
import type { PolymarketTrade, TradeRecord, WsLastTradeEvent } from "@/types"

interface ActivityFeedProps {
  tokenId: string
  marketId?: string
  conditionId?: string
  enabled?: boolean
  /** WS-driven trade events (real-time stream) */
  wsTrades?: WsLastTradeEvent[]
  wsConnected?: boolean
  /** Outcome labels (e.g. ["Up", "Down"]) for mapping WS trades */
  outcomes?: string[]
  /** Token IDs corresponding to outcomes */
  tokenIds?: string[]
}

import { fmtTimeCst } from "@/lib/utils"

function fmtTime(iso: string): string {
  return fmtTimeCst(iso)
}

function fmtRelativeTime(unixSeconds: number): string {
  const diff = Math.floor(Date.now() / 1000 - unixSeconds)
  if (diff < 5) return "刚刚"
  if (diff < 60) return `${diff}秒前`
  if (diff < 3600) return `${Math.floor(diff / 60)}分前`
  if (diff < 86400) return `${Math.floor(diff / 3600)}时前`
  return `${Math.floor(diff / 86400)}天前`
}

function shortenPseudonym(pseudonym: string, name: string): string {
  if (pseudonym) return pseudonym
  if (name) return name
  return "匿名"
}

export default function ActivityFeed({ tokenId, marketId, conditionId, enabled = true, wsTrades = [], wsConnected, outcomes = [], tokenIds = [] }: ActivityFeedProps) {
  const [tab, setTab] = useState("market")
  const prevTradesRef = useRef<Set<string>>(new Set())
  const [newTxHashes, setNewTxHashes] = useState<Set<string>>(new Set())

  // Prefer conditionId for Data API (returns fresher data than numeric marketId)
  const liveQueryId = conditionId || marketId

  // ── Live trades from Polymarket Data API ─────────────────
  // When WS is connected, reduce polling frequency (WS provides real-time trades)
  const { data: liveData, isLoading: liveLoading } = useQuery({
    queryKey: ["liveTrades", liveQueryId],
    queryFn: () => fetchLiveTrades(liveQueryId!, 40),
    enabled: !!liveQueryId && enabled && tab === "market",
    refetchInterval: wsConnected ? 30_000 : 3_000,
  })

  // ── My simulated trades ──────────────────────────────────
  const { data: myData, isLoading: myLoading } = useQuery({
    queryKey: ["activityFeed", tokenId],
    queryFn: () => fetchTradeHistory(0, 20, tokenId),
    enabled: !!tokenId && enabled && tab === "mine",
    refetchInterval: 3_000,
  })

  const httpTrades: PolymarketTrade[] = liveData?.trades ?? []
  const myTrades: TradeRecord[] = myData?.trades ?? []

  // Merge WS trades into the HTTP trade list (WS trades prepended as PolymarketTrade-like)
  const liveTrades: PolymarketTrade[] = useMemo(() => {
    if (!wsConnected || wsTrades.length === 0) return httpTrades

    // Convert WS trades to PolymarketTrade shape for unified rendering
    const wsConverted: PolymarketTrade[] = wsTrades.map((t) => {
      // Map asset_id to outcome (not by side — side is buy/sell direction, not the outcome)
      const outcomeIdx = tokenIds.indexOf(t.asset_id)
      const outcomeName = outcomeIdx >= 0 && outcomeIdx < outcomes.length
        ? outcomes[outcomeIdx]
        : (t.side === "BUY" ? "Yes" : "No")
      return {
        proxyWallet: "",
        side: t.side,
        asset: t.asset_id,
        conditionId: t.market,
        size: parseFloat(t.size),
        price: parseFloat(t.price),
        timestamp: parseFloat(t.timestamp) / 1000,
        title: "",
        slug: "",
        icon: "",
        eventSlug: "",
        outcome: outcomeName,
        outcomeIndex: outcomeIdx >= 0 ? outcomeIdx : 0,
        name: "",
        pseudonym: "WS",
        transactionHash: t.transaction_hash ?? `ws-${t.timestamp}-${t.price}`,
      }
    })

    // Merge: WS first, then HTTP, deduped by transactionHash
    const seen = new Set<string>()
    const merged: PolymarketTrade[] = []
    for (const t of [...wsConverted, ...httpTrades]) {
      if (!seen.has(t.transactionHash)) {
        seen.add(t.transactionHash)
        merged.push(t)
      }
    }
    return merged.slice(0, 60)
  }, [httpTrades, wsTrades, wsConnected])

  // ── Detect new trades for animation ──────────────────────
  useEffect(() => {
    if (liveTrades.length === 0) return
    const currentHashes = new Set(liveTrades.map((t) => t.transactionHash))

    // First load: seed ref without triggering animations
    if (prevTradesRef.current.size === 0) {
      prevTradesRef.current = currentHashes
      return
    }

    const fresh = new Set<string>()
    for (const hash of currentHashes) {
      if (!prevTradesRef.current.has(hash)) {
        fresh.add(hash)
      }
    }
    // Always update ref so stale hashes don't persist
    prevTradesRef.current = currentHashes

    if (fresh.size > 0) {
      setNewTxHashes(fresh)
      const timer = setTimeout(() => setNewTxHashes(new Set()), 1500)
      return () => clearTimeout(timer)
    }
  }, [liveTrades])

  // ── Live stats: BUY/SELL counts in recent window ─────────
  const stats = useMemo(() => {
    const now = Date.now() / 1000
    const window = 60 // 60 second window
    let buys = 0
    let sells = 0
    for (const t of liveTrades) {
      if (now - t.timestamp < window) {
        if (t.side === "BUY") buys++
        else if (t.side === "SELL") sells++
      }
    }
    return { buys, sells }
  }, [liveTrades])

  return (
    <Card>
      <CardHeader className="pb-2">
        <div className="flex items-center justify-between">
          <CardTitle className="text-sm">Polymarket Live</CardTitle>
          {tab === "market" && (stats.buys > 0 || stats.sells > 0) && (
            <div className="flex items-center gap-2 text-xs">
              <span className="text-emerald-500 font-medium">
                ↑买 +{stats.buys}
              </span>
              <span className="text-rose-500 font-medium">
                ↓卖 +{stats.sells}
              </span>
            </div>
          )}
        </div>
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
            {liveLoading ? (
              <div className="flex flex-col gap-2">
                {Array.from({ length: 5 }).map((_, i) => (
                  <Skeleton key={i} className="h-10 w-full" />
                ))}
              </div>
            ) : liveTrades.length === 0 ? (
              <p className="py-4 text-center text-xs text-muted-foreground">
                等待市场成交数据…
              </p>
            ) : (
              <ScrollArea className="h-[360px]">
                <div className="flex flex-col gap-0.5">
                  {liveTrades.map((t) => {
                    const isNew = newTxHashes.has(t.transactionHash)
                    const isBuy = t.side === "BUY"
                    const total = t.size * t.price
                    return (
                      <div
                        key={t.transactionHash}
                        className={`relative flex items-center gap-2 rounded-md px-2 py-1.5 text-xs transition-colors ${
                          isNew
                            ? isBuy
                              ? "animate-trade-slide-in animate-trade-pulse-buy"
                              : "animate-trade-slide-in animate-trade-pulse-sell"
                            : ""
                        }`}
                      >
                        {/* Floating badge for new trades */}
                        {isNew && (
                          <span
                            className={`absolute -left-1 top-0 animate-badge-float text-xs font-bold ${
                              isBuy ? "text-emerald-500" : "text-rose-500"
                            }`}
                          >
                            {isBuy ? "+" : "-"}{Math.round(t.size)}
                          </span>
                        )}

                        {/* Direction indicator */}
                        <span
                          className={`inline-flex h-5 w-5 shrink-0 items-center justify-center rounded-full text-[10px] font-bold ${
                            isBuy
                              ? "bg-emerald-500/15 text-emerald-600"
                              : "bg-rose-500/15 text-rose-600"
                          }`}
                        >
                          {isBuy ? "↑" : "↓"}
                        </span>

                        {/* Trade info */}
                        <div className="flex min-w-0 flex-1 flex-col">
                          <div className="flex items-center gap-1 truncate">
                            <span className="font-medium truncate">
                              {shortenPseudonym(t.pseudonym, t.name)}
                            </span>
                            <span className="text-muted-foreground">
                              {isBuy ? "已买入" : "已卖出"}
                            </span>
                            <span className="font-medium">
                              {t.size % 1 === 0 ? t.size : t.size.toFixed(1)}
                            </span>
                            <Badge
                              variant="outline"
                              className="h-4 px-1 text-[10px] font-normal"
                            >
                              {t.outcome}
                            </Badge>
                          </div>
                          <div className="flex items-center gap-1 text-muted-foreground">
                            <span>
                              于 {(t.price * 100).toFixed(1)}¢
                              {total >= 0.01 && (
                                <span className="ml-0.5">(${total.toFixed(2)})</span>
                              )}
                            </span>
                          </div>
                        </div>

                        {/* Relative time */}
                        <span className="shrink-0 text-muted-foreground text-[10px]">
                          {fmtRelativeTime(t.timestamp)}
                        </span>
                      </div>
                    )
                  })}
                </div>
              </ScrollArea>
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
                          className={`text-xs ${
                            t.side === "BUY"
                              ? "bg-blue-600 hover:bg-blue-700"
                              : "bg-blue-400 hover:bg-blue-500 text-white"
                          }`}
                        >
                          {t.side === "BUY" ? "↑买" : "↓卖"}
                          <span className="ml-0.5 text-[10px] opacity-75">模拟</span>
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
