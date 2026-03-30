import { useParams, Link } from "react-router-dom"
import { useQuery } from "@tanstack/react-query"
import { fetchResult } from "@/api/client"
import type { BacktestResult } from "@/types"
import MetricsPanel from "@/components/MetricsPanel"
import EquityCurveChart from "@/components/EquityCurveChart"
import TradesTable from "@/components/TradesTable"

export default function ResultDetailPage() {
  const { sessionId } = useParams<{ sessionId: string }>()

  const { data: result, isLoading, error } = useQuery<BacktestResult>({
    queryKey: ["result", sessionId],
    queryFn: () => fetchResult(sessionId!),
    enabled: !!sessionId,
  })

  if (isLoading) {
    return <div className="py-12 text-center text-muted-foreground">加载中...</div>
  }
  if (error || !result) {
    return <div className="py-12 text-center text-destructive">加载失败</div>
  }

  return (
    <div className="flex flex-col gap-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <div className="flex items-center gap-2">
            <Link to="/results" className="text-sm text-muted-foreground hover:text-foreground">
              ← 返回列表
            </Link>
          </div>
          <h1 className="mt-1 text-2xl font-bold tracking-tight">
            {result.strategy}
            <span className="ml-2 text-base font-normal text-muted-foreground">
              {result.slug}
            </span>
          </h1>
          <div className="mt-1 flex gap-3 text-sm text-muted-foreground">
            <span>ID: {result.session_id}</span>
            <span>·</span>
            <span>耗时: {result.duration_seconds.toFixed(2)}s</span>
            <span>·</span>
            <span>{result.created_at.slice(0, 19).replace("T", " ")}</span>
          </div>
        </div>
        <div className="text-right">
          <div className="text-2xl font-bold">
            ${result.final_equity.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
          </div>
          <div className={result.metrics.total_return_pct >= 0 ? "text-sm text-emerald-600" : "text-sm text-red-500"}>
            {result.metrics.total_return_pct >= 0 ? "+" : ""}
            {result.metrics.total_return_pct.toFixed(2)}%
            {" "}(${result.metrics.total_pnl.toFixed(2)})
          </div>
        </div>
      </div>

      {/* Metrics panel */}
      <MetricsPanel metrics={result.metrics} />

      {/* Equity curve */}
      {result.equity_curve.length > 0 && (
        <div className="rounded-lg border p-4">
          <h2 className="mb-3 text-sm font-medium text-muted-foreground">权益曲线</h2>
          <EquityCurveChart
            equityCurve={result.equity_curve}
            drawdownCurve={result.drawdown_curve}
          />
        </div>
      )}

      {/* Trades table */}
      {result.trades.length > 0 && (
        <div className="rounded-lg border p-4">
          <h2 className="mb-3 text-sm font-medium text-muted-foreground">
            交易明细 ({result.trades.length} 笔)
          </h2>
          <TradesTable trades={result.trades} />
        </div>
      )}

      {/* Strategy config */}
      {Object.keys(result.config).length > 0 && (
        <div className="rounded-lg border p-4">
          <h2 className="mb-3 text-sm font-medium text-muted-foreground">策略配置</h2>
          <pre className="rounded-md bg-muted p-3 text-xs">
            {JSON.stringify(result.config, null, 2)}
          </pre>
        </div>
      )}
    </div>
  )
}
