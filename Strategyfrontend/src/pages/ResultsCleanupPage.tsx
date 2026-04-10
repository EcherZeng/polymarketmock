import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import { useState, useMemo } from "react"
import { Link } from "react-router-dom"
import { cn } from "@/lib/utils"
import {
  fetchResultsStats,
  cleanupResultsBulk,
  cleanupBatchesBulk,
  purgeRunnerMemory,
  clearResults,
} from "@/api/client"
import type { ResultsStatsResponse, ResultStatItem } from "@/api/client"

function fmtSize(kb: number) {
  return kb >= 1024 ? `${(kb / 1024).toFixed(1)} MB` : `${kb.toFixed(0)} KB`
}

function fmtTime(iso: string) {
  if (!iso) return "—"
  try {
    return new Date(iso).toLocaleString("zh-CN", { hour12: false })
  } catch {
    return iso.slice(0, 19)
  }
}

function fmtPct(v: number) {
  const pct = v * 100
  return `${pct >= 0 ? "+" : ""}${pct.toFixed(2)}%`
}

type Tab = "standalone" | "batches"

export default function ResultsCleanupPage() {
  const queryClient = useQueryClient()
  const [tab, setTab] = useState<Tab>("standalone")
  const [selectedResults, setSelectedResults] = useState<Set<string>>(new Set())
  const [selectedBatches, setSelectedBatches] = useState<Set<string>>(new Set())
  const [expandedBatchId, setExpandedBatchId] = useState<string | null>(null)
  const [confirmAction, setConfirmAction] = useState<string | null>(null)

  const { data, isLoading, refetch } = useQuery<ResultsStatsResponse>({
    queryKey: ["results-stats"],
    queryFn: fetchResultsStats,
  })

  const allResults = data?.results ?? []
  const batches = data?.batches ?? []

  // Split results into standalone (no batch_id) and batch-associated
  const standaloneResults = useMemo(
    () => allResults.filter((r) => !r.batch_id),
    [allResults],
  )

  const batchResultsMap = useMemo(() => {
    const map: Record<string, ResultStatItem[]> = {}
    for (const r of allResults) {
      if (r.batch_id) {
        if (!map[r.batch_id]) map[r.batch_id] = []
        map[r.batch_id].push(r)
      }
    }
    return map
  }, [allResults])

  // ── Mutations ───────────────────────────────────────────────────────────

  const deleteResultsMut = useMutation({
    mutationFn: (ids: string[]) => cleanupResultsBulk(ids),
    onSuccess: () => {
      setSelectedResults(new Set())
      setConfirmAction(null)
      queryClient.invalidateQueries({ queryKey: ["results-stats"] })
      queryClient.invalidateQueries({ queryKey: ["results"] })
    },
  })

  const deleteBatchesMut = useMutation({
    mutationFn: (ids: string[]) => cleanupBatchesBulk(ids),
    onSuccess: () => {
      setSelectedBatches(new Set())
      setConfirmAction(null)
      queryClient.invalidateQueries({ queryKey: ["results-stats"] })
      queryClient.invalidateQueries({ queryKey: ["results"] })
      queryClient.invalidateQueries({ queryKey: ["batch-tasks"] })
    },
  })

  const clearAllMut = useMutation({
    mutationFn: clearResults,
    onSuccess: () => {
      setConfirmAction(null)
      queryClient.invalidateQueries({ queryKey: ["results-stats"] })
      queryClient.invalidateQueries({ queryKey: ["results"] })
    },
  })

  const purgeMut = useMutation({
    mutationFn: purgeRunnerMemory,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["results-stats"] })
    },
  })

  // ── Selection helpers ─────────────────────────────────────────────────

  function toggleResultAll() {
    if (selectedResults.size === standaloneResults.length) {
      setSelectedResults(new Set())
    } else {
      setSelectedResults(new Set(standaloneResults.map((r) => r.session_id)))
    }
  }

  function toggleResult(sid: string) {
    setSelectedResults((prev) => {
      const next = new Set(prev)
      if (next.has(sid)) next.delete(sid)
      else next.add(sid)
      return next
    })
  }

  function toggleBatchAll() {
    if (selectedBatches.size === batches.length) {
      setSelectedBatches(new Set())
    } else {
      setSelectedBatches(new Set(batches.map((b) => b.batch_id)))
    }
  }

  function toggleBatch(bid: string) {
    setSelectedBatches((prev) => {
      const next = new Set(prev)
      if (next.has(bid)) next.delete(bid)
      else next.add(bid)
      return next
    })
  }

  // ── Computed ──────────────────────────────────────────────────────────

  const selectedResultsSize = useMemo(
    () => standaloneResults.filter((r) => selectedResults.has(r.session_id)).reduce((s, r) => s + r.size_kb, 0),
    [standaloneResults, selectedResults],
  )

  const selectedBatchesSize = useMemo(
    () => batches.filter((b) => selectedBatches.has(b.batch_id)).reduce((s, b) => s + b.size_kb, 0),
    [batches, selectedBatches],
  )

  const standaloneSize = useMemo(
    () => standaloneResults.reduce((s, r) => s + r.size_kb, 0),
    [standaloneResults],
  )

  const batchResultsSize = useMemo(
    () => allResults.filter((r) => r.batch_id).reduce((s, r) => s + r.size_kb, 0),
    [allResults],
  )

  return (
    <div className="flex flex-col gap-4">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold tracking-tight">结果清理</h1>
        <p className="text-sm text-muted-foreground">
          管理回测结果和批量任务记录，释放磁盘空间和内存
        </p>
      </div>

      {/* Summary cards */}
      {data && (
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-5">
          <div className="rounded-lg border p-3">
            <p className="text-xs text-muted-foreground">单独回测</p>
            <p className="text-xl font-semibold">{standaloneResults.length}</p>
            <p className="text-xs text-muted-foreground">{fmtSize(standaloneSize)}</p>
          </div>
          <div className="rounded-lg border p-3">
            <p className="text-xs text-muted-foreground">批量回测</p>
            <p className="text-xl font-semibold">{batches.length}</p>
            <p className="text-xs text-muted-foreground">
              {data.batches_total_size_mb.toFixed(1)} MB (记录) + {fmtSize(batchResultsSize)} (结果)
            </p>
          </div>
          <div className="rounded-lg border p-3">
            <p className="text-xs text-muted-foreground">总磁盘占用</p>
            <p className="text-xl font-semibold">
              {(data.results_total_size_mb + data.batches_total_size_mb).toFixed(1)} MB
            </p>
          </div>
          <div className="rounded-lg border p-3">
            <p className="text-xs text-muted-foreground">内存中任务</p>
            <p className="text-xl font-semibold">{data.runner_tasks_in_memory}</p>
            <p className="text-xs text-muted-foreground">{data.runner_tasks_running} 运行中</p>
          </div>
          <div className="rounded-lg border p-3">
            <p className="text-xs text-muted-foreground">总结果数</p>
            <p className="text-xl font-semibold">{data.results_count}</p>
            <p className="text-xs text-muted-foreground">{data.results_total_size_mb.toFixed(1)} MB</p>
          </div>
        </div>
      )}

      {/* Quick actions */}
      <div className="flex flex-wrap items-center gap-2">
        <button
          onClick={() => purgeMut.mutate()}
          disabled={purgeMut.isPending || !data || data.runner_tasks_in_memory === 0}
          className="h-8 rounded-md border px-3 text-sm hover:bg-accent disabled:opacity-30"
        >
          {purgeMut.isPending ? "清理中..." : "清理内存任务"}
        </button>
        {confirmAction === "clear-all" ? (
          <div className="flex items-center gap-2">
            <span className="text-sm text-destructive">确认清空所有回测结果？</span>
            <button
              disabled={clearAllMut.isPending}
              onClick={() => clearAllMut.mutate()}
              className="h-8 rounded-md bg-destructive px-3 text-sm text-white disabled:opacity-50"
            >
              {clearAllMut.isPending ? "清空中..." : "确认清空"}
            </button>
            <button
              onClick={() => setConfirmAction(null)}
              className="h-8 rounded-md border px-3 text-sm"
            >
              取消
            </button>
          </div>
        ) : (
          <button
            onClick={() => setConfirmAction("clear-all")}
            disabled={!data || data.results_count === 0}
            className="h-8 rounded-md border border-destructive px-3 text-sm text-destructive hover:bg-destructive/10 disabled:opacity-30"
          >
            清空全部结果
          </button>
        )}
        <button
          onClick={() => refetch()}
          className="h-8 rounded-md border px-3 text-sm hover:bg-accent"
        >
          刷新
        </button>
      </div>

      {/* Tab switcher */}
      <div className="flex gap-1 border-b">
        <button
          onClick={() => setTab("standalone")}
          className={cn(
            "px-4 py-2 text-sm transition-colors",
            tab === "standalone"
              ? "border-b-2 border-foreground font-medium text-foreground"
              : "text-muted-foreground hover:text-foreground",
          )}
        >
          单独回测 ({standaloneResults.length})
        </button>
        <button
          onClick={() => setTab("batches")}
          className={cn(
            "px-4 py-2 text-sm transition-colors",
            tab === "batches"
              ? "border-b-2 border-foreground font-medium text-foreground"
              : "text-muted-foreground hover:text-foreground",
          )}
        >
          批量回测 ({batches.length})
        </button>
      </div>

      {isLoading && (
        <div className="py-12 text-center text-muted-foreground">加载中...</div>
      )}

      {/* ── Standalone results tab ─────────────────────────────────────────── */}
      {!isLoading && tab === "standalone" && (
        <>
          {standaloneResults.length > 0 && (
            <div className="flex items-center gap-3">
              <span className="text-sm text-muted-foreground">
                已选 {selectedResults.size} / {standaloneResults.length}
                {selectedResults.size > 0 && ` (${fmtSize(selectedResultsSize)})`}
              </span>
              {confirmAction === "delete-results" ? (
                <div className="flex items-center gap-2">
                  <span className="text-sm text-destructive">
                    确认删除 {selectedResults.size} 个结果?
                  </span>
                  <button
                    disabled={deleteResultsMut.isPending}
                    onClick={() => deleteResultsMut.mutate([...selectedResults])}
                    className="h-8 rounded-md bg-destructive px-3 text-sm text-white disabled:opacity-50"
                  >
                    {deleteResultsMut.isPending ? "删除中..." : "确认删除"}
                  </button>
                  <button
                    onClick={() => setConfirmAction(null)}
                    className="h-8 rounded-md border px-3 text-sm"
                  >
                    取消
                  </button>
                </div>
              ) : (
                <button
                  disabled={selectedResults.size === 0}
                  onClick={() => setConfirmAction("delete-results")}
                  className="h-8 rounded-md border border-destructive px-3 text-sm text-destructive hover:bg-destructive/10 disabled:opacity-30"
                >
                  批量删除
                </button>
              )}
              <button
                onClick={toggleResultAll}
                className="h-8 rounded-md border px-3 text-sm text-muted-foreground hover:text-foreground"
              >
                {selectedResults.size === standaloneResults.length ? "取消全选" : "全选"}
              </button>
            </div>
          )}

          {standaloneResults.length === 0 ? (
            <div className="py-12 text-center text-muted-foreground">暂无单独回测结果</div>
          ) : (
            <div className="overflow-x-auto rounded-lg border">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b bg-muted/50 text-left text-xs text-muted-foreground">
                    <th className="w-10 px-3 py-2">
                      <input
                        type="checkbox"
                        checked={selectedResults.size === standaloneResults.length && standaloneResults.length > 0}
                        onChange={toggleResultAll}
                        className="size-4 rounded border"
                      />
                    </th>
                    <th className="px-3 py-2">策略</th>
                    <th className="px-3 py-2">数据源</th>
                    <th className="px-3 py-2 text-right">收益率</th>
                    <th className="px-3 py-2 text-right">交易数</th>
                    <th className="px-3 py-2 text-right">大小</th>
                    <th className="px-3 py-2">时间</th>
                  </tr>
                </thead>
                <tbody>
                  {standaloneResults.map((r) => (
                    <tr
                      key={r.session_id}
                      className={cn(
                        "border-b transition-colors hover:bg-muted/30",
                        selectedResults.has(r.session_id) && "bg-muted/20",
                      )}
                    >
                      <td className="px-3 py-2">
                        <input
                          type="checkbox"
                          checked={selectedResults.has(r.session_id)}
                          onChange={() => toggleResult(r.session_id)}
                          className="size-4 rounded border"
                        />
                      </td>
                      <td className="px-3 py-2 font-medium">{r.strategy}</td>
                      <td className="px-3 py-2 font-mono text-xs">{r.slug}</td>
                      <td
                        className={cn(
                          "px-3 py-2 text-right font-medium",
                          r.total_return_pct >= 0 ? "text-emerald-600" : "text-red-500",
                        )}
                      >
                        {fmtPct(r.total_return_pct)}
                      </td>
                      <td className="px-3 py-2 text-right">{r.total_trades}</td>
                      <td className="px-3 py-2 text-right">{fmtSize(r.size_kb)}</td>
                      <td className="px-3 py-2 text-xs text-muted-foreground">
                        {fmtTime(r.created_at)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </>
      )}

      {/* ── Batches tab ──────────────────────────────────────────────────── */}
      {!isLoading && tab === "batches" && (
        <>
          {batches.length > 0 && (
            <div className="flex items-center gap-3">
              <span className="text-sm text-muted-foreground">
                已选 {selectedBatches.size} / {batches.length}
                {selectedBatches.size > 0 && ` (${fmtSize(selectedBatchesSize)})`}
              </span>
              {confirmAction === "delete-batches" ? (
                <div className="flex items-center gap-2">
                  <span className="text-sm text-destructive">
                    确认删除 {selectedBatches.size} 个批量记录及其关联结果?
                  </span>
                  <button
                    disabled={deleteBatchesMut.isPending}
                    onClick={() => deleteBatchesMut.mutate([...selectedBatches])}
                    className="h-8 rounded-md bg-destructive px-3 text-sm text-white disabled:opacity-50"
                  >
                    {deleteBatchesMut.isPending ? "删除中..." : "确认删除"}
                  </button>
                  <button
                    onClick={() => setConfirmAction(null)}
                    className="h-8 rounded-md border px-3 text-sm"
                  >
                    取消
                  </button>
                </div>
              ) : (
                <button
                  disabled={selectedBatches.size === 0}
                  onClick={() => setConfirmAction("delete-batches")}
                  className="h-8 rounded-md border border-destructive px-3 text-sm text-destructive hover:bg-destructive/10 disabled:opacity-30"
                >
                  批量删除（含关联结果）
                </button>
              )}
              <button
                onClick={toggleBatchAll}
                className="h-8 rounded-md border px-3 text-sm text-muted-foreground hover:text-foreground"
              >
                {selectedBatches.size === batches.length ? "取消全选" : "全选"}
              </button>
            </div>
          )}

          {batches.length === 0 ? (
            <div className="py-12 text-center text-muted-foreground">暂无批量记录</div>
          ) : (
            <div className="rounded-lg border">
              {batches.map((b) => {
                const batchResults = batchResultsMap[b.batch_id] ?? []
                const isExpanded = expandedBatchId === b.batch_id
                const batchResultsTotalSize = batchResults.reduce((s, r) => s + r.size_kb, 0)
                return (
                  <div key={b.batch_id} className="border-b last:border-b-0">
                    {/* Batch header row */}
                    <div className={cn(
                      "flex items-center gap-3 px-3 py-2.5 transition-colors hover:bg-muted/30",
                      selectedBatches.has(b.batch_id) && "bg-muted/20",
                    )}>
                      <input
                        type="checkbox"
                        checked={selectedBatches.has(b.batch_id)}
                        onChange={() => toggleBatch(b.batch_id)}
                        className="size-4 rounded border"
                      />
                      <button
                        onClick={() => setExpandedBatchId(isExpanded ? null : b.batch_id)}
                        className="flex min-w-0 flex-1 items-center gap-3 text-left"
                      >
                        <span className="text-xs text-muted-foreground">
                          {isExpanded ? "▼" : "▶"}
                        </span>
                        <span className="font-mono text-xs">{b.batch_id}</span>
                        <span className="font-medium">{b.strategy}</span>
                        <span
                          className={cn(
                            "inline-flex rounded-full px-2 py-0.5 text-xs",
                            b.status === "completed"
                              ? "bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-400"
                              : b.status === "running"
                                ? "bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-400"
                                : "bg-gray-100 text-gray-800 dark:bg-gray-900/30 dark:text-gray-400",
                          )}
                        >
                          {b.status}
                        </span>
                        <span className="text-xs text-muted-foreground">
                          {b.completed}/{b.total} 场
                        </span>
                      </button>
                      <span className="text-xs text-muted-foreground">
                        {fmtSize(b.size_kb + batchResultsTotalSize)}
                      </span>
                      <span className="text-xs text-muted-foreground">
                        {fmtTime(b.created_at)}
                      </span>
                      <Link
                        to={`/batch/${b.batch_id}`}
                        className="text-xs text-primary hover:underline"
                      >
                        详情
                      </Link>
                    </div>

                    {/* Expanded: child results */}
                    {isExpanded && (
                      <div className="border-t bg-muted/10">
                        {batchResults.length === 0 ? (
                          <div className="px-6 py-3 text-xs text-muted-foreground">
                            无关联回测结果
                          </div>
                        ) : (
                          <table className="w-full text-sm">
                            <thead>
                              <tr className="text-left text-xs text-muted-foreground">
                                <th className="px-6 py-1.5">数据源</th>
                                <th className="px-3 py-1.5 text-right">收益率</th>
                                <th className="px-3 py-1.5 text-right">交易数</th>
                                <th className="px-3 py-1.5 text-right">大小</th>
                                <th className="px-3 py-1.5"></th>
                              </tr>
                            </thead>
                            <tbody>
                              {batchResults.map((r) => (
                                <tr
                                  key={r.session_id}
                                  className="border-t border-muted/30 transition-colors hover:bg-muted/20"
                                >
                                  <td className="px-6 py-1.5 font-mono text-xs">{r.slug}</td>
                                  <td
                                    className={cn(
                                      "px-3 py-1.5 text-right font-medium text-xs",
                                      r.total_return_pct >= 0 ? "text-emerald-600" : "text-red-500",
                                    )}
                                  >
                                    {fmtPct(r.total_return_pct)}
                                  </td>
                                  <td className="px-3 py-1.5 text-right text-xs">{r.total_trades}</td>
                                  <td className="px-3 py-1.5 text-right text-xs">{fmtSize(r.size_kb)}</td>
                                  <td className="px-3 py-1.5 text-right">
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
                        )}
                      </div>
                    )}
                  </div>
                )
              })}
            </div>
          )}
        </>
      )}
    </div>
  )
}
