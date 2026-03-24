import { useEffect, useRef } from "react"
import { useQuery } from "@tanstack/react-query"
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { Skeleton } from "@/components/ui/skeleton"
import { createChart, type IChartApi, type ISeriesApi, type LineData, type Time } from "lightweight-charts"
import { fetchMidpoint } from "@/api/client"

interface PriceChartProps {
  tokenId: string
}

export default function PriceChart({ tokenId }: PriceChartProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const chartRef = useRef<IChartApi | null>(null)
  const seriesRef = useRef<ISeriesApi<"Line"> | null>(null)
  const dataRef = useRef<LineData<Time>[]>([])

  const { data: midData } = useQuery({
    queryKey: ["midpoint", tokenId],
    queryFn: () => fetchMidpoint(tokenId),
    refetchInterval: 3_000,
  })

  useEffect(() => {
    if (!containerRef.current) return

    const chart = createChart(containerRef.current, {
      width: containerRef.current.clientWidth,
      height: 200,
      layout: {
        background: { color: "transparent" },
        textColor: "hsl(var(--muted-foreground))",
        fontSize: 10,
      },
      grid: {
        vertLines: { color: "hsl(var(--border))" },
        horzLines: { color: "hsl(var(--border))" },
      },
      timeScale: { timeVisible: true, secondsVisible: true },
      rightPriceScale: {
        borderColor: "hsl(var(--border))",
      },
    })

    const series = chart.addLineSeries({
      color: "hsl(var(--primary))",
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

  useEffect(() => {
    if (!midData || !seriesRef.current) return
    const now = Math.floor(Date.now() / 1000) as Time
    const point: LineData<Time> = { time: now, value: midData.mid }
    dataRef.current.push(point)
    seriesRef.current.setData(dataRef.current)
  }, [midData])

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
