import { useMemo } from "react"
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
  ReferenceLine,
} from "recharts"
import type { ExitAnalysisResponse, ExitFactorPoint, PricePoint, TradeRecord } from "@/types"
import { fmtMsTimeCst, fmtMsDateTimeCst } from "@/lib/utils"

interface ExitAnalysisPanelProps {
  data: ExitAnalysisResponse
  priceCurve?: PricePoint[]
  trades?: TradeRecord[]
}

/** Map action → display label + color */
const ACTION_STYLE: Record<string, { label: string; color: string; bg: string }> = {
  hold:   { label: "持有", color: "text-emerald-600", bg: "bg-emerald-50 dark:bg-emerald-950" },
  reduce: { label: "减仓", color: "text-amber-600",   bg: "bg-amber-50 dark:bg-amber-950" },
  exit:   { label: "清仓", color: "text-red-500",     bg: "bg-red-50 dark:bg-red-950" },
}

function _isoToMs(ts: string): number {
  return new Date(ts).getTime()
}

export default function ExitAnalysisPanel({ data, priceCurve, trades }: ExitAnalysisPanelProps) {
  const { factor_timeline, simulated_equity_curve, summary } = data

  // ── Build chart data: merge factor timeline with Poly price ────────────
  const chartData = useMemo(() => {
    if (!factor_timeline.length) return []

    // Build price lookup from Poly price_curve
    const priceByMs = new Map<number, number>()
    if (priceCurve) {
      for (const p of priceCurve) {
        const ms = _isoToMs(p.timestamp)
        priceByMs.set(ms, p.anchor_price || p.mid_price)
      }
    }

    // Build equity lookup from simulated curve
    const eqByMs = new Map<number, number>()
    for (const e of simulated_equity_curve) {
      eqByMs.set(e.time_ms, e.equity)
    }

    // Merge
    return factor_timeline.map((pt) => {
      // Find nearest Poly price
      let polyPrice: number | null = null
      if (priceByMs.size > 0) {
        let bestDist = Infinity
        for (const [ms, price] of priceByMs) {
          const dist = Math.abs(ms - pt.time_ms)
          if (dist < bestDist) {
            bestDist = dist
            polyPrice = price
          }
        }
      }

      return {
        time_ms: pt.time_ms,
        time: fmtMsTimeCst(pt.time_ms),
        fullTime: fmtMsDateTimeCst(pt.time_ms),
        score: pt.composite_score,
        position_pct: pt.suggested_position_pct * 100,
        poly_price: polyPrice,
        sim_equity: eqByMs.get(pt.time_ms) ?? null,
        action: pt.action,
      }
    })
  }, [factor_timeline, priceCurve, simulated_equity_curve])

  // ── Key transition points (action changes) ────────────────────────────
  const keyPoints = useMemo(() => {
    const points: (ExitFactorPoint & { idx: number })[] = []
    for (let i = 0; i < factor_timeline.length; i++) {
      if (i === 0 || factor_timeline[i].action !== factor_timeline[i - 1].action) {
        points.push({ ...factor_timeline[i], idx: i })
      }
    }
    return points
  }, [factor_timeline])

  // ── Trade timestamps for reference lines ──────────────────────────────
  const buyMs = trades?.find((t) => t.side === "BUY")?.timestamp
    ? _isoToMs(trades.find((t) => t.side === "BUY")!.timestamp)
    : null
  const sellMs = trades?.find((t) => t.side === "SELL")?.timestamp
    ? _isoToMs(trades.find((t) => t.side === "SELL")!.timestamp)
    : null

  if (!factor_timeline.length) {
    return (
      <div className="rounded-lg border p-4 text-center text-sm text-muted-foreground">
        无因子退出分析数据（可能无买入交易）
      </div>
    )
  }

  return (
    <div className="flex flex-col gap-5">
      {/* ── Summary cards ──────────────────────────────────────────── */}
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <div className="rounded-md border p-3">
          <div className="text-xs text-muted-foreground">因子首次建议减仓</div>
          <div className="mt-1 text-sm font-bold">
            {summary.first_reduce_ts
              ? fmtMsDateTimeCst(summary.first_reduce_ts)
              : "—（全程持有）"}
          </div>
        </div>
        <div className="rounded-md border p-3">
          <div className="text-xs text-muted-foreground">因子首次建议清仓</div>
          <div className="mt-1 text-sm font-bold">
            {summary.first_exit_ts
              ? fmtMsDateTimeCst(summary.first_exit_ts)
              : "—（未触发）"}
          </div>
        </div>
        <div className="rounded-md border p-3">
          <div className="text-xs text-muted-foreground">实际卖出时间</div>
          <div className="mt-1 text-sm font-bold">
            {summary.actual_exit_ts
              ? fmtMsDateTimeCst(_isoToMs(summary.actual_exit_ts))
              : "—（未卖出）"}
          </div>
        </div>
        <div className="rounded-md border p-3">
          <div className="text-xs text-muted-foreground">权益差值（因子 − 实际）</div>
          <div className={`mt-1 text-sm font-bold ${summary.equity_diff > 0 ? "text-emerald-600" : summary.equity_diff < 0 ? "text-red-500" : "text-muted-foreground"}`}>
            {summary.equity_diff > 0 ? "+" : ""}{summary.equity_diff.toFixed(2)}
            <span className="ml-2 text-xs font-normal text-muted-foreground">
              因子: ${summary.factor_final_equity.toFixed(2)} / 实际: ${summary.actual_final_equity.toFixed(2)}
            </span>
          </div>
        </div>
      </div>

      {/* ── Timeline chart ─────────────────────────────────────────── */}
      {chartData.length > 0 && (
        <div className="rounded-lg border p-4">
          <h3 className="mb-3 text-sm font-medium text-muted-foreground">
            因子退出信号时间线
            <span className="ml-2 text-[10px]">
              composite_score &gt; 0.3 = 持有区 · &lt; -0.3 = 清仓区
            </span>
          </h3>
          <ResponsiveContainer width="100%" height={320}>
            <ComposedChart data={chartData} margin={{ top: 5, right: 30, bottom: 5, left: 5 }}>
              <CartesianGrid strokeDasharray="3 3" opacity={0.3} />
              <XAxis dataKey="time" tick={{ fontSize: 10 }} interval="preserveStartEnd" />
              <YAxis
                yAxisId="score"
                domain={[-1, 1]}
                tick={{ fontSize: 10 }}
                label={{ value: "Score", angle: -90, position: "insideLeft", style: { fontSize: 10 } }}
              />
              <YAxis
                yAxisId="pct"
                orientation="right"
                domain={[0, 100]}
                tick={{ fontSize: 10 }}
                label={{ value: "仓位%", angle: 90, position: "insideRight", style: { fontSize: 10 } }}
              />
              <Tooltip
                labelFormatter={(_, payload) => payload?.[0]?.payload?.fullTime ?? ""}
                formatter={(value: number, name: string) => {
                  if (name === "score") return [value.toFixed(4), "综合评分"]
                  if (name === "position_pct") return [`${value.toFixed(0)}%`, "建议仓位"]
                  if (name === "poly_price") return [`$${value.toFixed(4)}`, "Poly价格"]
                  if (name === "sim_equity") return [`$${value.toFixed(2)}`, "模拟权益"]
                  return [value, name]
                }}
              />
              <Legend
                formatter={(value) => {
                  const labels: Record<string, string> = {
                    score: "综合评分",
                    position_pct: "建议仓位%",
                    poly_price: "Poly价格",
                    sim_equity: "模拟权益",
                  }
                  return labels[value] ?? value
                }}
              />

              {/* Hold zone (green) */}
              <ReferenceLine yAxisId="score" y={0.3} stroke="hsl(142, 71%, 45%)" strokeDasharray="5 3" strokeOpacity={0.6} />
              {/* Exit zone (red) */}
              <ReferenceLine yAxisId="score" y={-0.3} stroke="hsl(0, 84%, 60%)" strokeDasharray="5 3" strokeOpacity={0.6} />
              <ReferenceLine yAxisId="score" y={0} stroke="hsl(var(--border))" strokeDasharray="2 2" />

              {/* Buy reference */}
              {buyMs && (
                <ReferenceLine
                  x={fmtMsTimeCst(buyMs)}
                  stroke="hsl(142, 71%, 45%)"
                  strokeWidth={2}
                  label={{ value: "买入", position: "top", fill: "hsl(142, 71%, 45%)", fontSize: 10 }}
                />
              )}
              {/* Sell reference */}
              {sellMs && (
                <ReferenceLine
                  x={fmtMsTimeCst(sellMs)}
                  stroke="hsl(0, 84%, 60%)"
                  strokeWidth={2}
                  label={{ value: "卖出", position: "top", fill: "hsl(0, 84%, 60%)", fontSize: 10 }}
                />
              )}
              {/* Factor first reduce */}
              {summary.first_reduce_ts && (
                <ReferenceLine
                  x={fmtMsTimeCst(summary.first_reduce_ts)}
                  stroke="hsl(45, 93%, 47%)"
                  strokeWidth={1.5}
                  strokeDasharray="4 2"
                  label={{ value: "因子减仓", position: "top", fill: "hsl(45, 93%, 47%)", fontSize: 9 }}
                />
              )}
              {/* Factor first exit */}
              {summary.first_exit_ts && (
                <ReferenceLine
                  x={fmtMsTimeCst(summary.first_exit_ts)}
                  stroke="hsl(0, 84%, 60%)"
                  strokeWidth={1.5}
                  strokeDasharray="4 2"
                  label={{ value: "因子清仓", position: "top", fill: "hsl(0, 84%, 60%)", fontSize: 9 }}
                />
              )}

              <Area
                yAxisId="score"
                dataKey="score"
                stroke="hsl(221, 83%, 53%)"
                fill="hsl(221, 83%, 53%)"
                fillOpacity={0.15}
                strokeWidth={1.5}
                dot={false}
              />
              <Line
                yAxisId="pct"
                dataKey="position_pct"
                stroke="hsl(280, 67%, 50%)"
                strokeWidth={2}
                dot={false}
                strokeDasharray="4 2"
              />
              {chartData.some((d) => d.poly_price !== null) && (
                <Line
                  yAxisId="score"
                  dataKey="poly_price"
                  stroke="hsl(var(--foreground))"
                  strokeWidth={1}
                  dot={false}
                  strokeOpacity={0.4}
                  hide
                />
              )}
              {chartData.some((d) => d.sim_equity !== null) && (
                <Line
                  yAxisId="pct"
                  dataKey="sim_equity"
                  stroke="hsl(142, 71%, 45%)"
                  strokeWidth={1.5}
                  dot={false}
                />
              )}
            </ComposedChart>
          </ResponsiveContainer>
        </div>
      )}

      {/* ── Key transition table ───────────────────────────────────── */}
      {keyPoints.length > 0 && (
        <div className="rounded-lg border p-4">
          <h3 className="mb-3 text-sm font-medium text-muted-foreground">
            关键时间点（动作变更节点）
          </h3>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b text-left text-xs text-muted-foreground">
                  <th className="px-2 py-1.5">时间</th>
                  <th className="px-2 py-1.5">连续性</th>
                  <th className="px-2 py-1.5">加速度</th>
                  <th className="px-2 py-1.5">量价耦合</th>
                  <th className="px-2 py-1.5">综合评分</th>
                  <th className="px-2 py-1.5">动作</th>
                  <th className="px-2 py-1.5">建议仓位</th>
                </tr>
              </thead>
              <tbody>
                {keyPoints.map((pt) => {
                  const style = ACTION_STYLE[pt.action] ?? ACTION_STYLE.hold
                  return (
                    <tr key={pt.time_ms} className={`border-b ${style.bg}`}>
                      <td className="px-2 py-1.5 font-mono text-xs">
                        {fmtMsDateTimeCst(pt.time_ms)}
                      </td>
                      <td className="px-2 py-1.5 text-xs">
                        {pt.streak}根 <span className="text-muted-foreground">({pt.streak_norm.toFixed(2)})</span>
                      </td>
                      <td className="px-2 py-1.5 text-xs">
                        {(pt.acceleration * 100).toFixed(4)}%
                        <span className="text-muted-foreground"> ({pt.accel_norm.toFixed(2)})</span>
                      </td>
                      <td className="px-2 py-1.5 text-xs">
                        {(pt.vol_coupling * 10000).toFixed(2)}bp
                        <span className="text-muted-foreground"> ({pt.vol_coupling_norm.toFixed(2)})</span>
                      </td>
                      <td className="px-2 py-1.5 font-bold text-xs">
                        <span className={pt.composite_score > 0.3 ? "text-emerald-600" : pt.composite_score < -0.3 ? "text-red-500" : "text-amber-600"}>
                          {pt.composite_score > 0 ? "+" : ""}{pt.composite_score.toFixed(4)}
                        </span>
                      </td>
                      <td className={`px-2 py-1.5 text-xs font-bold ${style.color}`}>
                        {style.label}
                      </td>
                      <td className="px-2 py-1.5 text-xs font-bold">
                        {(pt.suggested_position_pct * 100).toFixed(0)}%
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  )
}
