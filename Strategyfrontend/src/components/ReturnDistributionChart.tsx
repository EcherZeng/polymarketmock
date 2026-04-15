import { useMemo } from "react"
import {
  ResponsiveContainer,
  ComposedChart,
  Bar,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ReferenceLine,
  Cell,
} from "recharts"

interface ReturnDistributionChartProps {
  /** raw decimal returns (e.g. 0.03 = 3%) */
  returns: number[]
  /** number of histogram bins */
  bins?: number
}

/** Probability density of normal distribution */
function normalPdf(x: number, mean: number, std: number): number {
  if (std === 0) return x === mean ? 1 : 0
  const exp = -0.5 * ((x - mean) / std) ** 2
  return (1 / (std * Math.sqrt(2 * Math.PI))) * Math.exp(exp)
}

export default function ReturnDistributionChart({
  returns,
  bins: binsProp,
}: ReturnDistributionChartProps) {
  const data = useMemo(() => {
    if (returns.length < 2) return []

    const pctReturns = returns.map((r) => r * 100)
    const min = Math.min(...pctReturns)
    const max = Math.max(...pctReturns)
    if (min === max) return []

    // Sturges' rule for bin count, clamped to [6, 30]
    const binCount = binsProp ?? Math.max(6, Math.min(30, Math.ceil(1 + Math.log2(pctReturns.length))))
    const binWidth = (max - min) / binCount

    // mean & std
    const mean = pctReturns.reduce((a, b) => a + b, 0) / pctReturns.length
    const variance =
      pctReturns.reduce((a, x) => a + (x - mean) ** 2, 0) / pctReturns.length
    const std = Math.sqrt(variance)

    // build histogram
    const counts = new Array(binCount).fill(0)
    for (const v of pctReturns) {
      let idx = Math.floor((v - min) / binWidth)
      if (idx >= binCount) idx = binCount - 1
      counts[idx]++
    }

    // convert counts to density so histogram area ≈ 1
    const n = pctReturns.length
    return counts.map((c, i) => {
      const lo = min + i * binWidth
      const mid = lo + binWidth / 2
      const density = c / (n * binWidth)
      const normal = normalPdf(mid, mean, std)
      return {
        range: `${lo.toFixed(1)}`,
        mid,
        count: c,
        density: Math.round(density * 1e6) / 1e6,
        normal: Math.round(normal * 1e6) / 1e6,
        isPositive: mid >= 0,
      }
    })
  }, [returns, binsProp])

  const stats = useMemo(() => {
    if (returns.length === 0) return null
    const pct = returns.map((r) => r * 100)
    const mean = pct.reduce((a, b) => a + b, 0) / pct.length
    const variance = pct.reduce((a, x) => a + (x - mean) ** 2, 0) / pct.length
    const std = Math.sqrt(variance)
    const positive = pct.filter((r) => r > 0).length
    const negative = pct.filter((r) => r < 0).length
    return { mean, std, positive, negative }
  }, [returns])

  if (data.length === 0 || !stats) {
    return (
      <div className="flex h-64 items-center justify-center text-sm text-muted-foreground">
        数据不足，无法绘制分布图
      </div>
    )
  }

  return (
    <div>
      <div className="mb-2 flex flex-wrap items-center gap-4 text-xs text-muted-foreground">
        <span>
          均值: <b className={stats.mean >= 0 ? "text-emerald-600" : "text-red-500"}>
            {stats.mean >= 0 ? "+" : ""}{stats.mean.toFixed(2)}%
          </b>
        </span>
        <span>标准差: <b>{stats.std.toFixed(2)}%</b></span>
        <span>
          收益增加: <b className="text-emerald-600">{stats.positive}</b> 场
        </span>
        <span>
          收益减少: <b className="text-red-500">{stats.negative}</b> 场
        </span>
      </div>
      <div className="h-64">
        <ResponsiveContainer width="100%" height="100%">
          <ComposedChart data={data} margin={{ top: 5, right: 20, bottom: 5, left: 0 }}>
            <CartesianGrid strokeDasharray="3 3" opacity={0.3} />
            <XAxis
              dataKey="range"
              tick={{ fontSize: 10 }}
              label={{ value: "收益率 (%)", position: "insideBottomRight", offset: -5, fontSize: 11 }}
            />
            <YAxis
              tick={{ fontSize: 10 }}
              label={{ value: "密度", angle: -90, position: "insideLeft", fontSize: 11 }}
            />
            <Tooltip
              formatter={(value, name) => {
                const v = Number(value)
                if (name === "count") return [v, "场次"]
                if (name === "density") return [v.toFixed(4), "实际密度"]
                if (name === "normal") return [v.toFixed(4), "正态拟合"]
                return [v, String(name)]
              }}
              labelFormatter={(label) => `收益率: ${label}%`}
            />
            <Legend
              formatter={(value: string) => {
                if (value === "density") return "实际分布"
                if (value === "normal") return "正态拟合"
                return value
              }}
            />
            <ReferenceLine x={data.find((d) => d.mid >= 0)?.range} stroke="#888" strokeDasharray="3 3" />
            <Bar dataKey="density" name="density" barSize={999} opacity={0.7}>
              {data.map((entry, idx) => (
                <Cell
                  key={idx}
                  fill={entry.isPositive ? "#10b981" : "#ef4444"}
                />
              ))}
            </Bar>
            <Line
              type="monotone"
              dataKey="normal"
              name="normal"
              stroke="#6366f1"
              strokeWidth={2}
              dot={false}
            />
          </ComposedChart>
        </ResponsiveContainer>
      </div>
    </div>
  )
}
