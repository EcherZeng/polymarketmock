import { useEffect, useRef, useMemo } from "react"
import { useQuery } from "@tanstack/react-query"
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { Skeleton } from "@/components/ui/skeleton"
import { createChart, LineSeries, type IChartApi, type ISeriesApi, type LineData, type Time } from "lightweight-charts"
import { fetchMidpoint } from "@/api/client"
import type { WsBestBidAskEvent } from "@/types"

interface PriceChartProps {
  /** All token IDs for this market (e.g. [upTokenId, downTokenId]) */
  tokens: string[]
  /** Outcome labels matching tokens (e.g. ["Up", "Down"]) */
  outcomes: string[]
  /** Per-token WS best_bid_ask (keyed by token id) */
  wsBestBidAsks?: Record<string, WsBestBidAskEvent>
  wsConnected?: boolean
  /** Per-token mid price from replay snapshot (replay mode — skips HTTP/WS) */
  replayMid?: Record<string, number>
  /** ISO timestamp from replay snapshot (used as x-axis time) */
  replayTimestamp?: string
}

const SERIES_COLORS = ["#22c55e", "#ef4444"]  // green for Up, red for Down

export default function PriceChart({ tokens, outcomes, wsBestBidAsks, wsConnected, replayMid, replayTimestamp }: PriceChartProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const chartRef = useRef<IChartApi | null>(null)
  const seriesMapRef = useRef<Map<string, ISeriesApi<"Line">>>(new Map())
  const dataMapRef = useRef<Map<string, LineData<Time>[]>>(new Map())

  const isReplay = !!replayMid

  // Stable key for chart recreation
  const tokenKey = useMemo(() => tokens.join(","), [tokens.join(",")])

  const token0 = tokens[0] ?? ""
  const token1 = tokens[1] ?? ""

  // HTTP polling fallback per token
  const hasWsBBA0 = !!(wsConnected && wsBestBidAsks?.[token0])
  const { data: mid0 } = useQuery({
    queryKey: ["midpoint", token0],
    queryFn: () => fetchMidpoint(token0),
    refetchInterval: hasWsBBA0 ? false : 1_000,
    enabled: !!token0 && !hasWsBBA0 && !isReplay,
  })

  const hasWsBBA1 = !!(wsConnected && wsBestBidAsks?.[token1])
  const { data: mid1 } = useQuery({
    queryKey: ["midpoint", token1],
    queryFn: () => fetchMidpoint(token1),
    refetchInterval: hasWsBBA1 ? false : 1_000,
    enabled: !!token1 && !hasWsBBA1 && !isReplay,
  })

  // Create chart + series
  useEffect(() => {
    if (!containerRef.current) return
    const el = containerRef.current

    const chart = createChart(el, {
      width: el.clientWidth,
      height: 220,
      layout: {
        background: { color: "#ffffff" },
        textColor: "#787878",
        fontSize: 10,
      },
      grid: {
        vertLines: { color: "#e8e8e8" },
        horzLines: { color: "#e8e8e8" },
      },
      timeScale: { timeVisible: true, secondsVisible: true },
      rightPriceScale: { borderColor: "#e8e8e8" },
    })
    chartRef.current = chart

    const newSeriesMap = new Map<string, ISeriesApi<"Line">>()
    const newDataMap = new Map<string, LineData<Time>[]>()
    tokens.forEach((tid, i) => {
      const series = chart.addSeries(LineSeries, {
        color: SERIES_COLORS[i] ?? "#2962ff",
        lineWidth: 2,
        title: outcomes[i] ?? `Token ${i + 1}`,
        priceFormat: { type: "custom", formatter: (p: number) => `${(p * 100).toFixed(1)}¢` },
      })
      newSeriesMap.set(tid, series)
      newDataMap.set(tid, [])
    })
    seriesMapRef.current = newSeriesMap
    dataMapRef.current = newDataMap

    const observer = new ResizeObserver(() => {
      if (containerRef.current) chart.applyOptions({ width: containerRef.current.clientWidth })
    })
    observer.observe(el)

    return () => {
      observer.disconnect()
      chart.remove()
      chartRef.current = null
      seriesMapRef.current = new Map()
      dataMapRef.current = new Map()
    }
  }, [tokenKey]) // eslint-disable-line react-hooks/exhaustive-deps

  // Push HTTP data for token0
  useEffect(() => {
    if (!mid0 || (wsConnected && wsBestBidAsks?.[token0])) return
    pushPoint(token0, mid0.mid)
  }, [mid0, wsConnected, wsBestBidAsks]) // eslint-disable-line react-hooks/exhaustive-deps

  // Push HTTP data for token1
  useEffect(() => {
    if (!mid1 || (wsConnected && wsBestBidAsks?.[token1])) return
    pushPoint(token1, mid1.mid)
  }, [mid1, wsConnected, wsBestBidAsks]) // eslint-disable-line react-hooks/exhaustive-deps

  // Push WS data for all tokens
  useEffect(() => {
    if (!wsBestBidAsks) return
    for (const tid of tokens) {
      const bba = wsBestBidAsks[tid]
      if (!bba) continue
      const bestBid = parseFloat(bba.best_bid)
      const bestAsk = parseFloat(bba.best_ask)
      const mid = (bestBid + bestAsk) / 2
      if (mid > 0) pushPoint(tid, mid)
    }
  }, [wsBestBidAsks]) // eslint-disable-line react-hooks/exhaustive-deps

  const lastReplayTsRef = useRef<number>(0)

  // Push replay data
  useEffect(() => {
    if (!replayMid || !replayTimestamp) return
    const ts = Math.floor(new Date(replayTimestamp).getTime() / 1000) as Time
    const tsNum = ts as number

    // Seek backward detected — clear chart data and rebuild
    if (tsNum < lastReplayTsRef.current) {
      for (const tid of tokens) {
        const data = dataMapRef.current.get(tid)
        const series = seriesMapRef.current.get(tid)
        if (data && series) {
          // Keep only data points before the new timestamp
          const trimmed = data.filter((d) => (d.time as number) <= tsNum)
          dataMapRef.current.set(tid, trimmed)
          series.setData(trimmed)
        }
      }
    }
    lastReplayTsRef.current = tsNum

    for (const tid of tokens) {
      const mid = replayMid[tid]
      if (mid && mid > 0) pushPoint(tid, mid, ts)
    }
  }, [replayMid, replayTimestamp]) // eslint-disable-line react-hooks/exhaustive-deps

  function pushPoint(tokenId: string, value: number, time?: Time) {
    const series = seriesMapRef.current.get(tokenId)
    const data = dataMapRef.current.get(tokenId)
    if (!series || !data) return

    const now = (time ?? Math.floor(Date.now() / 1000)) as Time
    const last = data[data.length - 1]

    if (last && last.time >= now) {
      // Same or older second — update last point in-place to avoid duplicate timestamp
      last.value = value
      series.update(last)
    } else {
      const point: LineData<Time> = { time: now, value }
      data.push(point)
      series.update(point)
    }
  }

  const hasAnyData = !!(mid0 || mid1 || isReplay || (wsBestBidAsks && Object.keys(wsBestBidAsks).length > 0))

  return (
    <Card>
      <CardHeader className="pb-2">
        <div className="flex items-center justify-between">
          <CardTitle className="text-sm">Price</CardTitle>
          <div className="flex items-center gap-3">
            {tokens.map((_, i) => (
              <span key={i} className="flex items-center gap-1 text-[10px] text-muted-foreground">
                <span className="inline-block h-2 w-2 rounded-full" style={{ backgroundColor: SERIES_COLORS[i] ?? "#2962ff" }} />
                {outcomes[i] ?? `Token ${i + 1}`}
              </span>
            ))}
          </div>
        </div>
      </CardHeader>
      <CardContent className="p-2">
        {!hasAnyData && <Skeleton className="h-48 w-full" />}
        <div ref={containerRef} />
      </CardContent>
    </Card>
  )
}
