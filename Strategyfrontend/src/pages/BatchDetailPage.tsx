import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import { useParams, Link } from "react-router-dom"
import { useMemo, useState } from "react"
import { cn } from "@/lib/utils"
import { fetchBatchTask, cancelBatch } from "@/api/client"
import type { BatchTaskDetail, BatchResultSummary, SlugWorkflow } from "@/types"

const statusLabel: Record<string, string> = {
  running: "运行中",
  completed: "已完成",
  cancelled: "已取消",
  failed: "失败",
  pending: "等待中",
  skipped: "已跳过",
}

const statusColor: Record<string, string> = {
  running: "bg-blue-100 text-blue-700",
  completed: "bg-emerald-100 text-emerald-700",
  cancelled: "bg-amber-100 text-amber-700",
  failed: "bg-red-100 text-red-700",
  pending: "bg-muted text-muted-foreground",
  skipped: "bg-amber-100 text-amber-700",
}

const stepLabel: Record<string, string> = {
  data_load: "数据加载",
  strategy_init: "策略初始化",
  tick_loop: "回测执行",
  evaluate: "指标计算",
  done: "完成",
  error: "错误",
  cancelled: "已取消",
}

const stepStatusIcon: Record<string, string> = {
  ok: "✓",
  fail: "✗",
  skip: "—",
}

