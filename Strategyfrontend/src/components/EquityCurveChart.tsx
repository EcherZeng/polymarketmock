import { useMemo } from "react"
import {
  ResponsiveContainer,
  ComposedChart,
  Area,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
} from "recharts"
import type { EquityPoint, DrawdownPoint } from "@/types"

interface EquityCurveChartProps {
  equityCurve: EquityPoint[]
  drawdownCurve: DrawdownPoint[]
}

export default function EquityCurveChart({ equityCurve, drawdownCurve }: EquityCurveChartProps) {
  const merged = useMemo(() => {
    // Build drawdown map from server data; fall back to client-side computation
    let ddMap: Map<string, number>
    if (drawdownCurve.length > 0) {
      ddMap = new Map(drawdownCurve.map((d) => [d.timestamp, d.drawdown_pct]))
    } else {
      // Compute drawdown client-side from equity curve
      ddMap = new Map()
      let peak = 0
      for (const pt of equityCurve) {
        if (pt.equity > peak) peak = pt.equity
        const dd = peak > 0 ? ((peak - pt.equity) / peak) * 100 : 0
        ddMap.set(pt.timestamp, Math.round(dd * 10000) / 10000)
      }
    }
    return equityCurve.map((pt) => ({
      timestamp: pt.timestamp,
      equity: pt.equity,
      balance: pt.balance,
      drawdown: ddMap.get(pt.timestamp) ?? 0,
    }))
  }, [equityCurve, drawdownCurve])

  const hasDrawdown = merged.some((d) => d.drawdown > 0)

  if (merged.length === 0) return null

  const minEquity = Math.min(...merged.map((d) => d.equity)) * 0.999
  const maxEquity = Math.max(...merged.map((d) => d.equity)) * 1.001

  return (
    <div className="flex flex-col gap-4">
      {/* Equity chart */}
      <div className="h-64">
        <ResponsiveContainer width="100%" height="100%">
          <ComposedChart data={merged}>
            <CartesianGrid strokeDasharray="3 3" opacity={0.3} />
            <XAxis
              dataKey="timestamp"
              tickFormatter={(v: string) => v.slice(11, 19)}
              tick={{ fontSize: 11 }}
              interval="preserveStartEnd"
            />
            <YAxis
              domain={[minEquity, maxEquity]}
              tickFormatter={(v: number) => `$${v.toFixed(0)}`}
              tick={{ fontSize: 11 }}
              width={70}
            />
            <Tooltip
              labelFormatter={(v) => String(v).slice(0, 19).replace("T", " ")}
              formatter={(value, name) => {
                const n = Number(value)
                if (name === "equity") return [`$${n.toFixed(2)}`, "权益"]
                return [n.toFixed(2), String(name)]
              }}
            />
            <Area
              type="monotone"
              dataKey="equity"
              stroke="hsl(var(--chart-2, 142 71% 45%))"
              fill="hsl(var(--chart-2, 142 71% 45%))"
              fillOpacity={0.1}
              strokeWidth={2}
              dot={false}
            />
          </ComposedChart>
        </ResponsiveContainer>
      </div>

      {/* Drawdown chart — show whenever there are non-zero drawdown values */}
      {hasDrawdown && (
        <div className="h-32">
          <div className="mb-1 text-xs text-muted-foreground">回撤曲线</div>
          <ResponsiveContainer width="100%" height="100%">
            <ComposedChart data={merged}>
              <CartesianGrid strokeDasharray="3 3" opacity={0.3} />
              <XAxis
                dataKey="timestamp"
                tickFormatter={(v: string) => v.slice(11, 19)}
                tick={{ fontSize: 10 }}
                interval="preserveStartEnd"
              />
              <YAxis
                tickFormatter={(v: number) => `${v.toFixed(1)}%`}
                tick={{ fontSize: 10 }}
                width={50}
                reversed
              />
              <Tooltip
                labelFormatter={(v) => String(v).slice(0, 19).replace("T", " ")}
                formatter={(value) => [`${Number(value).toFixed(2)}%`, "回撤"]}
              />
              <Line
                type="monotone"
                dataKey="drawdown"
                stroke="hsl(var(--chart-1, 0 84% 60%))"
                strokeWidth={1.5}
                dot={false}
              />
            </ComposedChart>
          </ResponsiveContainer>
        </div>
      )}
    </div>
  )
}
