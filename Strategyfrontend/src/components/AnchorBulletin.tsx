import { useState, useMemo } from "react"
import {
  ResponsiveContainer,
  ComposedChart,
  Line,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
} from "recharts"
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from "@/components/ui/dialog"
import { Badge } from "@/components/ui/badge"
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card"
import { Separator } from "@/components/ui/separator"
import type { PricePoint } from "@/types"

interface AnchorBulletinProps {
  priceCurve: PricePoint[]
}

const SOURCE_LABELS: Record<string, { label: string; color: string; desc: string }> = {
  mid: { label: "Mid", color: "hsl(217, 91%, 60%)", desc: "Spread < 0.05，简单中间价" },
  micro: { label: "Micro", color: "hsl(280, 68%, 55%)", desc: "0.05 ≤ Spread < 0.15，深度加权" },
  last_trade: { label: "Last Trade", color: "hsl(30, 95%, 55%)", desc: "Spread ≥ 0.15，最近成交价" },
  none: { label: "N/A", color: "hsl(0, 0%, 50%)", desc: "无可靠价格" },
}

/** Determine UP/DOWN label from price: >= 0.5 is UP, < 0.5 is DOWN */
function priceLabel(mid: number): { side: "UP" | "DOWN"; emoji: string; color: string } {
  if (mid >= 0.5) return { side: "UP", emoji: "▲", color: "hsl(142, 71%, 45%)" }
  return { side: "DOWN", emoji: "▼", color: "hsl(0, 84%, 60%)" }
}

