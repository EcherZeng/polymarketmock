import { useMemo, useState } from "react"
import {
  ResponsiveContainer,
  ComposedChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  Line,
} from "recharts"
import type { BtcKline } from "@/types"

interface BtcKlineChartProps {
  klines: BtcKline[]
}

interface CandleData {
  time: string
  fullTime: string
  open: number
  high: number
  low: number
  close: number
  volume: number
  // For candlestick rendering via stacked bars
  base: number
  body: number
  isUp: boolean
  wickLow: number
  wickHigh: number
}

import { fmtMsTimeCst, fmtMsDateTimeCst } from "@/lib/utils"

function formatTime(ms: number): string {
  return fmtMsTimeCst(ms)
}

function formatDate(ms: number): string {
  return fmtMsDateTimeCst(ms)
}

type ViewMode = "candle" | "volume"

export default function BtcKlineChart({ klines }: BtcKlineChartProps) {
  const [viewMode, setViewMode] = useState<ViewMode>("candle")

  const data: CandleData[] = useMemo(
    () =>
      klines.map((k) => {
        const isUp = k.close >= k.open
        const bodyTop = Math.max(k.open, k.close)
        const bodyBottom = Math.min(k.open, k.close)
        return {
          time: formatTime(k.open_time),
          fullTime: formatDate(k.open_time),
          open: k.open,
          high: k.high,
          low: k.low,
          close: k.close,
          volume: k.volume,
          base: bodyBottom,
          body: bodyTop - bodyBottom || 0.01,
          isUp,
          wickLow: bodyBottom - k.low,
          wickHigh: k.high - bodyTop,
        }
      }),
    [klines],
  )

  if (data.length === 0) return null

  const priceMin = Math.min(...data.map((d) => d.low))
  const priceMax = Math.max(...data.map((d) => d.high))
  const pricePadding = (priceMax - priceMin) * 0.05 || 10
  const domainMin = Math.floor(priceMin - pricePadding)
  const domainMax = Math.ceil(priceMax + pricePadding)

  return (
    <div className="flex flex-col gap-3">
      {/* Tab switcher */}
      <div className="flex gap-2">
        <button
          onClick={() => setViewMode("candle")}
          className={`rounded-md px-3 py-1 text-sm transition-colors ${
            viewMode === "candle"
              ? "bg-foreground text-background"
              : "bg-muted text-muted-foreground hover:text-foreground"
          }`}
        >
          K线图
        </button>
        <button
          onClick={() => setViewMode("volume")}
          className={`rounded-md px-3 py-1 text-sm transition-colors ${
            viewMode === "volume"
              ? "bg-foreground text-background"
              : "bg-muted text-muted-foreground hover:text-foreground"
          }`}
        >
          成交量柱状图
        </button>
      </div>

      {/* Candlestick Chart */}
      {viewMode === "candle" && (
        <div className="h-80">
          <ResponsiveContainer width="100%" height="100%">
            <ComposedChart data={data} barCategoryGap="20%">
              <CartesianGrid strokeDasharray="3 3" opacity={0.3} />
              <XAxis
                dataKey="time"
                tick={{ fontSize: 11 }}
                interval="preserveStartEnd"
              />
              <YAxis
                domain={[domainMin, domainMax]}
                tickFormatter={(v: number) => `$${v.toLocaleString()}`}
                tick={{ fontSize: 11 }}
                width={80}
              />
              <Tooltip
                labelFormatter={(_v, payload) => {
                  const item = payload?.[0]?.payload
                  return item?.fullTime ?? _v
                }}
                formatter={() => null}
                content={({ active, payload }) => {
                  if (!active || !payload?.length) return null
                  const d = payload[0].payload as CandleData
                  return (
                    <div className="rounded-md border bg-background p-2 text-xs shadow-md">
                      <div className="mb-1 font-medium">{d.fullTime}</div>
                      <div className="grid grid-cols-2 gap-x-4 gap-y-0.5">
                        <span className="text-muted-foreground">开:</span>
                        <span>${d.open.toLocaleString(undefined, { minimumFractionDigits: 2 })}</span>
                        <span className="text-muted-foreground">高:</span>
                        <span>${d.high.toLocaleString(undefined, { minimumFractionDigits: 2 })}</span>
                        <span className="text-muted-foreground">低:</span>
                        <span>${d.low.toLocaleString(undefined, { minimumFractionDigits: 2 })}</span>
                        <span className="text-muted-foreground">收:</span>
                        <span className={d.isUp ? "text-emerald-600" : "text-red-500"}>
                          ${d.close.toLocaleString(undefined, { minimumFractionDigits: 2 })}
                        </span>
                        <span className="text-muted-foreground">量:</span>
                        <span>{d.volume.toFixed(4)} BTC</span>
                      </div>
                    </div>
                  )
                }}
              />
              {/* Invisible line for high/low to set domain */}
              <Line
                type="monotone"
                dataKey="high"
                stroke="transparent"
                dot={false}
                activeDot={false}
                legendType="none"
              />
              <Line
                type="monotone"
                dataKey="low"
                stroke="transparent"
                dot={false}
                activeDot={false}
                legendType="none"
              />
              {/* Open price line — X axis is open_time so Y must be the open price at that instant */}
              <Line
                type="monotone"
                dataKey="open"
                stroke="hsl(217, 91%, 60%)"
                strokeWidth={1.5}
                dot={false}
                name="BTC 价格"
              />
              <Legend />
            </ComposedChart>
          </ResponsiveContainer>
        </div>
      )}

      {/* Volume Chart */}
      {viewMode === "volume" && (
        <div className="h-64">
          <ResponsiveContainer width="100%" height="100%">
            <ComposedChart data={data} barCategoryGap="20%">
              <CartesianGrid strokeDasharray="3 3" opacity={0.3} />
              <XAxis
                dataKey="time"
                tick={{ fontSize: 11 }}
                interval="preserveStartEnd"
              />
              <YAxis
                tickFormatter={(v: number) => v.toFixed(2)}
                tick={{ fontSize: 11 }}
                width={70}
                label={{
                  value: "BTC",
                  angle: -90,
                  position: "insideLeft",
                  style: { fontSize: 11 },
                }}
              />
              <Tooltip
                labelFormatter={(_v, payload) => {
                  const item = payload?.[0]?.payload
                  return item?.fullTime ?? _v
                }}
                content={({ active, payload }) => {
                  if (!active || !payload?.length) return null
                  const d = payload[0].payload as CandleData
                  return (
                    <div className="rounded-md border bg-background p-2 text-xs shadow-md">
                      <div className="mb-1 font-medium">{d.fullTime}</div>
                      <div className="grid grid-cols-2 gap-x-4 gap-y-0.5">
                        <span className="text-muted-foreground">成交量:</span>
                        <span>{d.volume.toFixed(4)} BTC</span>
                        <span className="text-muted-foreground">收盘:</span>
                        <span className={d.isUp ? "text-emerald-600" : "text-red-500"}>
                          ${d.close.toLocaleString(undefined, { minimumFractionDigits: 2 })}
                        </span>
                      </div>
                    </div>
                  )
                }}
              />
              <Bar
                dataKey="volume"
                name="成交量"
                fill="hsl(217, 91%, 60%)"
                opacity={0.8}
              />
              <Legend />
            </ComposedChart>
          </ResponsiveContainer>
        </div>
      )}
    </div>
  )
}
