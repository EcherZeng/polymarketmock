import { useMemo } from "react"
import { useParams, Link } from "react-router-dom"
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import { cn } from "@/lib/utils"
import { fetchAiOptimizeTask, stopAiOptimize } from "@/api/client"
import type { AiOptimizeTaskDetail } from "@/types"

const statusLabel: Record<string, string> = {
  running: "运行中",
  completed: "已完成",
  cancelled: "已停止",
  failed: "失败",
}

const statusColor: Record<string, string> = {
  running: "bg-blue-100 text-blue-700",
  completed: "bg-emerald-100 text-emerald-700",
  cancelled: "bg-amber-100 text-amber-700",
  failed: "bg-red-100 text-red-700",
}

const metricLabels: Record<string, string> = {
  total_return_pct: "收益率 %",
  sharpe_ratio: "Sharpe",
  win_rate: "胜率",
  max_drawdown: "最大回撤 %",
  profit_factor: "盈亏比",
  total_trades: "交易次数",
  avg_slippage: "平均滑点 %",
}

function formatMetric(key: string, val: number): string {
  if (key === "total_trades") return String(val)
  return val.toFixed(4)
}

export default function AiOptimizeDetailPage() {
  const { taskId } = useParams<{ taskId: string }>()
  const queryClient = useQueryClient()

  const { data: task, isLoading, isError } = useQuery<AiOptimizeTaskDetail>({
    queryKey: ["aiOptimizeTask", taskId],
    queryFn: () => fetchAiOptimizeTask(taskId!),
    enabled: !!taskId,
    refetchInterval: (query) => {
      const status = query.state.data?.status
      return status === "running" ? 3000 : false
    },
  })

  const stopMutation = useMutation({
    mutationFn: () => stopAiOptimize(taskId!),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["aiOptimizeTask", taskId] }),
  })

  // ── Best config display ───────────────────────────────────────────────
  const bestConfigEntries = useMemo(() => {
    if (!task?.best_config) return []
    return Object.entries(task.best_config).filter(
      ([, v]) => typeof v === "number" || typeof v === "boolean",
    )
  }, [task])

  if (isLoading) {
    return <div className="py-12 text-center text-muted-foreground">加载中...</div>
  }
  if (isError || !task) {
    return (
      <div className="py-12 text-center text-muted-foreground">
        任务不存在 · <Link to="/ai-optimize" className="text-primary underline">返回列表</Link>
      </div>
    )
  }

  const progress = task.total_runs > 0 ? (task.completed_runs / task.total_runs) * 100 : 0

  return (
    <div className="flex flex-col gap-6">
      {/* ── Header ───────────────────────────────────────────────────── */}
      <div className="flex items-start justify-between">
        <div>
          <div className="flex items-center gap-3">
            <Link to="/ai-optimize" className="text-sm text-muted-foreground hover:text-foreground">
              ← AI 优化
            </Link>
            <span className="font-mono text-lg font-bold">{task.task_id}</span>
            <span
              className={cn(
                "rounded-full px-2.5 py-0.5 text-xs font-medium",
                statusColor[task.status] ?? "bg-muted text-muted-foreground",
              )}
            >
              {statusLabel[task.status] ?? task.status}
            </span>
          </div>
          <div className="mt-1 flex gap-4 text-sm text-muted-foreground">
            <span>策略: <span className="font-medium text-foreground">{task.strategy}</span></span>
            <span>·</span>
            <span>目标: <span className="font-medium text-foreground">{task.optimize_target}</span></span>
            <span>·</span>
            <span>{task.slugs.length} 数据源</span>
            <span>·</span>
            <span>轮次 {task.current_round}/{task.max_rounds}</span>
          </div>
        </div>

        {task.status === "running" && (
          <button
            onClick={() => stopMutation.mutate()}
            disabled={stopMutation.isPending}
            className="rounded-md border border-red-200 px-3 py-1.5 text-sm text-red-600 hover:bg-red-50"
          >
            停止优化
          </button>
        )}
      </div>

      {/* ── Progress ─────────────────────────────────────────────────── */}
      <div className="rounded-lg border p-4">
        <div className="flex items-center justify-between text-sm">
          <span>回测进度: {task.completed_runs} / {task.total_runs}</span>
          <span>{progress.toFixed(0)}%</span>
        </div>
        <div className="mt-2 h-2 w-full overflow-hidden rounded-full bg-muted">
          <div
            className={cn(
              "h-full rounded-full transition-all duration-300",
              task.status === "completed" ? "bg-emerald-500"
                : task.status === "failed" ? "bg-red-400"
                : "bg-blue-500",
            )}
            style={{ width: `${progress}%` }}
          />
        </div>
        {task.error && (
          <p className="mt-2 text-sm text-red-500">错误: {task.error}</p>
        )}
      </div>

      {/* ── Best result ──────────────────────────────────────────────── */}
      {task.best_config && Object.keys(task.best_config).length > 0 && (
        <div className="rounded-lg border border-emerald-200 bg-emerald-50/50 p-4">
          <h3 className="text-sm font-semibold text-emerald-800">
            当前最优: {task.optimize_target} = {task.best_metric?.toFixed(4) ?? "N/A"}
          </h3>
          {task.best_session_id && (
            <Link
              to={`/results/${task.best_session_id}`}
              className="text-xs text-emerald-700 underline"
            >
              查看详细结果 →
            </Link>
          )}
          <div className="mt-3 grid grid-cols-4 gap-2">
            {bestConfigEntries.map(([key, val]) => (
              <div key={key} className="text-xs">
                <span className="text-muted-foreground">{key}:</span>{" "}
                <span className="font-mono font-medium">
                  {typeof val === "boolean" ? (val ? "true" : "false") : Number(val).toFixed(4)}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* ── Rounds ───────────────────────────────────────────────────── */}
      <div>
        <h2 className="mb-3 text-lg font-semibold">轮次详情</h2>
        {task.rounds.length === 0 ? (
          <p className="py-4 text-center text-sm text-muted-foreground">
            {task.status === "running" ? "等待第一轮完成..." : "无轮次数据"}
          </p>
        ) : (
          <div className="flex flex-col gap-4">
            {task.rounds.map((round) => (
              <div key={round.round} className="rounded-lg border">
                {/* Round header */}
                <div className="flex items-center justify-between border-b px-4 py-3">
                  <div className="flex items-center gap-3">
                    <span className="text-sm font-semibold">Round {round.round}</span>
                    <span className="text-xs text-muted-foreground">
                      {round.runs_completed} 次回测 · {(round.duration_ms / 1000).toFixed(1)}s
                    </span>
                  </div>
                  <span className="text-sm font-medium">
                    最优: <span className="text-emerald-600">{round.best_metric_value.toFixed(4)}</span>
                  </span>
                </div>

                {/* AI reasoning */}
                {round.ai_reasoning && (
                  <div className="border-b bg-muted/30 px-4 py-2">
                    <p className="text-xs text-muted-foreground">
                      <span className="font-medium">AI 推理:</span> {round.ai_reasoning}
                    </p>
                  </div>
                )}

                {/* Config results table */}
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b bg-muted/20">
                        <th className="px-4 py-2 text-left font-medium">#</th>
                        <th className="px-4 py-2 text-left font-medium">参数变化</th>
                        <th className="px-4 py-2 text-right font-medium">收益率</th>
                        <th className="px-4 py-2 text-right font-medium">Sharpe</th>
                        <th className="px-4 py-2 text-right font-medium">胜率</th>
                        <th className="px-4 py-2 text-right font-medium">回撤</th>
                        <th className="px-4 py-2 text-right font-medium">交易数</th>
                      </tr>
                    </thead>
                    <tbody>
                      {round.configs_results.map((cr) => {
                        const m = cr.avg_metrics
                        return (
                          <tr key={cr.config_index} className="border-b last:border-0 hover:bg-muted/10">
                            <td className="px-4 py-2 font-mono text-xs">{cr.config_index + 1}</td>
                            <td className="px-4 py-2 max-w-xs">
                              <div className="flex flex-wrap gap-1">
                                {Object.entries(cr.config).slice(0, 6).map(([k, v]) => (
                                  <span key={k} className="rounded bg-muted px-1.5 py-0.5 text-xs">
                                    {k}={typeof v === "number" ? v.toFixed(3) : String(v)}
                                  </span>
                                ))}
                                {Object.keys(cr.config).length > 6 && (
                                  <span className="text-xs text-muted-foreground">
                                    +{Object.keys(cr.config).length - 6}
                                  </span>
                                )}
                              </div>
                            </td>
                            <td className={cn(
                              "px-4 py-2 text-right font-mono",
                              (m.total_return_pct ?? 0) >= 0 ? "text-emerald-600" : "text-red-500",
                            )}>
                              {(m.total_return_pct ?? 0).toFixed(2)}%
                            </td>
                            <td className="px-4 py-2 text-right font-mono">{(m.sharpe_ratio ?? 0).toFixed(3)}</td>
                            <td className="px-4 py-2 text-right font-mono">{((m.win_rate ?? 0) * 100).toFixed(1)}%</td>
                            <td className="px-4 py-2 text-right font-mono">{(m.max_drawdown ?? 0).toFixed(2)}%</td>
                            <td className="px-4 py-2 text-right font-mono">{m.total_trades ?? 0}</td>
                          </tr>
                        )
                      })}
                    </tbody>
                  </table>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* ── Data sources ─────────────────────────────────────────────── */}
      <div>
        <h2 className="mb-2 text-sm font-medium text-muted-foreground">数据源</h2>
        <div className="flex flex-wrap gap-2">
          {task.slugs.map((slug) => (
            <span key={slug} className="rounded bg-muted px-2 py-1 text-xs font-mono">
              {slug}
            </span>
          ))}
        </div>
      </div>

      {/* ── AI communication log ─────────────────────────────────────── */}
      {task.ai_messages.length > 0 && (
        <div>
          <h2 className="mb-2 text-sm font-medium text-muted-foreground">AI 通信日志</h2>
          <div className="rounded-lg border divide-y max-h-48 overflow-y-auto">
            {task.ai_messages.map((msg, i) => (
              <div key={i} className="flex items-center gap-3 px-4 py-2 text-xs">
                <span className="font-mono text-muted-foreground">R{msg.round}</span>
                <span className={cn(
                  "rounded px-1.5 py-0.5 font-medium",
                  msg.role === "user" ? "bg-blue-100 text-blue-700" : "bg-green-100 text-green-700",
                )}>
                  {msg.role === "user" ? "→ LLM" : "← LLM"}
                </span>
                <span className="text-muted-foreground">{msg.content_length.toLocaleString()} chars</span>
                <span className="ml-auto text-muted-foreground">
                  {msg.timestamp.replace("T", " ").slice(11, 19)}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
