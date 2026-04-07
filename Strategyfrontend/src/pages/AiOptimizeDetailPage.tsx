import { useMemo, useState } from "react"
import { useParams, Link } from "react-router-dom"
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import { cn } from "@/lib/utils"
import { fetchAiOptimizeTask, stopAiOptimize, fetchPresets, savePreset } from "@/api/client"
import type { AiOptimizeTaskDetail, PresetsResponse } from "@/types"
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"

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

const PCT_METRICS = new Set(["total_return_pct", "win_rate", "max_drawdown", "hold_to_settlement_ratio", "annualized_return"])

function fmtMetric(target: string, value: number): string {
  if (PCT_METRICS.has(target)) return `${(value * 100).toFixed(2)}%`
  return value.toFixed(4)
}

export default function AiOptimizeDetailPage() {
  const { taskId } = useParams<{ taskId: string }>()
  const queryClient = useQueryClient()

  const [createDialogOpen, setCreateDialogOpen] = useState(false)
  const [presetName, setPresetName] = useState("")
  const [expandedRoundSlugs, setExpandedRoundSlugs] = useState<Record<string, boolean>>({})
  const [expandedAiMsgIdx, setExpandedAiMsgIdx] = useState<number | null>(null)

  const { data: task, isLoading, isError } = useQuery<AiOptimizeTaskDetail>({
    queryKey: ["aiOptimizeTask", taskId],
    queryFn: () => fetchAiOptimizeTask(taskId!),
    enabled: !!taskId,
    refetchInterval: (query) => {
      const status = query.state.data?.status
      return status === "running" ? 3000 : false
    },
  })

  const { data: presets } = useQuery<PresetsResponse>({
    queryKey: ["presets"],
    queryFn: fetchPresets,
  })

  const stopMutation = useMutation({
    mutationFn: () => stopAiOptimize(taskId!),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["aiOptimizeTask", taskId] }),
  })

  const createPresetMutation = useMutation({
    mutationFn: (name: string) =>
      savePreset(name, { description: `AI 优化最优参数 (${task?.task_id})`, params: task?.best_config ?? {} }),
    onSuccess: () => {
      setCreateDialogOpen(false)
      setPresetName("")
      queryClient.invalidateQueries({ queryKey: ["presets"] })
    },
  })

  // ── Param schema lookup ─────────────────────────────────────────────
  const paramSchema = presets?.param_schema ?? {}

  const getParamLabel = (key: string): string => {
    const schema = paramSchema[key]
    if (schema?.label?.zh) return schema.label.zh
    return key
  }

  // ── Best config display ───────────────────────────────────────────────
  const { bestConfigEntries, bestConfigJson } = useMemo(() => {
    if (!task?.best_config) return { bestConfigEntries: [] as [string, unknown][], bestConfigJson: "" }
    const entries = Object.entries(task.best_config).filter(
      ([, v]) => typeof v === "number" || typeof v === "boolean",
    )
    const obj = Object.fromEntries(entries)
    return {
      bestConfigEntries: entries,
      bestConfigJson: JSON.stringify(obj, null, 2),
    }
  }, [task])

  const [showJson, setShowJson] = useState(false)

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

      {/* ── Errors ───────────────────────────────────────────────────── */}
      <ErrorsSection errors={task.errors} persistErrors={task.persist_errors} />

      {/* ── Best result ──────────────────────────────────────────────── */}
      {task.best_config && Object.keys(task.best_config).length > 0 && (
        <div className="rounded-lg border border-emerald-200 bg-emerald-50/50 p-4">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-semibold text-emerald-800">
              当前最优: {task.optimize_target} = {task.best_metric != null ? fmtMetric(task.optimize_target, task.best_metric) : "N/A"}
            </h3>
            <div className="flex items-center gap-2">
              {task.best_session_id && (
                <Link
                  to={`/results/${task.best_session_id}`}
                  className="text-xs text-emerald-700 underline"
                >
                  查看详细结果 →
                </Link>
              )}
              <button
                onClick={() => setShowJson((v) => !v)}
                className="rounded border border-emerald-300 px-2 py-0.5 text-xs text-emerald-700 hover:bg-emerald-100"
              >
                {showJson ? "参数视图" : "JSON 视图"}
              </button>
              <button
                onClick={() => {
                  setPresetName(`ai_opt_${task.task_id}`)
                  setCreateDialogOpen(true)
                }}
                className="rounded bg-emerald-600 px-2.5 py-0.5 text-xs font-medium text-white hover:bg-emerald-700"
              >
                一键创建策略
              </button>
            </div>
          </div>

          {showJson ? (
            <pre className="mt-3 max-h-64 overflow-auto rounded bg-white/80 p-3 text-xs font-mono text-emerald-900 border border-emerald-100">
              {bestConfigJson}
            </pre>
          ) : (
            <div className="mt-3 grid grid-cols-3 gap-2">
              {bestConfigEntries.map(([key, val]) => (
                <div key={key} className="rounded bg-white/60 px-2 py-1.5 text-xs border border-emerald-100">
                  <span className="text-emerald-700">{getParamLabel(key)}</span>
                  <div className="font-mono font-medium mt-0.5">
                    {typeof val === "boolean" ? (val ? "是" : "否") : Number(val).toFixed(4)}
                  </div>
                  <div className="text-[10px] text-muted-foreground font-mono">{key}</div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* ── Create preset dialog ─────────────────────────────────────── */}
      <Dialog open={createDialogOpen} onOpenChange={setCreateDialogOpen}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>创建策略预设</DialogTitle>
          </DialogHeader>
          <div className="flex flex-col gap-3 py-4">
            <label className="text-sm text-muted-foreground">策略名称</label>
            <Input
              value={presetName}
              onChange={(e) => setPresetName(e.target.value)}
              placeholder="输入自定义名称"
            />
            <p className="text-xs text-muted-foreground">
              将使用 AI 优化得到的最优参数创建新的策略预设
            </p>
          </div>
          <DialogFooter>
            <button
              onClick={() => setCreateDialogOpen(false)}
              className="rounded border px-3 py-1.5 text-sm hover:bg-muted"
            >
              取消
            </button>
            <button
              disabled={!presetName.trim() || createPresetMutation.isPending}
              onClick={() => createPresetMutation.mutate(presetName.trim())}
              className="rounded bg-primary px-3 py-1.5 text-sm text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
            >
              {createPresetMutation.isPending ? "创建中..." : "创建"}
            </button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

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
                    <span className="text-sm font-semibold">
                      {round.round === 0 ? "基准 (Baseline)" : `Round ${round.round}`}
                    </span>
                    {round.round === 0 && (
                      <span className="rounded bg-blue-100 px-1.5 py-0.5 text-[10px] font-medium text-blue-700">
                        原始参数
                      </span>
                    )}
                    <span className="text-xs text-muted-foreground">
                      {round.runs_completed} 次回测 · {(round.duration_ms / 1000).toFixed(1)}s
                    </span>
                  </div>
                  <span className="text-sm font-medium">
                    最优: <span className="text-emerald-600">{fmtMetric(task.optimize_target, round.best_metric_value)}</span>
                  </span>
                </div>

                {/* AI reasoning */}
                {round.ai_reasoning && round.round > 0 && (
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
                        <th className="px-4 py-2 text-left font-medium">{round.round === 0 ? "#" : "组"}</th>
                        <th className="px-4 py-2 text-left font-medium">{round.round === 0 ? "基准参数" : "参数变化"}</th>
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
                        const slugKey = `${round.round}-${cr.config_index}`
                        const isSlugExpanded = expandedRoundSlugs[slugKey] ?? false
                        const slugMetrics = cr.slug_metrics ?? []
                        return (
                          <>
                            <tr
                              key={cr.config_index}
                              className={cn(
                                "border-b last:border-0 hover:bg-muted/10 cursor-pointer",
                                isSlugExpanded && "bg-muted/5",
                              )}
                              onClick={() =>
                                setExpandedRoundSlugs((prev) => ({
                                  ...prev,
                                  [slugKey]: !prev[slugKey],
                                }))
                              }
                            >
                              <td className="px-4 py-2 font-mono text-xs">
                                <span className="mr-1 text-muted-foreground">{isSlugExpanded ? "▾" : "▸"}</span>
                                {cr.config_index + 1}
                              </td>
                              <td className="px-4 py-2 max-w-xs">
                                <div className="flex flex-wrap gap-1">
                                  {Object.entries(cr.config).slice(0, 6).map(([k, v]) => (
                                    <span key={k} className="rounded bg-muted px-1.5 py-0.5 text-xs" title={k}>
                                      {getParamLabel(k)}={typeof v === "number" ? v.toFixed(3) : String(v)}
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
                                {((m.total_return_pct ?? 0) * 100).toFixed(2)}%
                              </td>
                              <td className="px-4 py-2 text-right font-mono">{(m.sharpe_ratio ?? 0).toFixed(3)}</td>
                              <td className="px-4 py-2 text-right font-mono">{((m.win_rate ?? 0) * 100).toFixed(1)}%</td>
                              <td className="px-4 py-2 text-right font-mono">{((m.max_drawdown ?? 0) * 100).toFixed(2)}%</td>
                              <td className="px-4 py-2 text-right font-mono">{m.total_trades ?? 0}</td>
                            </tr>
                            {isSlugExpanded && slugMetrics.length > 0 && slugMetrics.map((sm) => (
                              <tr key={`${cr.config_index}-${sm.slug}`} className="border-b bg-muted/10 last:border-0">
                                <td className="px-4 py-1.5" />
                                <td className="px-4 py-1.5 text-xs">
                                  <span className="font-mono text-muted-foreground">└</span>{" "}
                                  {sm.session_id ? (
                                    <Link to={`/results/${sm.session_id}`} className="text-primary underline">
                                      {sm.slug}
                                    </Link>
                                  ) : (
                                    <span className="font-mono">{sm.slug}</span>
                                  )}
                                </td>
                                <td className={cn(
                                  "px-4 py-1.5 text-right font-mono text-xs",
                                  sm.total_return_pct >= 0 ? "text-emerald-600" : "text-red-500",
                                )}>
                                  {(sm.total_return_pct * 100).toFixed(2)}%
                                </td>
                                <td className="px-4 py-1.5 text-right font-mono text-xs">{sm.sharpe_ratio.toFixed(3)}</td>
                                <td className="px-4 py-1.5 text-right font-mono text-xs">{((sm.win_rate ?? 0) * 100).toFixed(1)}%</td>
                                <td className="px-4 py-1.5 text-right font-mono text-xs">{(sm.max_drawdown * 100).toFixed(2)}%</td>
                                <td className="px-4 py-1.5 text-right font-mono text-xs">{sm.total_trades}</td>
                              </tr>
                            ))}
                          </>
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
          <div className="rounded-lg border divide-y max-h-[600px] overflow-y-auto">
            {task.ai_messages.map((msg, i) => (
              <div key={i} className="px-4 py-2">
                <button
                  className="flex w-full items-center gap-3 text-xs text-left"
                  onClick={() => setExpandedAiMsgIdx(expandedAiMsgIdx === i ? null : i)}
                >
                  <span className="text-muted-foreground">{expandedAiMsgIdx === i ? "▾" : "▸"}</span>
                  <span className="font-mono text-muted-foreground">R{msg.round}</span>
                  <span className={cn(
                    "rounded px-1.5 py-0.5 font-medium",
                    msg.role === "user" ? "bg-blue-100 text-blue-700" : "bg-green-100 text-green-700",
                  )}>
                    {msg.role === "user" ? "→ LLM (提问)" : "← LLM (回复)"}
                  </span>
                  <span className="text-muted-foreground">{msg.content_length.toLocaleString()} chars</span>
                  <span className="ml-auto text-muted-foreground">
                    {msg.timestamp.replace("T", " ").slice(11, 19)}
                  </span>
                </button>
                {expandedAiMsgIdx === i && msg.content && (
                  <pre className="mt-2 max-h-96 overflow-auto rounded bg-muted p-3 text-xs whitespace-pre-wrap break-words font-mono">
                    {msg.content}
                  </pre>
                )}
                {expandedAiMsgIdx === i && !msg.content && (
                  <p className="mt-2 text-xs text-muted-foreground italic">内容未记录</p>
                )}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}


// ── Errors section (collapsible) ────────────────────────────────────────────

const phaseLabel: Record<string, string> = {
  llm_call: "LLM 调用",
  parse: "响应解析",
  backtest: "回测执行",
  unknown: "未知",
}

function ErrorsSection({
  errors,
  persistErrors,
}: {
  errors?: Array<{
    round: number
    phase: string
    message: string
    detail: string
    timestamp: string
    config_index?: number
    slug?: string
  }>
  persistErrors?: string[]
}) {
  const [expandedIdx, setExpandedIdx] = useState<number | null>(null)
  const hasErrors = (errors && errors.length > 0) || (persistErrors && persistErrors.length > 0)
  if (!hasErrors) return null

  return (
    <div className="rounded-lg border border-red-200">
      <div className="flex items-center gap-2 border-b border-red-100 bg-red-50/50 px-4 py-2.5">
        <span className="text-sm font-semibold text-red-700">
          错误日志 ({(errors?.length ?? 0) + (persistErrors?.length ?? 0)})
        </span>
      </div>
      <div className="max-h-80 divide-y overflow-y-auto">
        {errors?.map((err, i) => (
          <div key={i} className="px-4 py-2">
            <button
              className="flex w-full items-center gap-2 text-left text-xs"
              onClick={() => setExpandedIdx(expandedIdx === i ? null : i)}
            >
              <span className="font-mono text-red-400">✗</span>
              <span className="rounded bg-red-100 px-1.5 py-0.5 text-red-700">
                R{err.round} · {phaseLabel[err.phase] ?? err.phase}
              </span>
              {err.slug && (
                <span className="font-mono text-muted-foreground">{err.slug}</span>
              )}
              {err.config_index != null && (
                <span className="text-muted-foreground">config#{err.config_index + 1}</span>
              )}
              <span className="ml-auto text-muted-foreground">
                {err.timestamp.replace("T", " ").slice(11, 19)}
              </span>
            </button>
            <p className="mt-1 text-xs text-red-600">{err.message}</p>
            {expandedIdx === i && err.detail && (
              <pre className="mt-2 max-h-48 overflow-auto rounded bg-muted p-2 text-xs text-muted-foreground">
                {err.detail}
              </pre>
            )}
          </div>
        ))}
        {persistErrors?.map((msg, i) => (
          <div key={`p-${i}`} className="px-4 py-2">
            <div className="flex items-center gap-2 text-xs">
              <span className="font-mono text-amber-500">⚠</span>
              <span className="rounded bg-amber-100 px-1.5 py-0.5 text-amber-700">持久化失败</span>
            </div>
            <p className="mt-1 text-xs text-amber-600">{msg}</p>
          </div>
        ))}
      </div>
    </div>
  )
}
