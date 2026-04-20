import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import { useParams, Link, useNavigate } from "react-router-dom"
import { useMemo, useState } from "react"
import { cn, fmtTimeCst, fmtFullCst } from "@/lib/utils"
import { fetchBatchTask, cancelBatch, cleanupByBatch, rerunBacktest } from "@/api/client"
import { Checkbox } from "@/components/ui/checkbox"
import AddToPortfolioDialog from "@/components/AddToPortfolioDialog"
import CompositeDetailPanel from "@/components/CompositeDetailPanel"
import type { BatchTaskDetail, BatchResultSummary, SlugWorkflow, PortfolioItem } from "@/types"

const statusLabel: Record<string, string> = {
  running: "运行中",
  completed: "已完成",
  cancelled: "已取消",
  failed: "失败",
  pending: "等待中",
  skipped: "已跳过",
  interrupted: "已中断",
}

const statusColor: Record<string, string> = {
  running: "bg-blue-100 text-blue-700",
  completed: "bg-emerald-100 text-emerald-700",
  cancelled: "bg-amber-100 text-amber-700",
  failed: "bg-red-100 text-red-700",
  pending: "bg-muted text-muted-foreground",
  skipped: "bg-amber-100 text-amber-700",
  interrupted: "bg-orange-100 text-orange-700",
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
  const navigate = useNavigate()
  const [expandedSlug, setExpandedSlug] = useState<string | null>(null)
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set())
  const [returnFilter, setReturnFilter] = useState<"all" | "positive" | "negative">("all")
  const [portfolioOpen, setPortfolioOpen] = useState(false)
  const [confirmDelete, setConfirmDelete] = useState(false)
  const [currentPage, setCurrentPage] = useState(1)
  const [rerunningIds, setRerunningIds] = useState<Set<string>>(new Set())
  const [sortField, setSortField] = useState<string | null>(null)
  const [sortDir, setSortDir] = useState<"asc" | "desc">("desc")
  const pageSize = 50

  const { data: task, isLoading, isError } = useQuery<BatchTaskDetail>({
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

  const deleteBatchMutation = useMutation({
    mutationFn: () => cleanupByBatch(batchId!),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["batch-tasks"] })
      queryClient.invalidateQueries({ queryKey: ["results-stats"] })
      queryClient.invalidateQueries({ queryKey: ["results"] })
      navigate("/batch")
    },
  })

  const rerunMutation = useMutation({
    mutationFn: (sessionId: string) => {
      setRerunningIds((s) => new Set(s).add(sessionId))
      return rerunBacktest({ session_id: sessionId, matching_mode: "vwap" })
    },
    onSuccess: (result) => {
      window.open(`/results/${result.session_id}`, "_blank")
    },
    onSettled: (_data, _error, sessionId) => {
      setRerunningIds((s) => {
        const next = new Set(s)
        next.delete(sessionId)
        return next
      })
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
      avgReturn: returns.reduce((a, b) => a + b, 0) / returns.length * 100,
      winRate: (winCount / results.length) * 100,
      bestReturn: Math.max(...returns) * 100,
      worstReturn: Math.min(...returns) * 100,
      avgSharpe:
        results.reduce((a, [, r]) => a + r.sharpe_ratio, 0) / results.length,
      avgDrawdown:
        results.reduce((a, [, r]) => a + r.max_drawdown, 0) / results.length * 100,
      totalTrades: results.reduce((a, [, r]) => a + r.total_trades, 0),
    }
  }, [results, workflows])

  const filteredResults = useMemo(() => {
    let list = results
    if (returnFilter !== "all") {
      list = list.filter(([, r]) =>
        returnFilter === "positive" ? r.total_return_pct > 0 : r.total_return_pct < 0,
      )
    }
    if (sortField) {
      list = [...list].sort((a, b) => {
        const ra = a[1] as unknown as Record<string, unknown>
        const rb = b[1] as unknown as Record<string, unknown>
        const va = ra[sortField]
        const vb = rb[sortField]
        // String sort for matched_branch/matched_preset
        if (typeof va === "string" || typeof vb === "string") {
          const sa = (va as string) ?? ""
          const sb = (vb as string) ?? ""
          return sortDir === "asc" ? sa.localeCompare(sb) : sb.localeCompare(sa)
        }
        const na = (va as number) ?? 0
        const nb = (vb as number) ?? 0
        return sortDir === "asc" ? na - nb : nb - na
      })
    }
    return list
  }, [results, returnFilter, sortField, sortDir])

  const filteredStats = useMemo(() => {
    if (returnFilter === "all" || filteredResults.length === 0) return null
    const returns = filteredResults.map(([, r]) => r.total_return_pct)
    const sorted = [...returns].sort((a, b) => a - b)
    const mid = Math.floor(sorted.length / 2)
    const median = sorted.length % 2 !== 0 ? sorted[mid] : (sorted[mid - 1] + sorted[mid]) / 2
    return {
      count: filteredResults.length,
      sumReturn: returns.reduce((a, b) => a + b, 0) * 100,
      avgReturn: returns.reduce((a, b) => a + b, 0) / returns.length * 100,
      medianReturn: median * 100,
      avgSharpe: filteredResults.reduce((a, [, r]) => a + r.sharpe_ratio, 0) / filteredResults.length,
      totalTrades: filteredResults.reduce((a, [, r]) => a + r.total_trades, 0),
    }
  }, [filteredResults, returnFilter])

  const totalPages = Math.max(1, Math.ceil(filteredResults.length / pageSize))
  const safePage = Math.min(currentPage, totalPages)
  const pagedResults = useMemo(() => {
    const start = (safePage - 1) * pageSize
    return filteredResults.slice(start, start + pageSize)
  }, [filteredResults, safePage, pageSize])

  const toggleSelect = (sessionId: string) => {
    setSelectedIds((prev) => {
      const next = new Set(prev)
      if (next.has(sessionId)) next.delete(sessionId)
      else next.add(sessionId)
      return next
    })
  }

  const toggleSelectAll = () => {
    const allFilteredIds = filteredResults.map(([, r]) => r.session_id)
    const allSelected = allFilteredIds.length > 0 && allFilteredIds.every((id) => selectedIds.has(id))
    if (allSelected) {
      setSelectedIds((prev) => {
        const next = new Set(prev)
        for (const id of allFilteredIds) next.delete(id)
        return next
      })
    } else {
      setSelectedIds((prev) => {
        const next = new Set(prev)
        for (const id of allFilteredIds) next.add(id)
        return next
      })
    }
  }

  const toggleSelectPage = () => {
    const visibleIds = pagedResults.map(([, r]) => r.session_id)
    const allSelected = visibleIds.length > 0 && visibleIds.every((id) => selectedIds.has(id))
    if (allSelected) {
      setSelectedIds((prev) => {
        const next = new Set(prev)
        for (const id of visibleIds) next.delete(id)
        return next
      })
    } else {
      setSelectedIds((prev) => {
        const next = new Set(prev)
        for (const id of visibleIds) next.add(id)
        return next
      })
    }
  }

  const toggleSort = (field: string) => {
    if (sortField === field) {
      setSortDir((d) => (d === "asc" ? "desc" : "asc"))
    } else {
      setSortField(field)
      setSortDir("desc")
    }
    setCurrentPage(1)
  }

  const sortIndicator = (field: string) =>
    sortField === field ? (sortDir === "asc" ? " ↑" : " ↓") : ""

  const selectedItems = useMemo<PortfolioItem[]>(() => {
    return results
      .filter(([, r]) => selectedIds.has(r.session_id))
      .map(([slug, r]) => ({
        session_id: r.session_id,
        strategy: task?.strategy ?? "",
        slug,
        total_return_pct: r.total_return_pct,
        sharpe_ratio: r.sharpe_ratio,
        win_rate: r.win_rate,
        max_drawdown: r.max_drawdown,
        profit_factor: r.profit_factor,
        total_trades: r.total_trades,
        avg_slippage: r.avg_slippage,
        initial_balance: r.initial_balance,
        final_equity: r.final_equity,
        btc_momentum: r.btc_momentum ?? 0,
        config: task?.config ?? {},
      }))
  }, [results, selectedIds, task])

  if (isLoading) {
    return <div className="py-12 text-center text-muted-foreground">加载中...</div>
  }

  if (isError || !task) {
    return (
      <div className="py-12 text-center text-muted-foreground">
        批量任务不存在或已被清除 ·{" "}
        <Link to="/batch" className="text-primary underline">返回列表</Link>
      </div>
    )
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
            <span>{fmtFullCst(task.created_at)}</span>
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
          {task.status !== "running" && !confirmDelete && (
            <button
              onClick={() => setConfirmDelete(true)}
              className="rounded-md border border-destructive px-3 py-1.5 text-sm font-medium text-destructive transition-colors hover:bg-destructive/10"
            >
              删除此批次
            </button>
          )}
          {confirmDelete && (
            <>
              <button
                onClick={() => deleteBatchMutation.mutate()}
                disabled={deleteBatchMutation.isPending}
                className="rounded-md bg-destructive px-3 py-1.5 text-sm font-medium text-white disabled:opacity-50"
              >
                {deleteBatchMutation.isPending ? "删除中..." : "确认删除"}
              </button>
              <button
                onClick={() => setConfirmDelete(false)}
                className="rounded-md border px-3 py-1.5 text-sm font-medium transition-colors hover:bg-muted"
              >
                取消
              </button>
            </>
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

      {/* Composite strategy detail panel */}
      {task.composite_detail && task.composite_name && (
        <CompositeDetailPanel
          compositeDetail={task.composite_detail}
          compositeName={task.composite_name}
          results={task.results}
        />
      )}

      {/* Persist errors */}
      {task.persist_errors && task.persist_errors.length > 0 && (
        <div className="rounded-lg border border-amber-200 bg-amber-50/50 p-4">
          <h3 className="text-sm font-semibold text-amber-800">
            持久化警告 ({task.persist_errors.length})
          </h3>
          <p className="mt-1 text-xs text-amber-600">以下结果可能未成功保存到磁盘</p>
          <div className="mt-2 max-h-32 divide-y divide-amber-100 overflow-y-auto">
            {task.persist_errors.map((msg, i) => (
              <p key={i} className="py-1 text-xs text-amber-700">{msg}</p>
            ))}
          </div>
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
                      {(result.total_return_pct * 100).toFixed(2)}%
                    </span>
                  )}
                  {result && (
                    <Link
                      to={`/results/${result.session_id}`}
                      target="_blank"
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
                                {fmtTimeCst(step.timestamp)}
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
          <div className="flex items-center justify-between border-b bg-muted/50 px-4 py-2">
            <h2 className="text-sm font-medium">成功结果 ({results.length})</h2>
            <div className="flex items-center gap-2">
              {/* Return filter toggles */}
              {(["all", "positive", "negative"] as const).map((f) => (
                <button
                  key={f}
                  onClick={() => { setReturnFilter(f); setSelectedIds(new Set()); setCurrentPage(1) }}
                  className={cn(
                    "rounded-md px-2.5 py-1 text-xs font-medium transition-colors",
                    returnFilter === f
                      ? "bg-foreground text-background"
                      : "bg-muted text-muted-foreground hover:bg-muted/80",
                  )}
                >
                  {f === "all" ? "全部" : f === "positive" ? "收益增加" : "收益减少"}
                </button>
              ))}
              <span className="text-xs text-muted-foreground">
                {filteredResults.length} / {results.length} 条
              </span>
              {/* Select all filtered */}
              {filteredResults.length > pageSize && (
                <button
                  onClick={toggleSelectAll}
                  className="rounded-md border px-2.5 py-1 text-xs font-medium text-primary transition-colors hover:bg-primary/10"
                >
                  {filteredResults.every(([, r]) => selectedIds.has(r.session_id))
                    ? `取消全选 (${filteredResults.length})`
                    : `全选 ${filteredResults.length} 条`}
                </button>
              )}
              {/* Selection info + Add to portfolio */}
              {selectedIds.size > 0 && (
                <>
                  <span className="text-xs text-muted-foreground">
                    已选 {selectedIds.size} 条
                  </span>
                  <button
                    onClick={() => setPortfolioOpen(true)}
                    className="rounded-md bg-primary px-3 py-1 text-xs font-medium text-primary-foreground transition-colors hover:bg-primary/90"
                  >
                    加入组合
                  </button>
                </>
              )}
            </div>
          </div>
          {filteredStats && (
            <div className="flex flex-wrap items-center gap-4 border-b bg-muted/30 px-4 py-2 text-xs">
              <span className="font-medium text-muted-foreground">
                {returnFilter === "positive" ? "收益增加" : "收益减少"}小计
              </span>
              <span>场次: <b>{filteredStats.count}</b></span>
              <span>
                收益率总和:{" "}
                <b className={filteredStats.sumReturn >= 0 ? "text-emerald-600" : "text-red-500"}>
                  {filteredStats.sumReturn >= 0 ? "+" : ""}{filteredStats.sumReturn.toFixed(2)}%
                </b>
              </span>
              <span>
                平均收益率:{" "}
                <b className={filteredStats.avgReturn >= 0 ? "text-emerald-600" : "text-red-500"}>
                  {filteredStats.avgReturn >= 0 ? "+" : ""}{filteredStats.avgReturn.toFixed(2)}%
                </b>
              </span>
              <span>
                中位收益率:{" "}
                <b className={filteredStats.medianReturn >= 0 ? "text-emerald-600" : "text-red-500"}>
                  {filteredStats.medianReturn >= 0 ? "+" : ""}{filteredStats.medianReturn.toFixed(2)}%
                </b>
              </span>
              <span>平均 Sharpe: <b>{filteredStats.avgSharpe.toFixed(4)}</b></span>
              <span>总交易数: <b>{filteredStats.totalTrades}</b></span>
            </div>
          )}
          <div className="overflow-auto">
            <table className="w-full text-sm">
              <thead className="bg-muted/30">
                <tr className="border-b text-left text-xs text-muted-foreground">
                  <th className="px-3 py-2">
                    <Checkbox
                      checked={
                        pagedResults.length > 0 &&
                        pagedResults.every(([, r]) => selectedIds.has(r.session_id))
                      }
                      onCheckedChange={toggleSelectPage}
                    />
                  </th>
                  <th className="px-3 py-2">数据源</th>
                  {task.composite_name && (
                    <th className="cursor-pointer select-none px-3 py-2 hover:text-foreground" onClick={() => toggleSort("matched_branch")}>使用策略{sortIndicator("matched_branch")}</th>
                  )}
                  <th className="cursor-pointer select-none px-3 py-2 text-right hover:text-foreground" onClick={() => toggleSort("total_return_pct")}>收益率{sortIndicator("total_return_pct")}</th>
                  <th className="cursor-pointer select-none px-3 py-2 text-right hover:text-foreground" onClick={() => toggleSort("sharpe_ratio")}>Sharpe{sortIndicator("sharpe_ratio")}</th>
                  <th className="cursor-pointer select-none px-3 py-2 text-right hover:text-foreground" onClick={() => toggleSort("win_rate")}>胜率{sortIndicator("win_rate")}</th>
                  <th className="cursor-pointer select-none px-3 py-2 text-right hover:text-foreground" onClick={() => toggleSort("max_drawdown")}>最大回撤{sortIndicator("max_drawdown")}</th>
                  <th className="cursor-pointer select-none px-3 py-2 text-right hover:text-foreground" onClick={() => toggleSort("btc_momentum")}>BTC动量{sortIndicator("btc_momentum")}</th>
                  <th className="cursor-pointer select-none px-3 py-2 text-right hover:text-foreground" onClick={() => toggleSort("total_trades")}>交易数{sortIndicator("total_trades")}</th>
                  <th className="cursor-pointer select-none px-3 py-2 text-right hover:text-foreground" onClick={() => toggleSort("avg_slippage")}>滑点{sortIndicator("avg_slippage")}</th>
                  <th className="px-3 py-2"></th>
                </tr>
              </thead>
              <tbody>
                {pagedResults.map(([slug, r]) => (
                  <tr
                    key={slug}
                    className={cn(
                      "border-b transition-colors hover:bg-muted/30",
                      selectedIds.has(r.session_id) && "bg-primary/5",
                    )}
                  >
                    <td className="px-3 py-2">
                      <Checkbox
                        checked={selectedIds.has(r.session_id)}
                        onCheckedChange={() => toggleSelect(r.session_id)}
                      />
                    </td>
                    <td className="px-3 py-2 font-mono text-xs">{slug}</td>
                    {task.composite_name && (
                      <td className="px-3 py-2 text-xs">
                        {r.matched_branch ? (
                          <span className="rounded bg-primary/10 px-1.5 py-0.5 text-primary">
                            {r.matched_branch}
                          </span>
                        ) : (
                          <span className="text-muted-foreground">未匹配</span>
                        )}
                      </td>
                    )}
                    <td
                      className={cn(
                        "px-3 py-2 text-right font-mono",
                        r.total_return_pct >= 0 ? "text-emerald-600" : "text-red-500",
                      )}
                    >
                      {r.total_return_pct >= 0 ? "+" : ""}
                      {(r.total_return_pct * 100).toFixed(2)}%
                    </td>
                    <td className="px-3 py-2 text-right font-mono">
                      {r.sharpe_ratio.toFixed(4)}
                    </td>
                    <td className="px-3 py-2 text-right font-mono">
                      {(r.win_rate * 100).toFixed(1)}%
                    </td>
                    <td className="px-3 py-2 text-right font-mono text-red-500">
                      {(r.max_drawdown * 100).toFixed(2)}%
                    </td>
                    <td className="px-3 py-2 text-right font-mono">
                      {(r.btc_momentum * 100).toFixed(4)}%
                    </td>
                    <td className="px-3 py-2 text-right font-mono">
                      {r.total_trades}
                    </td>
                    <td className="px-3 py-2 text-right font-mono">
                      {(r.avg_slippage * 100).toFixed(4)}%
                    </td>
                    <td className="px-3 py-2 text-right">
                      <div className="flex items-center justify-end gap-2">
                        <Link
                          to={`/results/${r.session_id}`}
                          target="_blank"
                          className="text-xs text-primary hover:underline"
                        >
                          详情
                        </Link>
                        <button
                          onClick={() => rerunMutation.mutate(r.session_id)}
                          disabled={rerunningIds.has(r.session_id)}
                          className="rounded border px-1.5 py-0.5 text-xs text-muted-foreground transition-colors hover:bg-muted hover:text-foreground disabled:opacity-40 disabled:cursor-wait"
                          title="使用完整 VWAP 深度撮合重新计算"
                        >
                          {rerunningIds.has(r.session_id) ? "计算中…" : "精细计算"}
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {/* Pagination controls */}
          {totalPages > 1 && (
            <div className="flex items-center justify-between border-t px-4 py-2">
              <span className="text-xs text-muted-foreground">
                第 {safePage} / {totalPages} 页 · 共 {filteredResults.length} 条
              </span>
              <div className="flex items-center gap-1">
                <button
                  onClick={() => setCurrentPage(1)}
                  disabled={safePage <= 1}
                  className="rounded-md border px-2 py-1 text-xs font-medium transition-colors hover:bg-muted disabled:opacity-30 disabled:cursor-not-allowed"
                >
                  首页
                </button>
                <button
                  onClick={() => setCurrentPage((p) => Math.max(1, p - 1))}
                  disabled={safePage <= 1}
                  className="rounded-md border px-2 py-1 text-xs font-medium transition-colors hover:bg-muted disabled:opacity-30 disabled:cursor-not-allowed"
                >
                  上一页
                </button>
                <button
                  onClick={() => setCurrentPage((p) => Math.min(totalPages, p + 1))}
                  disabled={safePage >= totalPages}
                  className="rounded-md border px-2 py-1 text-xs font-medium transition-colors hover:bg-muted disabled:opacity-30 disabled:cursor-not-allowed"
                >
                  下一页
                </button>
                <button
                  onClick={() => setCurrentPage(totalPages)}
                  disabled={safePage >= totalPages}
                  className="rounded-md border px-2 py-1 text-xs font-medium transition-colors hover:bg-muted disabled:opacity-30 disabled:cursor-not-allowed"
                >
                  末页
                </button>
              </div>
            </div>
          )}
        </div>
      )}

      <AddToPortfolioDialog
        open={portfolioOpen}
        onOpenChange={setPortfolioOpen}
        items={selectedItems}
      />
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