export default function AnchorBulletin({ priceCurve }: AnchorBulletinProps) {
  const [selectedToken, setSelectedToken] = useState<string | null>(null)
  const [showFormula, setShowFormula] = useState(false)

  const tokenIds = useMemo(() => {
    const ids = [...new Set(priceCurve.map((p) => p.token_id))]
    return ids.sort()
  }, [priceCurve])

  // Determine UP/DOWN from first available prices
  const tokenSides = useMemo(() => {
    const sides: Record<string, { side: "UP" | "DOWN"; emoji: string; color: string }> = {}
    for (const tid of tokenIds) {
      const pts = priceCurve.filter((p) => p.token_id === tid)
      // Use average of first 10 points to be robust
      const slice = pts.slice(0, 10)
      const avgMid = slice.length > 0 ? slice.reduce((s, p) => s + p.mid_price, 0) / slice.length : 0.5
      sides[tid] = priceLabel(avgMid)
    }
    return sides
  }, [priceCurve, tokenIds])

  // Per-token summary stats
  const tokenStats = useMemo(() => {
    const stats: Record<string, {
      lastMid: number
      lastAnchor: number
      lastSource: string
      lastSpread: number
      lastBid: number
      lastAsk: number
      lastTrade: number
      anchorSourceCounts: Record<string, number>
      avgSpread: number
      points: number
    }> = {}

    for (const tid of tokenIds) {
      const pts = priceCurve.filter((p) => p.token_id === tid)
      if (pts.length === 0) continue

      const last = pts[pts.length - 1]
      const sourceCounts: Record<string, number> = {}
      let spreadSum = 0

      for (const p of pts) {
        const src = p.anchor_source ?? "mid"
        sourceCounts[src] = (sourceCounts[src] || 0) + 1
        spreadSum += p.spread ?? 0
      }

      stats[tid] = {
        lastMid: last.mid_price,
        lastAnchor: last.anchor_price ?? last.mid_price,
        lastSource: last.anchor_source ?? "mid",
        lastSpread: last.spread ?? 0,
        lastBid: last.best_bid ?? 0,
        lastAsk: last.best_ask ?? 0,
        lastTrade: last.last_trade_price ?? 0,
        anchorSourceCounts: sourceCounts,
        avgSpread: spreadSum / pts.length,
        points: pts.length,
      }
    }
    return stats
  }, [priceCurve, tokenIds])

  // Chart data for selected token detail
  const detailData = useMemo(() => {
    if (!selectedToken) return []
    return priceCurve
      .filter((p) => p.token_id === selectedToken)
      .map((p) => ({
        timestamp: p.timestamp,
        mid: p.mid_price,
        anchor: p.anchor_price ?? p.mid_price,
        bid: p.best_bid ?? 0,
        ask: p.best_ask ?? 0,
        last_trade: (p.last_trade_price ?? 0) > 0 ? p.last_trade_price : undefined,
        spread: p.spread ?? 0,
        source: p.anchor_source ?? "mid",
      }))
  }, [priceCurve, selectedToken])

  if (tokenIds.length === 0) return null

  const getLabel = (tid: string) => {
    const info = tokenSides[tid]
    return info ? `${info.emoji} ${info.side}` : tid.slice(0, 8)
  }

  return (
    <>
      <Card>
        <CardHeader className="pb-2">
          <div className="flex items-center justify-between">
            <CardTitle className="text-base">锚点价格公告栏</CardTitle>
            <button
              onClick={() => setShowFormula(!showFormula)}
              className="text-xs text-muted-foreground underline decoration-dotted hover:text-foreground"
            >
              {showFormula ? "收起公式" : "查看计算公式"}
            </button>
          </div>
        </CardHeader>
        <CardContent>
          {/* Formula panel */}
          {showFormula && (
            <div className="mb-4 rounded-md border border-dashed p-3 text-xs leading-relaxed text-muted-foreground">
              <p className="mb-2 font-medium text-foreground">分层锚点价格计算规则：</p>

              <div className="mb-2">
                <Badge variant="outline" className="mr-1" style={{ borderColor: SOURCE_LABELS.mid.color, color: SOURCE_LABELS.mid.color }}>Tier 1: Mid</Badge>
                <span>当 <code>Spread &lt; 0.05</code> 时，订单簿紧密，直接取中间价</span>
                <div className="mt-1 rounded bg-muted px-2 py-1 font-mono">
                  anchor = (best_bid + best_ask) / 2
                </div>
              </div>

              <div className="mb-2">
                <Badge variant="outline" className="mr-1" style={{ borderColor: SOURCE_LABELS.micro.color, color: SOURCE_LABELS.micro.color }}>Tier 2: Micro-price（前3档深度加权）</Badge>
                <span>当 <code>0.05 ≤ Spread &lt; 0.15</code> 时</span>
                <div className="mt-1 rounded bg-muted px-2 py-1 font-mono text-[11px]">
                  anchor = (Σ bid_i × ΣV_ask + Σ ask_i × ΣV_bid) / (N_bid × ΣV_ask + N_ask × ΣV_bid)
                </div>
                <div className="mt-1 text-[11px]">
                  取 orderbook 买卖各前 3 档，用对侧总量交叉加权。
                  买方挂单量大 → 价格向 ask 靠拢（买压强、价格上行）；
                  卖方挂单量大 → 价格向 bid 靠拢。
                  <strong>震荡时多个相近价位均被纳入计算</strong>，比仅用 best 单档更稳健。
                </div>
              </div>

              <div className="mb-2">
                <Badge variant="outline" className="mr-1" style={{ borderColor: SOURCE_LABELS.last_trade.color, color: SOURCE_LABELS.last_trade.color }}>Tier 3: Last Trade</Badge>
                <span>当 <code>Spread ≥ 0.15</code> 且有成交记录时，Mid 不可信</span>
                <div className="mt-1 rounded bg-muted px-2 py-1 font-mono">
                  anchor = last_trade_price
                </div>
                <div className="mt-1 text-[11px]">
                  Polymarket 官方在 spread &gt; 0.10 时也会用 last traded price 替代 mid 展示。
                </div>
              </div>

              <Separator className="my-2" />

              <div className="text-[11px]">
                <p className="font-medium text-foreground">决策 vs 执行的区别：</p>
                <ul className="mt-1 flex flex-col gap-0.5">
                  <li>• <strong>策略决策</strong>（入场信号、止盈止损触发）→ 基于<strong>锚点价格</strong>（上述分层计算）</li>
                  <li>• <strong>订单执行</strong>（实际买入/卖出成交价）→ 基于 <strong>VWAP 穿越 orderbook</strong>（BUY 吃 ask 各档、SELL 吃 bid 各档），与锚点无关</li>
                  <li>• <strong>最近成交价</strong>（last_trade_price）→ 作为 Tier 3 回退 + 展示参考，不直接用于执行</li>
                </ul>
              </div>
            </div>
          )}

          <p className="mb-3 text-xs text-muted-foreground">
            策略决策锚点 = 分层计算参考价。实际执行 = VWAP 穿越 orderbook。点击查看走势详情。
          </p>

          <div className="flex flex-col gap-2">
            {tokenIds.map((tid) => {
              const s = tokenStats[tid]
              if (!s) return null
              const sideInfo = tokenSides[tid]
              const srcInfo = SOURCE_LABELS[s.lastSource] ?? SOURCE_LABELS.none
              const deviation = s.lastMid > 0
                ? Math.abs(s.lastAnchor - s.lastMid) / s.lastMid
                : 0

              return (
                <button
                  key={tid}
                  onClick={() => setSelectedToken(tid)}
                  className="flex items-center justify-between rounded-md border px-3 py-2.5 text-left transition-colors hover:bg-accent"
                >
                  <div className="flex items-center gap-3">
                    <span className="text-sm font-bold" style={{ color: sideInfo.color }}>
                      {sideInfo.emoji} {sideInfo.side}
                    </span>
                    <Badge variant="secondary" className="text-[10px]" style={{ borderColor: srcInfo.color, color: srcInfo.color }}>
                      {srcInfo.label}
                    </Badge>
                  </div>
                  <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-muted-foreground">
                    <span>Mid: <strong className="text-foreground">${s.lastMid.toFixed(4)}</strong></span>
                    <span>锚点: <strong className="text-foreground">${s.lastAnchor.toFixed(4)}</strong></span>
                    {s.lastTrade > 0 && (
                      <span>成交: <strong className="text-foreground">${s.lastTrade.toFixed(4)}</strong></span>
                    )}
                    <span>Spread: <strong className={s.lastSpread > 0.15 ? "text-destructive" : s.lastSpread > 0.05 ? "text-yellow-500" : "text-foreground"}>
                      {s.lastSpread.toFixed(4)}
                    </strong></span>
                    {deviation > 0.01 && (
                      <span className="text-yellow-500">偏离 {(deviation * 100).toFixed(1)}%</span>
                    )}
                  </div>
                </button>
              )
            })}
          </div>
        </CardContent>
      </Card>

      {/* Detail dialog */}
      <Dialog open={selectedToken !== null} onOpenChange={(open) => { if (!open) setSelectedToken(null) }}>
        <DialogContent className="max-w-3xl">
          <DialogHeader>
            <DialogTitle>
              {selectedToken && (
                <span style={{ color: tokenSides[selectedToken]?.color }}>
                  {tokenSides[selectedToken]?.emoji} {tokenSides[selectedToken]?.side}
                </span>
              )}
              {" "}— 锚点价格详情
            </DialogTitle>
            <DialogDescription>
              Mid vs 锚点 vs 最近成交价走势 + Bid/Ask 价差带
            </DialogDescription>
          </DialogHeader>

          {selectedToken && tokenStats[selectedToken] && (
            <div className="flex flex-col gap-4">
              {/* Source distribution */}
              <div className="flex flex-wrap gap-2">
                {Object.entries(tokenStats[selectedToken].anchorSourceCounts).map(([src, count]) => {
                  const info = SOURCE_LABELS[src] ?? SOURCE_LABELS.none
                  const pct = ((count / tokenStats[selectedToken].points) * 100).toFixed(0)
                  return (
                    <Badge key={src} variant="outline" style={{ borderColor: info.color, color: info.color }}>
                      {info.label}: {pct}% — {info.desc}
                    </Badge>
                  )
                })}
              </div>

              {/* Summary stats */}
              <div className="grid grid-cols-5 gap-2 text-center text-xs">
                <div className="rounded-md border p-2">
                  <div className="text-muted-foreground">最终 Mid</div>
                  <div className="text-sm font-semibold">${tokenStats[selectedToken].lastMid.toFixed(4)}</div>
                </div>
                <div className="rounded-md border p-2">
                  <div className="text-muted-foreground">最终锚点</div>
                  <div className="text-sm font-semibold">${tokenStats[selectedToken].lastAnchor.toFixed(4)}</div>
                </div>
                <div className="rounded-md border p-2">
                  <div className="text-muted-foreground">最近成交</div>
                  <div className="text-sm font-semibold">
                    {tokenStats[selectedToken].lastTrade > 0
                      ? `$${tokenStats[selectedToken].lastTrade.toFixed(4)}`
                      : "—"}
                  </div>
                </div>
                <div className="rounded-md border p-2">
                  <div className="text-muted-foreground">平均 Spread</div>
                  <div className="text-sm font-semibold">{tokenStats[selectedToken].avgSpread.toFixed(4)}</div>
                </div>
                <div className="rounded-md border p-2">
                  <div className="text-muted-foreground">Bid / Ask</div>
                  <div className="text-sm font-semibold">
                    ${tokenStats[selectedToken].lastBid.toFixed(2)} / ${tokenStats[selectedToken].lastAsk.toFixed(2)}
                  </div>
                </div>
              </div>

              {/* Detail chart */}
              <div className="h-72">
                <ResponsiveContainer width="100%" height="100%">
                  <ComposedChart data={detailData}>
                    <CartesianGrid strokeDasharray="3 3" opacity={0.3} />
                    <XAxis
                      dataKey="timestamp"
                      tickFormatter={(v: string) => v.slice(11, 19)}
                      tick={{ fontSize: 10 }}
                      interval="preserveStartEnd"
                    />
                    <YAxis
                      domain={[0, 1]}
                      tickFormatter={(v: number) => `$${v.toFixed(2)}`}
                      tick={{ fontSize: 10 }}
                      width={50}
                    />
                    <Tooltip
                      labelFormatter={(v) => String(v).slice(0, 19).replace("T", " ")}
                      formatter={(value, name) => {
                        const labels: Record<string, string> = {
                          mid: "Mid Price",
                          anchor: "锚点价格",
                          last_trade: "最近成交价",
                          bid: "Best Bid",
                          ask: "Best Ask",
                        }
                        return [`$${Number(value).toFixed(4)}`, labels[String(name)] ?? String(name)]
                      }}
                    />
                    <Legend
                      formatter={(value: string) => {
                        const labels: Record<string, string> = {
                          mid: "Mid Price",
                          anchor: "锚点价格",
                          last_trade: "最近成交价",
                          bid: "Best Bid",
                          ask: "Best Ask",
                        }
                        return labels[value] ?? value
                      }}
                    />

                    {/* Bid-Ask spread band */}
                    <Area type="monotone" dataKey="ask" stroke="none" fill="hsl(0, 84%, 60%)" fillOpacity={0.08} />
                    <Area type="monotone" dataKey="bid" stroke="none" fill="hsl(142, 71%, 45%)" fillOpacity={0.08} />

                    {/* Bid / Ask lines */}
                    <Line type="monotone" dataKey="bid" stroke="hsl(142, 71%, 45%)" strokeWidth={1} strokeDasharray="2 2" dot={false} connectNulls />
                    <Line type="monotone" dataKey="ask" stroke="hsl(0, 84%, 60%)" strokeWidth={1} strokeDasharray="2 2" dot={false} connectNulls />

                    {/* Mid price — solid blue */}
                    <Line type="monotone" dataKey="mid" stroke="hsl(217, 91%, 60%)" strokeWidth={2} dot={false} connectNulls />

                    {/* Last trade price — orange step line */}
                    <Line type="stepAfter" dataKey="last_trade" stroke="hsl(30, 95%, 55%)" strokeWidth={1.5} dot={false} connectNulls />

                    {/* Anchor price — thick dashed purple */}
                    <Line type="monotone" dataKey="anchor" stroke="hsl(280, 68%, 55%)" strokeWidth={2.5} strokeDasharray="6 3" dot={false} connectNulls />
                  </ComposedChart>
                </ResponsiveContainer>
              </div>

              {/* Explanation box */}
              <div className="rounded-md border border-dashed p-3 text-xs text-muted-foreground leading-relaxed">
                <p className="font-medium text-foreground">图表说明</p>
                <ul className="mt-1 flex flex-col gap-1">
                  <li><span className="inline-block size-2 rounded-full" style={{ backgroundColor: "hsl(217, 91%, 60%)" }} /> <strong>Mid Price</strong>（实线蓝）= (best_bid + best_ask) / 2，订单簿趋势参考</li>
                  <li><span className="inline-block size-2 rounded-full" style={{ backgroundColor: "hsl(280, 68%, 55%)" }} /> <strong>锚点价格</strong>（虚线紫）= 分层计算的策略决策锚点</li>
                  <li><span className="inline-block size-2 rounded-full" style={{ backgroundColor: "hsl(30, 95%, 55%)" }} /> <strong>最近成交价</strong>（阶梯橙）= 真实交易价格（last_trade_price）</li>
                  <li><span className="inline-block size-2 rounded-full" style={{ backgroundColor: "hsl(142, 71%, 45%)" }} /> <strong>Best Bid</strong>（虚线绿）/ <span className="inline-block size-2 rounded-full" style={{ backgroundColor: "hsl(0, 84%, 60%)" }} /> <strong>Best Ask</strong>（虚线红）= 买卖价差带</li>
                </ul>
                <Separator className="my-2" />
                <p>
                  <strong>策略决策</strong>（入场/止盈/止损）基于紫色锚点线。
                  <strong>订单执行</strong>（实际成交价）基于 VWAP 穿越 orderbook ask/bid 各档位，与锚点无关。
                </p>
              </div>
            </div>
          )}
        </DialogContent>
      </Dialog>
    </>
  )
}
