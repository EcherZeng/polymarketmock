import { useMemo, useState } from "react"
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
} from "recharts"

interface ReturnDistributionChartProps {
  /** raw decimal returns (e.g. 0.03 = 3%) */
  returns: number[]
}

/** Probability density of normal distribution */
function normalPdf(x: number, mean: number, std: number): number {
  if (std === 0) return x === mean ? 1 : 0
  const exp = -0.5 * ((x - mean) / std) ** 2
  return (1 / (std * Math.sqrt(2 * Math.PI))) * Math.exp(exp)
}

/** Build histogram + normal fit with fixed 0.1% bin width */
function buildDistribution(pctReturns: number[]) {
  if (pctReturns.length < 1) return { data: [], stats: null }

  const mean = pctReturns.reduce((a, b) => a + b, 0) / pctReturns.length
  const variance = pctReturns.length > 1
    ? pctReturns.reduce((a, x) => a + (x - mean) ** 2, 0) / pctReturns.length
    : 0
  const std = Math.sqrt(variance)

  const min = Math.min(...pctReturns)
  const max = Math.max(...pctReturns)

  const binWidth = 0.1
  // Single-value edge case: create one bin centered on the value
  const binStart = min === max ? min - binWidth / 2 : Math.floor(min / binWidth) * binWidth
  const binEnd = min === max ? min + binWidth / 2 : Math.ceil(max / binWidth) * binWidth
  const binCount = Math.max(1, Math.round((binEnd - binStart) / binWidth))

  const counts = new Array(binCount).fill(0)
  for (const v of pctReturns) {
    let idx = Math.floor((v - binStart) / binWidth)
    if (idx >= binCount) idx = binCount - 1
    if (idx < 0) idx = 0
    counts[idx]++
  }

  const n = pctReturns.length
  const data = counts.map((c, i) => {
    const lo = binStart + i * binWidth
    const mid = lo + binWidth / 2
    const density = c / (n * binWidth)
    const normal = normalPdf(mid, mean, std)
    return {
      range: `${lo.toFixed(1)}`,
      mid,
      count: c,
      density: Math.round(density * 1e6) / 1e6,
      normal: Math.round(normal * 1e6) / 1e6,
    }
  })

  return {
    data,
    stats: { mean, std, count: pctReturns.length },
  }
}

export default function ReturnDistributionChart({
  returns,
}: ReturnDistributionChartProps) {
  const [mode, setMode] = useState<"positive" | "negative">("positive")

  const positiveReturns = useMemo(
    () => returns.filter((r) => r > 0).map((r) => r * 100),
    [returns],
  )
  const negativeReturns = useMemo(
    () => returns.filter((r) => r < 0).map((r) => r * 100),
    [returns],
  )

  const positiveDist = useMemo(() => buildDistribution(positiveReturns), [positiveReturns])
  const negativeDist = useMemo(() => buildDistribution(negativeReturns), [negativeReturns])

  const current = mode === "positive" ? positiveDist : negativeDist
  const barColor = mode === "positive" ? "#10b981" : "#ef4444"
  const label = mode === "positive" ? "收益增加" : "收益减少"
  const hasData = current.data.length > 0 && current.stats

  return (
    <div>
      <div className="mb-2 flex items-center justify-between">
        <div className="flex flex-wrap items-center gap-4 text-xs text-muted-foreground">
          {hasData && (
            <>
              <span>
                均值:{" "}
                <b className={current.stats!.mean >= 0 ? "text-emerald-600" : "text-red-500"}>
                  {current.stats!.mean >= 0 ? "+" : ""}{current.stats!.mean.toFixed(2)}%
                </b>
              </span>
              <span>标准差: <b>{current.stats!.std.toFixed(2)}%</b></span>
              <span>场次: <b>{current.stats!.count}</b></span>
            </>
          )}
        </div>
        <div className="flex items-center gap-1">
          {(["positive", "negative"] as const).map((m) => (
            <button
              key={m}
              onClick={() => setMode(m)}
              className={`rounded-md px-2 py-1 text-xs font-medium transition-colors ${
                mode === m
                  ? m === "positive"
                    ? "bg-emerald-600 text-white"
                    : "bg-red-500 text-white"
                  : "bg-muted text-muted-foreground hover:bg-muted/80"
              }`}
            >
              {m === "positive" ? "收益增加" : "收益减少"}
            </button>
          ))}
        </div>
      </div>
      {hasData ? (
      <div className="h-64">
        <ResponsiveContainer width="100%" height="100%">
          <ComposedChart data={current.data} margin={{ top: 5, right: 20, bottom: 5, left: 0 }}>
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
                if (name === "density") return [v.toFixed(4), "实际密度"]
                if (name === "normal") return [v.toFixed(4), "正态拟合"]
                return [v, String(name)]
              }}
              labelFormatter={(l) => `收益率: ${l}%`}
            />
            <Legend
              formatter={(value: string) => {
                if (value === "density") return "实际分布"
                if (value === "normal") return "正态拟合"
                return value
              }}
            />
            <Bar dataKey="density" name="density" fill={barColor} barSize={999} opacity={0.7} />
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
      ) : (
        <div className="flex h-64 items-center justify-center text-sm text-muted-foreground">
          {label}场次不足，无法绘制分布图
        </div>
      )}
    </div>
  )
}
