import { useMemo } from "react"
import {
  ResponsiveContainer,
  ComposedChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ReferenceDot,
  Legend,
} from "recharts"
import type { PricePoint, TradeRecord } from "@/types"
import { fmtTimeCst, fmtDateTimeCst } from "@/lib/utils"

interface PriceChartProps {
  priceCurve: PricePoint[]
  trades: TradeRecord[]
}

// Shorten token_id for display
function shortToken(tid: string): string {
  if (tid.length > 20) return tid.slice(0, 8) + "..."
  return tid
}

export default function PriceChart({ priceCurve, trades }: PriceChartProps) {
  // Discover unique token_ids and assign labels
  const tokenIds = useMemo(() => {
    const ids = [...new Set(priceCurve.map((p) => p.token_id))]
    return ids.sort()
  }, [priceCurve])

  // Build merged time-series: { timestamp, [token_0]: price, [token_1]: price, anchor_0, anchor_1, ... }
  const merged = useMemo(() => {
    const map = new Map<string, Record<string, number | string>>()
    for (const pt of priceCurve) {
      if (!map.has(pt.timestamp)) {
        map.set(pt.timestamp, { timestamp: pt.timestamp })
      }
      const entry = map.get(pt.timestamp)!
      const idx = tokenIds.indexOf(pt.token_id)
      entry[`token_${idx}`] = pt.mid_price
      if (pt.anchor_price != null) {
        entry[`anchor_${idx}`] = pt.anchor_price
      }
    }
    return [...map.values()].sort((a, b) =>
      String(a.timestamp).localeCompare(String(b.timestamp)),
    )
  }, [priceCurve, tokenIds])

  // Check if anchor data is present
  const hasAnchor = useMemo(
    () => priceCurve.some((p) => p.anchor_price != null && p.anchor_price !== p.mid_price),
    [priceCurve],
  )

  // Map trades to chart reference dots
  const tradeMarkers = useMemo(() => {
    return trades.map((t) => {
      const idx = tokenIds.indexOf(t.token_id)
      return {
        timestamp: t.timestamp,
        tokenKey: `token_${idx}`,
        tokenIdx: idx,
        side: t.side,
        price: t.avg_price,
        amount: t.filled_amount,
      }
    })
  }, [trades, tokenIds])

  if (merged.length === 0) return null

  // Token label: try to determine UP/DOWN from price patterns
  const tokenLabels = useMemo(() => {
    if (tokenIds.length !== 2) return tokenIds.map((id) => shortToken(id))
    // For binary markets: the token with higher price at start is likely UP
    const firstRow = merged[0]
    const p0 = Number(firstRow?.token_0 ?? 0)
    const p1 = Number(firstRow?.token_1 ?? 0)
    if (p0 > p1) return ["UP (Yes)", "DOWN (No)"]
    if (p1 > p0) return ["DOWN (No)", "UP (Yes)"]
    return [shortToken(tokenIds[0]), shortToken(tokenIds[1])]
  }, [tokenIds, merged])

  const tokenColors = ["hsl(142, 71%, 45%)", "hsl(0, 84%, 60%)", "hsl(217, 91%, 60%)", "hsl(47, 96%, 53%)"]

  return (
    <div className="h-72">
      <ResponsiveContainer width="100%" height="100%">
        <ComposedChart data={merged}>
          <CartesianGrid strokeDasharray="3 3" opacity={0.3} />
          <XAxis
            dataKey="timestamp"
            tickFormatter={(v: string) => fmtTimeCst(v)}
            tick={{ fontSize: 11 }}
            interval="preserveStartEnd"
          />
          <YAxis
            domain={[0, 1]}
            tickFormatter={(v: number) => `$${v.toFixed(2)}`}
            tick={{ fontSize: 11 }}
            width={55}
          />
          <Tooltip
            labelFormatter={(v) => fmtDateTimeCst(String(v))}
            formatter={(value, name) => {
              const nameStr = String(name)
              if (nameStr.startsWith("anchor_")) {
                const idx = parseInt(nameStr.replace("anchor_", ""))
                const label = tokenLabels[idx] ?? nameStr
                return [`$${Number(value).toFixed(4)}`, `${label} 锚点`]
              }
              const idx = parseInt(nameStr.replace("token_", ""))
              const label = tokenLabels[idx] ?? nameStr
              return [`$${Number(value).toFixed(4)}`, `${label} Mid`]
            }}
          />
          <Legend
            formatter={(value: string) => {
              if (value.startsWith("anchor_")) {
                const idx = parseInt(value.replace("anchor_", ""))
                return `${tokenLabels[idx] ?? value} 锚点`
              }
              const idx = parseInt(value.replace("token_", ""))
              return tokenLabels[idx] ?? value
            }}
          />

          {/* Mid price lines for each token */}
          {tokenIds.map((_, i) => (
            <Line
              key={`token_${i}`}
              type="monotone"
              dataKey={`token_${i}`}
              stroke={tokenColors[i % tokenColors.length]}
              strokeWidth={2}
              dot={false}
              connectNulls
            />
          ))}

          {/* Anchor price lines (dashed) */}
          {hasAnchor && tokenIds.map((_, i) => (
            <Line
              key={`anchor_${i}`}
              type="monotone"
              dataKey={`anchor_${i}`}
              stroke={tokenColors[i % tokenColors.length]}
              strokeWidth={1.5}
              strokeDasharray="4 3"
              dot={false}
              connectNulls
            />
          ))}

          {/* Trade entry/exit markers */}
          {tradeMarkers.map((m, i) => {
            // Find the data index for this timestamp
            const dataIdx = merged.findIndex((d) => d.timestamp === m.timestamp)
            if (dataIdx < 0) return null
            const yVal = Number(merged[dataIdx]?.[m.tokenKey] ?? m.price)
            return (
              <ReferenceDot
                key={`trade-${i}`}
                x={m.timestamp}
                y={yVal}
                r={5}
                fill={m.side === "BUY" ? "#22c55e" : "#ef4444"}
                stroke="#fff"
                strokeWidth={2}
                ifOverflow="extendDomain"
              />
            )
          })}
        </ComposedChart>
      </ResponsiveContainer>

      {/* Trade legend */}
      {trades.length > 0 && (
        <div className="mt-2 flex items-center justify-center gap-4 text-xs text-muted-foreground">
          <span className="flex items-center gap-1">
            <span className="inline-block size-3 rounded-full bg-green-500" />
            买入 (BUY)
          </span>
          <span className="flex items-center gap-1">
            <span className="inline-block size-3 rounded-full bg-red-500" />
            卖出 (SELL)
          </span>
        </div>
      )}
    </div>
  )
}
