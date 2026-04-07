import { useQuery } from "@tanstack/react-query"
import { useMemo, useState } from "react"
import { Link } from "react-router-dom"
import { cn } from "@/lib/utils"
import { fetchResults } from "@/api/client"
import type { BacktestResultSummary } from "@/types"

export default function DashboardPage() {
  const { data: results = [], isLoading } = useQuery<BacktestResultSummary[]>({
    queryKey: ["results"],
    queryFn: fetchResults,
  })

  const [filterStrategy, setFilterStrategy] = useState<string>("")

  const strategies = useMemo(
    () => [...new Set(results.map((r) => r.strategy))],
    [results],
  )

  const filtered = useMemo(() => {
    const list = filterStrategy ? results.filter((r) => r.strategy === filterStrategy) : results
    return [...list].sort((a, b) => b.created_at.localeCompare(a.created_at))
  }, [results, filterStrategy])

  // Aggregate stats
  const stats = useMemo(() => {
    if (filtered.length === 0) return null
    const returns = filtered.map((r) => r.metrics.total_return_pct)
    const winCount = returns.filter((r) => r > 0).length
    return {
      count: filtered.length,
      avgReturn: returns.reduce((a, b) => a + b, 0) / returns.length * 100,
      winRate: (winCount / returns.length) * 100,
      bestReturn: Math.max(...returns) * 100,
      worstReturn: Math.min(...returns) * 100,
      avgSharpe: filtered.reduce((a, b) => a + b.metrics.sharpe_ratio, 0) / filtered.length,
      avgDrawdown: filtered.reduce((a, b) => a + b.metrics.max_drawdown, 0) / filtered.length * 100,
      totalTrades: filtered.reduce((a, b) => a + b.metrics.total_trades, 0),
    }
  }, [filtered])

  if (isLoading) {
    return <div className="py-12 text-center text-muted-foreground">加载中...</div>
  }

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">回测仪表盘</h1>
        <p className="text-sm text-muted-foreground">
          {results.length} 次回测的汇总分析
        </p>
      </div>

      {results.length === 0 ? (
        <div className="flex flex-col items-center gap-3 py-12 text-muted-foreground">
          <p>暂无回测结果</p>
          <Link to="/" className="text-sm text-primary underline">运行回测</Link>
        </div>
      ) : (
        <>
          {/* Filter */}
          <div className="flex items-center gap-3">
            <span className="text-sm text-muted-foreground">筛选策略:</span>
            <button
              onClick={() => setFilterStrategy("")}
              className={cn(
                "h-8 rounded-md border px-3 text-sm transition-colors",
                !filterStrategy ? "border-primary bg-primary/5 font-medium" : "hover:border-primary/50",
              )}
            >
              全部
            </button>
            {strategies.map((s) => (
              <button
                key={s}
                onClick={() => setFilterStrategy(s)}
                className={cn(
                  "h-8 rounded-md border px-3 text-sm transition-colors",
                  filterStrategy === s ? "border-primary bg-primary/5 font-medium" : "hover:border-primary/50",
                )}
              >
                {s}
              </button>
            ))}
          </div>

          {/* Aggregate stats */}
          {stats && (
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-4 lg:grid-cols-8">
              <StatCard label="回测次数" value={`${stats.count}`} />
              <StatCard
                label="平均收益率"
                value={`${stats.avgReturn >= 0 ? "+" : ""}${stats.avgReturn.toFixed(2)}%`}
                color={stats.avgReturn >= 0 ? "green" : "red"}
              />
              <StatCard
                label="盈利占比"
                value={`${stats.winRate.toFixed(1)}%`}
                color={stats.winRate >= 50 ? "green" : "red"}
              />
              <StatCard label="最佳收益" value={`+${stats.bestReturn.toFixed(2)}%`} color="green" />
              <StatCard label="最差收益" value={`${stats.worstReturn.toFixed(2)}%`} color="red" />
              <StatCard label="平均 Sharpe" value={stats.avgSharpe.toFixed(4)} />
              <StatCard label="平均回撤" value={`${stats.avgDrawdown.toFixed(2)}%`} color="red" />
              <StatCard label="总交易数" value={`${stats.totalTrades}`} />
            </div>
          )}

          {/* Results comparison table */}
          <div className="rounded-lg border">
            <div className="overflow-auto">
              <table className="w-full text-sm">
                <thead className="bg-muted/50">
                  <tr className="border-b text-left text-xs text-muted-foreground">
                    <th className="px-3 py-2">策略</th>
                    <th className="px-3 py-2">数据源</th>
                    <th className="px-3 py-2 text-right">收益率</th>
                    <th className="px-3 py-2 text-right">Sharpe</th>
                    <th className="px-3 py-2 text-right">胜率</th>
                    <th className="px-3 py-2 text-right">最大回撤</th>
                    <th className="px-3 py-2 text-right">盈亏比</th>
                    <th className="px-3 py-2 text-right">交易数</th>
                    <th className="px-3 py-2 text-right">滑点</th>
                    <th className="px-3 py-2"></th>
                  </tr>
                </thead>
                <tbody>
                  {filtered.map((r) => (
                    <tr key={r.session_id} className="border-b hover:bg-muted/30 transition-colors">
                      <td className="px-3 py-2 font-medium">{r.strategy}</td>
                      <td className="px-3 py-2 font-mono text-xs text-muted-foreground">{r.slug}</td>
                      <td className={cn(
                        "px-3 py-2 text-right font-mono",
                        r.metrics.total_return_pct >= 0 ? "text-emerald-600" : "text-red-500",
                      )}>
                        {r.metrics.total_return_pct >= 0 ? "+" : ""}{(r.metrics.total_return_pct * 100).toFixed(2)}%
                      </td>
                      <td className="px-3 py-2 text-right font-mono">{r.metrics.sharpe_ratio.toFixed(4)}</td>
                      <td className="px-3 py-2 text-right font-mono">{(r.metrics.win_rate * 100).toFixed(1)}%</td>
                      <td className="px-3 py-2 text-right font-mono text-red-500">{(r.metrics.max_drawdown * 100).toFixed(2)}%</td>
                      <td className="px-3 py-2 text-right font-mono">
                        {r.metrics.profit_factor === Infinity ? "∞" : r.metrics.profit_factor.toFixed(2)}
                      </td>
                      <td className="px-3 py-2 text-right font-mono">{r.metrics.total_trades}</td>
                      <td className="px-3 py-2 text-right font-mono">{(r.metrics.avg_slippage * 100).toFixed(4)}%</td>
                      <td className="px-3 py-2 text-right">
                        <Link
                          to={`/results/${r.session_id}`}
                          className="text-xs text-primary hover:underline"
                        >
                          详情
                        </Link>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </>
      )}
    </div>
  )
}

function StatCard({ label, value, color }: { label: string; value: string; color?: "green" | "red" }) {
  return (
    <div className="rounded-lg border p-3">
      <div className="text-xs text-muted-foreground">{label}</div>
      <div className={cn(
        "mt-1 text-sm font-semibold",
        color === "green" && "text-emerald-600",
        color === "red" && "text-red-500",
      )}>
        {value}
      </div>
    </div>
  )
}
