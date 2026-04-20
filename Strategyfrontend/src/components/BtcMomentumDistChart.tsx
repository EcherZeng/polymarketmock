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
} from "recharts"

interface BtcMomentumDistChartProps {
  /** raw decimal btc_momentum values (abs(a1+a2)), e.g. 0.003 = 0.3% */
  values: number[]
}

/** Probability density of normal distribution */
function normalPdf(x: number, mean: number, std: number): number {
  if (std === 0) return x === mean ? 1 : 0
  const exp = -0.5 * ((x - mean) / std) ** 2
  return (1 / (std * Math.sqrt(2 * Math.PI))) * Math.exp(exp)
}

/** Build histogram + normal fit with adaptive bin width */
function buildDistribution(pctValues: number[]) {
  if (pctValues.length < 1) return { data: [], stats: null }

  const mean = pctValues.reduce((a, b) => a + b, 0) / pctValues.length
  const variance =
    pctValues.length > 1
      ? pctValues.reduce((a, x) => a + (x - mean) ** 2, 0) / pctValues.length
      : 0
  const std = Math.sqrt(variance)

  const min = Math.min(...pctValues)
  const max = Math.max(...pctValues)
  const range = max - min

  // Adaptive bin width: target ~20-40 bins, round to a nice number
  const rawBin = range / 25 || 0.01
  const nice = [0.001, 0.002, 0.005, 0.01, 0.02, 0.05, 0.1, 0.2, 0.5, 1]
  const binWidth = nice.find((n) => n >= rawBin) ?? rawBin

  const binStart =
    min === max ? min - binWidth / 2 : Math.floor(min / binWidth) * binWidth
  const binEnd =
    min === max ? min + binWidth / 2 : Math.ceil(max / binWidth) * binWidth
  const binCount = Math.max(1, Math.round((binEnd - binStart) / binWidth))

  const counts = new Array(binCount).fill(0)
  for (const v of pctValues) {
    let idx = Math.floor((v - binStart) / binWidth)
    if (idx >= binCount) idx = binCount - 1
    if (idx < 0) idx = 0
    counts[idx]++
  }

  const n = pctValues.length
  const data = counts.map((c, i) => {
    const lo = binStart + i * binWidth
    const mid = lo + binWidth / 2
    const normalCount = n * binWidth * normalPdf(mid, mean, std)
    return {
      range: `${lo.toFixed(3)}`,
      mid,
      count: c,
      normal: Math.round(normalCount * 1000) / 1000,
    }
  })

  return { data, stats: { mean, std, count: pctValues.length } }
}

export default function BtcMomentumDistChart({
  values,
}: BtcMomentumDistChartProps) {
  // Convert raw decimals to percentage for display
  const pctValues = useMemo(() => values.map((v) => v * 100), [values])
  const dist = useMemo(() => buildDistribution(pctValues), [pctValues])

  const hasData = dist.data.length > 0 && dist.stats

  return (
    <div>
      <div className="mb-2 flex flex-wrap items-center gap-4 text-xs text-muted-foreground">
        {hasData && (
          <>
            <span>
              均值: <b>{dist.stats!.mean.toFixed(4)}%</b>
            </span>
            <span>
              标准差: <b>{dist.stats!.std.toFixed(4)}%</b>
            </span>
            <span>
              场次: <b>{dist.stats!.count}</b>
            </span>
          </>
        )}
      </div>
      {hasData ? (
        <div className="h-64">
          <ResponsiveContainer width="100%" height="100%">
            <ComposedChart
              data={dist.data}
              margin={{ top: 5, right: 20, bottom: 5, left: 0 }}
            >
              <CartesianGrid strokeDasharray="3 3" opacity={0.3} />
              <XAxis
                dataKey="range"
                tick={{ fontSize: 10 }}
                label={{
                  value: "BTC动量 abs(a1+a2) (%)",
                  position: "insideBottomRight",
                  offset: -5,
                  fontSize: 11,
                }}
              />
              <YAxis
                tick={{ fontSize: 10 }}
                allowDecimals={false}
                label={{
                  value: "数量",
                  angle: -90,
                  position: "insideLeft",
                  fontSize: 11,
                }}
              />
              <Tooltip
                formatter={(value, name) => {
                  const v = Number(value)
                  if (name === "count") return [v, "数量"]
                  if (name === "normal") return [v.toFixed(2), "正态拟合"]
                  return [v, String(name)]
                }}
                labelFormatter={(l) => `BTC动量: ${l}%`}
              />
              <Legend
                formatter={(value: string) => {
                  if (value === "count") return "实际分布"
                  if (value === "normal") return "正态拟合"
                  return value
                }}
              />
              <Bar
                dataKey="count"
                name="count"
                fill="#f59e0b"
                barSize={999}
                opacity={0.7}
              />
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
          数据不足，无法绘制 BTC 动量分布图
        </div>
      )}
    </div>
  )
}
