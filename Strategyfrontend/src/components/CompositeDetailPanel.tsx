import { useMemo } from "react"
import type { CompositePreset, BatchResultSummary } from "@/types"

interface CompositeDetailPanelProps {
  compositeDetail: CompositePreset
  compositeName: string
  results: Record<string, BatchResultSummary>
}

export default function CompositeDetailPanel({
  compositeDetail,
  compositeName,
  results,
}: CompositeDetailPanelProps) {
  const { branches, btc_windows } = compositeDetail

  // Compute distribution stats: how many slugs matched each branch
  const distribution = useMemo(() => {
    const branchCounts: Record<string, number> = {}
    let skipCount = 0
    const total = Object.keys(results).length

    for (const branch of branches) {
      branchCounts[branch.label] = 0
    }

    for (const r of Object.values(results)) {
      if (r.matched_branch) {
        branchCounts[r.matched_branch] = (branchCounts[r.matched_branch] || 0) + 1
      } else {
        skipCount++
      }
    }

    return { branchCounts, skipCount, total }
  }, [branches, results])

  // Compute per-branch avg return
  const branchStats = useMemo(() => {
    const stats: Record<string, { count: number; sumReturn: number; sumTrades: number }> = {}
    for (const branch of branches) {
      stats[branch.label] = { count: 0, sumReturn: 0, sumTrades: 0 }
    }
    stats["未匹配"] = { count: 0, sumReturn: 0, sumTrades: 0 }

    for (const r of Object.values(results)) {
      const key = r.matched_branch ?? "未匹配"
      if (!stats[key]) stats[key] = { count: 0, sumReturn: 0, sumTrades: 0 }
      stats[key].count++
      stats[key].sumReturn += r.total_return_pct
      stats[key].sumTrades += r.total_trades
    }
    return stats
  }, [branches, results])

  return (
    <div className="rounded-lg border p-4">
      <h3 className="text-sm font-medium mb-3">
        复合策略详情: <span className="text-primary">{compositeName}</span>
      </h3>

      {/* BTC Windows */}
      <div className="mb-3 flex items-center gap-4 text-xs text-muted-foreground">
        <span>
          BTC 窗口: W1={btc_windows?.btc_trend_window_1 ?? "?"}min, W2=
          {btc_windows?.btc_trend_window_2 ?? "?"}min
        </span>
      </div>

      {/* Branch condition table */}
      <table className="w-full text-sm mb-4">
        <thead>
          <tr className="border-b text-left text-xs text-muted-foreground">
            <th className="py-1.5 pr-3">分支</th>
            <th className="py-1.5 pr-3">阈值 (≥)</th>
            <th className="py-1.5 pr-3">预设</th>
            <th className="py-1.5 pr-3 text-right">匹配数</th>
            <th className="py-1.5 pr-3 text-right">占比</th>
            <th className="py-1.5 pr-3 text-right">平均收益</th>
            <th className="py-1.5 text-right">总交易</th>
          </tr>
        </thead>
        <tbody>
          {branches.map((branch) => {
            const count = distribution.branchCounts[branch.label] || 0
            const pct = distribution.total > 0 ? (count / distribution.total) * 100 : 0
            const stat = branchStats[branch.label]
            const avgReturn = stat && stat.count > 0 ? stat.sumReturn / stat.count : 0

            return (
              <tr key={branch.label} className="border-b last:border-0">
                <td className="py-1.5 pr-3 font-medium">{branch.label}</td>
                <td className="py-1.5 pr-3 font-mono text-xs">{branch.min_momentum}</td>
                <td className="py-1.5 pr-3">{branch.preset_name}</td>
                <td className="py-1.5 pr-3 text-right">{count}</td>
                <td className="py-1.5 pr-3 text-right">{pct.toFixed(1)}%</td>
                <td
                  className={`py-1.5 pr-3 text-right ${
                    avgReturn > 0 ? "text-emerald-600" : avgReturn < 0 ? "text-red-500" : ""
                  }`}
                >
                  {(avgReturn * 100).toFixed(2)}%
                </td>
                <td className="py-1.5 text-right">{stat?.sumTrades ?? 0}</td>
              </tr>
            )
          })}
          {/* Skip row */}
          {distribution.skipCount > 0 && (
            <tr className="text-muted-foreground">
              <td className="py-1.5 pr-3">未匹配</td>
              <td className="py-1.5 pr-3 text-xs">—</td>
              <td className="py-1.5 pr-3">跳过</td>
              <td className="py-1.5 pr-3 text-right">{distribution.skipCount}</td>
              <td className="py-1.5 pr-3 text-right">
                {distribution.total > 0
                  ? ((distribution.skipCount / distribution.total) * 100).toFixed(1)
                  : 0}
                %
              </td>
              <td className="py-1.5 pr-3 text-right">0.00%</td>
              <td className="py-1.5 text-right">0</td>
            </tr>
          )}
        </tbody>
      </table>

      {/* Distribution bar */}
      <div className="flex h-3 w-full overflow-hidden rounded-full bg-muted">
        {branches.map((branch, i) => {
          const count = distribution.branchCounts[branch.label] || 0
          const pct = distribution.total > 0 ? (count / distribution.total) * 100 : 0
          if (pct === 0) return null
          const colors = [
            "bg-blue-500",
            "bg-emerald-500",
            "bg-amber-500",
            "bg-purple-500",
            "bg-pink-500",
            "bg-cyan-500",
          ]
          return (
            <div
              key={branch.label}
              className={`${colors[i % colors.length]} transition-all`}
              style={{ width: `${pct}%` }}
              title={`${branch.label}: ${count} (${pct.toFixed(1)}%)`}
            />
          )
        })}
        {distribution.skipCount > 0 && (
          <div
            className="bg-muted-foreground/20 transition-all"
            style={{
              width: `${(distribution.skipCount / distribution.total) * 100}%`,
            }}
            title={`未匹配: ${distribution.skipCount}`}
          />
        )}
      </div>
      <div className="mt-1 flex flex-wrap gap-3 text-xs text-muted-foreground">
        {branches.map((branch, i) => {
          const colors = [
            "bg-blue-500",
            "bg-emerald-500",
            "bg-amber-500",
            "bg-purple-500",
            "bg-pink-500",
            "bg-cyan-500",
          ]
          return (
            <span key={branch.label} className="flex items-center gap-1">
              <span className={`inline-block size-2 rounded-full ${colors[i % colors.length]}`} />
              {branch.label}
            </span>
          )
        })}
        {distribution.skipCount > 0 && (
          <span className="flex items-center gap-1">
            <span className="inline-block size-2 rounded-full bg-muted-foreground/20" />
            未匹配
          </span>
        )}
      </div>
    </div>
  )
}
