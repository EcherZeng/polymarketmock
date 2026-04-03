import { useParams, Link } from "react-router-dom"
import { useQuery } from "@tanstack/react-query"
import { fetchResult, fetchBtcKlines } from "@/api/client"
import type { BacktestResult, BtcKlineResponse } from "@/types"
import MetricsPanel from "@/components/MetricsPanel"
import EquityCurveChart from "@/components/EquityCurveChart"
import PriceChart from "@/components/PriceChart"
import AnchorBulletin from "@/components/AnchorBulletin"
import DrawdownTable from "@/components/DrawdownTable"
import TradesTable from "@/components/TradesTable"
import BtcKlineChart from "@/components/BtcKlineChart"

export default function ResultDetailPage() {
  const { sessionId } = useParams<{ sessionId: string }>()

  const { data: result, isLoading, error } = useQuery<BacktestResult>({
    queryKey: ["result", sessionId],
    queryFn: () => fetchResult(sessionId!),
    enabled: !!sessionId,
  })

  const { data: btcKlines, isLoading: btcLoading } = useQuery<BtcKlineResponse>({
    queryKey: ["btc-klines", sessionId],
    queryFn: () => fetchBtcKlines(sessionId!),
    enabled: !!sessionId,
  })

  if (isLoading) {
    return <div className="py-12 text-center text-muted-foreground">加载中...</div>
  }
  if (error || !result) {
    return <div className="py-12 text-center text-destructive">加载失败</div>
  }

  const hasSettlement = result.settlement_result && Object.keys(result.settlement_result).length > 0

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

      {/* Settlement info */}
      {hasSettlement && (
        <div className="rounded-lg border p-4">
          <h2 className="mb-3 text-sm font-medium text-muted-foreground">结算信息</h2>
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            {Object.entries(result.settlement_result).map(([tokenId, price]) => (
              <div key={tokenId} className="rounded-md border p-3">
                <div className="truncate text-xs text-muted-foreground font-mono" title={tokenId}>
                  {tokenId.slice(0, 12)}...
                </div>
                <div className="mt-1 flex items-center gap-2">
                  <span className={
                    price >= 0.95
                      ? "text-sm font-bold text-emerald-600"
                      : price <= 0.05
                        ? "text-sm font-bold text-red-500"
                        : "text-sm font-bold text-muted-foreground"
                  }>
                    ${price.toFixed(2)}
                  </span>
                  <span className="text-xs text-muted-foreground">
                    {price >= 0.95 ? "YES" : price <= 0.05 ? "NO" : "未定"}
                  </span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Price chart with entry/exit points */}
      {result.price_curve && result.price_curve.length > 0 && (
        <div className="rounded-lg border p-4">
          <h2 className="mb-3 text-sm font-medium text-muted-foreground">价格走势与交易点位</h2>
          <PriceChart
            priceCurve={result.price_curve}
            trades={result.trades}
          />
        </div>
      )}

      {/* Anchor price bulletin */}
      {result.price_curve && result.price_curve.length > 0 && (
        <AnchorBulletin priceCurve={result.price_curve} />
      )}

      {/* BTC/USDT kline chart from Binance */}
      <div className="rounded-lg border p-4">
        <h2 className="mb-3 text-sm font-medium text-muted-foreground">
          BTC/USDT 1分钟K线（Binance）
        </h2>
        {btcLoading ? (
          <div className="py-8 text-center text-sm text-muted-foreground">加载 BTC K线数据中...</div>
        ) : btcKlines && btcKlines.klines.length > 0 ? (
          <BtcKlineChart klines={btcKlines.klines} />
        ) : (
          <div className="py-8 text-center text-sm text-muted-foreground">暂无 BTC K线数据</div>
        )}
      </div>

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

      {/* Drawdown events table */}
      {result.drawdown_events && result.drawdown_events.length > 0 && (
        <div className="rounded-lg border p-4">
          <h2 className="mb-3 text-sm font-medium text-muted-foreground">
            回撤事件 ({result.drawdown_events.length} 次)
          </h2>
          <DrawdownTable events={result.drawdown_events} />
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