export default function BatchDetailPage() {
  const { batchId } = useParams<{ batchId: string }>()
  const queryClient = useQueryClient()
  const [expandedSlug, setExpandedSlug] = useState<string | null>(null)

  const { data: task, isLoading } = useQuery<BatchTaskDetail>({
    queryKey: ["batchTask", batchId],
    queryFn: () => fetchBatchTask(batchId!),
    enabled: !!batchId,
    refetchInterval: (query) => {
      const d = query.state.data
      return d && d.status === "running" ? 2000 : false
    },
  })

  const cancelMutation = useMutation({
    mutationFn: () => cancelBatch(batchId!),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["batchTask", batchId] })
      queryClient.invalidateQueries({ queryKey: ["batchTasks"] })
    },
  })

  // ── Aggregate stats from results ──────────────────────────────────────────

  const results = useMemo<[string, BatchResultSummary][]>(() => {
    if (!task?.results) return []
    return Object.entries(task.results)
  }, [task])

  const workflows = useMemo<[string, SlugWorkflow][]>(() => {
    if (!task?.workflows) return []
    return Object.entries(task.workflows)
  }, [task])

  const stats = useMemo(() => {
    if (results.length === 0) return null
    const returns = results.map(([, r]) => r.total_return_pct)
    const winCount = returns.filter((r) => r > 0).length
    return {
      count: results.length,
      failCount: workflows.filter(([, w]) => w.status === "failed").length,
      avgReturn: returns.reduce((a, b) => a + b, 0) / returns.length,
      winRate: (winCount / results.length) * 100,
      bestReturn: Math.max(...returns),
      worstReturn: Math.min(...returns),
      avgSharpe:
        results.reduce((a, [, r]) => a + r.sharpe_ratio, 0) / results.length,
      avgDrawdown:
        results.reduce((a, [, r]) => a + r.max_drawdown, 0) / results.length,
      totalTrades: results.reduce((a, [, r]) => a + r.total_trades, 0),
    }
  }, [results, workflows])

  if (isLoading || !task) {
    return <div className="py-12 text-center text-muted-foreground">加载中...</div>
  }

  const progress = task.total > 0 ? (task.completed / task.total) * 100 : 0
  const failedWorkflows = workflows.filter(([, w]) => w.status === "failed")

  return (
    <div className="flex flex-col gap-6">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <div className="flex items-center gap-3">
            <h1 className="text-2xl font-bold tracking-tight">批量回测详情</h1>
            <span
              className={cn(
                "rounded-full px-2.5 py-0.5 text-xs font-medium",
                statusColor[task.status] ?? "bg-muted text-muted-foreground",
              )}
            >
              {statusLabel[task.status] ?? task.status}
            </span>
          </div>
          <div className="mt-1 flex flex-wrap gap-3 text-sm text-muted-foreground">
            <span>ID: <span className="font-mono">{task.batch_id}</span></span>
            <span>·</span>
            <span>策略: <span className="font-medium text-foreground">{task.strategy}</span></span>
            <span>·</span>
            <span>{task.created_at.replace("T", " ").slice(0, 19)}</span>
          </div>
        </div>
        <div className="flex gap-2">
          {task.status === "running" && (
            <button
              onClick={() => cancelMutation.mutate()}
              disabled={cancelMutation.isPending}
              className="rounded-md border px-3 py-1.5 text-sm font-medium text-red-600 transition-colors hover:bg-red-50"
            >
              取消批量
            </button>
          )}
          <Link
            to="/batch"
            className="rounded-md border px-3 py-1.5 text-sm font-medium transition-colors hover:bg-muted"
          >
            返回列表
          </Link>
        </div>
      </div>

      {/* Progress */}
      <div className="rounded-lg border p-4">
        <div className="mb-2 flex items-center justify-between text-sm">
          <span className="text-muted-foreground">进度</span>
          <span className="font-mono font-medium">
            {task.completed} / {task.total}
            {failedWorkflows.length > 0 && (
              <span className="ml-2 text-red-500">({failedWorkflows.length} 失败)</span>
            )}
          </span>
        </div>
        <div className="h-2 w-full overflow-hidden rounded-full bg-muted">
          <div
            className={cn(
              "h-full rounded-full transition-all duration-300",
              task.status === "completed"
                ? "bg-emerald-500"
                : task.status === "cancelled"
                  ? "bg-red-400"
                  : "bg-blue-500",
            )}
            style={{ width: `${progress}%` }}
          />
        </div>
      </div>

      {/* Aggregate stats */}
      {stats && (
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4 lg:grid-cols-8">
          <StatCard label="成功" value={`${stats.count}`} />
          <StatCard label="失败" value={`${stats.failCount}`} color={stats.failCount > 0 ? "red" : undefined} />
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
          <StatCard label="总交易数" value={`${stats.totalTrades}`} />
        </div>
      )}

      {/* Workflow overview — all slugs with step progress */}
      <div className="rounded-lg border">
        <div className="border-b bg-muted/50 px-4 py-2">
          <h2 className="text-sm font-medium">工作流日志</h2>
        </div>
        <div className="max-h-[600px] overflow-y-auto">
          {workflows.map(([slug, wf]) => {
            const result = task.results[slug]
            const isExpanded = expandedSlug === slug
            return (
              <div key={slug} className="border-b last:border-b-0">
                {/* Slug row */}
                <button
                  onClick={() => setExpandedSlug(isExpanded ? null : slug)}
                  className="flex w-full items-center gap-3 px-4 py-2.5 text-left transition-colors hover:bg-muted/30"
                >
                  <span className="text-xs text-muted-foreground">{isExpanded ? "▼" : "▶"}</span>
                  <span className="min-w-0 flex-1 truncate font-mono text-xs">{slug}</span>
                  {/* Step mini-indicators */}
                  <div className="flex items-center gap-1">
                    {wf.steps.map((s, i) => (
                      <span
                        key={i}
                        title={`${stepLabel[s.step] ?? s.step}: ${s.message}`}
                        className={cn(
                          "inline-block h-2 w-2 rounded-full",
                          s.status === "ok" && "bg-emerald-500",
                          s.status === "fail" && "bg-red-500",
                          s.status === "skip" && "bg-amber-400",
                        )}
                      />
                    ))}
                    {wf.status === "pending" && (
                      <span className="h-2 w-2 rounded-full bg-muted-foreground/30" />
                    )}
                    {wf.status === "running" && (
                      <span className="h-2 w-2 animate-pulse rounded-full bg-blue-500" />
                    )}
                  </div>
                  <span
                    className={cn(
                      "rounded-full px-2 py-0.5 text-[10px] font-medium",
                      statusColor[wf.status] ?? "bg-muted text-muted-foreground",
                    )}
                  >
                    {statusLabel[wf.status] ?? wf.status}
                  </span>
                  {result && (
                    <span
                      className={cn(
                        "font-mono text-xs",
                        result.total_return_pct >= 0 ? "text-emerald-600" : "text-red-500",
                      )}
                    >
                      {result.total_return_pct >= 0 ? "+" : ""}
                      {result.total_return_pct.toFixed(2)}%
                    </span>
                  )}
                  {result && (
                    <Link
                      to={`/results/${result.session_id}`}
                      onClick={(e) => e.stopPropagation()}
                      className="text-xs text-primary hover:underline"
                    >
                      详情
                    </Link>
                  )}
                </button>

                {/* Expanded: step logs */}
                {isExpanded && wf.steps.length > 0 && (
                  <div className="border-t bg-muted/20 px-4 py-3">
                    <div className="flex flex-col gap-2">
                      {wf.steps.map((step, i) => (
                        <div key={i} className="flex items-start gap-2 text-xs">
                          <span
                            className={cn(
                              "mt-0.5 shrink-0 font-bold",
                              step.status === "ok" && "text-emerald-600",
                              step.status === "fail" && "text-red-500",
                              step.status === "skip" && "text-amber-500",
                            )}
                          >
                            {stepStatusIcon[step.status] ?? "?"}
                          </span>
                          <div className="min-w-0 flex-1">
                            <div className="flex items-center gap-2">
                              <span className="font-medium">
                                {stepLabel[step.step] ?? step.step}
                              </span>
                              {step.duration_ms > 0 && (
                                <span className="text-muted-foreground">
                                  {step.duration_ms >= 1000
                                    ? `${(step.duration_ms / 1000).toFixed(1)}s`
                                    : `${step.duration_ms.toFixed(0)}ms`}
                                </span>
                              )}
                              <span className="text-muted-foreground">
                                {step.timestamp.slice(11, 19)}
                              </span>
                            </div>
                            {step.message && (
                              <div className="mt-0.5 text-muted-foreground">{step.message}</div>
                            )}
                            {step.detail && (
                              <pre className="mt-1 max-h-32 overflow-auto rounded bg-muted p-2 font-mono text-[10px] text-red-600">
                                {step.detail}
                              </pre>
                            )}
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Expanded but no steps yet */}
                {isExpanded && wf.steps.length === 0 && (
                  <div className="border-t bg-muted/20 px-4 py-3 text-xs text-muted-foreground">
                    暂无日志 — 任务可能还在排队中
                  </div>
                )}
              </div>
            )
          })}
        </div>
      </div>

      {/* Results table — successful only */}
      {results.length > 0 && (
        <div className="rounded-lg border">
          <div className="border-b bg-muted/50 px-4 py-2">
            <h2 className="text-sm font-medium">成功结果 ({results.length})</h2>
          </div>
          <div className="overflow-auto">
            <table className="w-full text-sm">
              <thead className="bg-muted/30">
                <tr className="border-b text-left text-xs text-muted-foreground">
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
                {results.map(([slug, r]) => (
                  <tr
                    key={slug}
                    className="border-b transition-colors hover:bg-muted/30"
                  >
                    <td className="px-3 py-2 font-mono text-xs">{slug}</td>
                    <td
                      className={cn(
                        "px-3 py-2 text-right font-mono",
                        r.total_return_pct >= 0 ? "text-emerald-600" : "text-red-500",
                      )}
                    >
                      {r.total_return_pct >= 0 ? "+" : ""}
                      {r.total_return_pct.toFixed(2)}%
                    </td>
                    <td className="px-3 py-2 text-right font-mono">
                      {r.sharpe_ratio.toFixed(4)}
                    </td>
                    <td className="px-3 py-2 text-right font-mono">
                      {r.win_rate.toFixed(1)}%
                    </td>
                    <td className="px-3 py-2 text-right font-mono text-red-500">
                      {r.max_drawdown.toFixed(2)}%
                    </td>
                    <td className="px-3 py-2 text-right font-mono">
                      {r.profit_factor === Infinity
                        ? "∞"
                        : r.profit_factor.toFixed(2)}
                    </td>
                    <td className="px-3 py-2 text-right font-mono">
                      {r.total_trades}
                    </td>
                    <td className="px-3 py-2 text-right font-mono">
                      {r.avg_slippage.toFixed(4)}%
                    </td>
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
      )}
    </div>
  )
}

function StatCard({
  label,
  value,
  color,
}: {
  label: string
  value: string
  color?: "green" | "red"
}) {
  return (
    <div className="rounded-lg border p-3">
      <div className="text-xs text-muted-foreground">{label}</div>
      <div
        className={cn(
          "mt-1 text-sm font-semibold",
          color === "green" && "text-emerald-600",
          color === "red" && "text-red-500",
        )}
      >
        {value}
      </div>
    </div>
  )
}
