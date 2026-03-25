import { useEffect, useRef } from "react"
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
  tokenId: string
  /** WS best_bid_ask event (if provided, HTTP polling is reduced) */
  wsBestBidAsk?: WsBestBidAskEvent | null
  wsConnected?: boolean
}

export default function PriceChart({ tokenId, wsBestBidAsk, wsConnected }: PriceChartProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const chartRef = useRef<IChartApi | null>(null)
  const seriesRef = useRef<ISeriesApi<"Line"> | null>(null)
  const dataRef = useRef<LineData<Time>[]>([])

  // HTTP polling fallback — disabled when WS is connected
  const { data: midData } = useQuery({
    queryKey: ["midpoint", tokenId],
    queryFn: () => fetchMidpoint(tokenId),
    refetchInterval: wsConnected ? false : 1_000,
    enabled: !wsConnected,
  })

  useEffect(() => {
    if (!containerRef.current) return

    const el = containerRef.current

    const chart = createChart(el, {
      width: el.clientWidth,
      height: 200,
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
      rightPriceScale: {
        borderColor: "#e8e8e8",
      },
    })

    const series = chart.addSeries(LineSeries, {
      color: "#2962ff",
      lineWidth: 2,
      priceFormat: { type: "custom", formatter: (p: number) => `${(p * 100).toFixed(1)}¢` },
    })

    chartRef.current = chart
    seriesRef.current = series

    const observer = new ResizeObserver(() => {
      if (containerRef.current) {
        chart.applyOptions({ width: containerRef.current.clientWidth })
      }
    })
    observer.observe(containerRef.current)

    return () => {
      observer.disconnect()
      chart.remove()
      chartRef.current = null
      seriesRef.current = null
      dataRef.current = []
    }
  }, [tokenId])

  // Push data from HTTP polling
  useEffect(() => {
    if (!midData || !seriesRef.current || wsConnected) return
    const now = Math.floor(Date.now() / 1000) as Time
    const point: LineData<Time> = { time: now, value: midData.mid }
    dataRef.current.push(point)
    seriesRef.current.setData(dataRef.current)
  }, [midData, wsConnected])

  // Push data from WS best_bid_ask events
  useEffect(() => {
    if (!wsBestBidAsk || !seriesRef.current) return
    const bestBid = parseFloat(wsBestBidAsk.best_bid)
    const bestAsk = parseFloat(wsBestBidAsk.best_ask)
    const mid = (bestBid + bestAsk) / 2
    if (mid <= 0) return
    const now = Math.floor(Date.now() / 1000) as Time
    const point: LineData<Time> = { time: now, value: mid }
    // Use update() for single-point append (more efficient than setData)
    dataRef.current.push(point)
    seriesRef.current.update(point)
  }, [wsBestBidAsk])

  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-sm">Price</CardTitle>
      </CardHeader>
      <CardContent className="p-2">
        {!midData && <Skeleton className="h-48 w-full" />}
        <div ref={containerRef} />
      </CardContent>
    </Card>
  )
}
