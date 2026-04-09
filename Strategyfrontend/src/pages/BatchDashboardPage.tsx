import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import { useMemo } from "react"
import { Link } from "react-router-dom"
import { cn } from "@/lib/utils"
import { fetchBatchTasks, cancelBatch } from "@/api/client"
import type { BatchTask } from "@/types"

const statusLabel: Record<string, string> = {
  running: "运行中",
  completed: "已完成",
  cancelled: "已取消",
  interrupted: "已中断",
}

const statusColor: Record<string, string> = {
  running: "bg-blue-100 text-blue-700",
  completed: "bg-emerald-100 text-emerald-700",
  cancelled: "bg-red-100 text-red-700",
  interrupted: "bg-orange-100 text-orange-700",
}

export default function BatchDashboardPage() {
  const queryClient = useQueryClient()

  const { data: rawTasks = [], isLoading } = useQuery<BatchTask[]>({
    queryKey: ["batchTasks"],
    queryFn: fetchBatchTasks,
    refetchInterval: (query) => {
      const data = query.state.data
      return data?.some((t) => t.status === "running") ? 3000 : false
    },
  })

  const tasks = useMemo(
    () => [...rawTasks].sort((a, b) => b.created_at.localeCompare(a.created_at)),
    [rawTasks],
  )

  const cancelMutation = useMutation({
    mutationFn: (batchId: string) => cancelBatch(batchId),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["batchTasks"] }),
  })

  if (isLoading) {
    return <div className="py-12 text-center text-muted-foreground">加载中...</div>
  }

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">批量回测</h1>
        <p className="text-sm text-muted-foreground">
          {tasks.length} 个批量任务
        </p>
      </div>

      {tasks.length === 0 ? (
        <div className="flex flex-col items-center gap-3 py-12 text-muted-foreground">
          <p>暂无批量任务</p>
          <Link to="/" className="text-sm text-primary underline">
            前往策略回测页面创建批量任务
          </Link>
        </div>
      ) : (
        <div className="flex flex-col gap-3">
          {tasks.map((t) => {
            const progress = t.total > 0 ? (t.completed / t.total) * 100 : 0
            return (
              <Link
                key={t.batch_id}
                to={`/batch/${t.batch_id}`}
                className="rounded-lg border p-4 transition-colors hover:border-primary/50"
              >
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <span className="font-mono text-sm font-medium">{t.batch_id}</span>
                    <span
                      className={cn(
                        "rounded-full px-2 py-0.5 text-xs font-medium",
                        statusColor[t.status] ?? "bg-muted text-muted-foreground",
                      )}
                    >
                      {statusLabel[t.status] ?? t.status}
                    </span>
                  </div>
                  <span className="text-xs text-muted-foreground">
                    {t.created_at.replace("T", " ").slice(0, 19)}
                  </span>
                </div>

                <div className="mt-2 flex items-center gap-4 text-sm text-muted-foreground">
                  <span>策略: <span className="font-medium text-foreground">{t.strategy}</span></span>
                  <span>·</span>
                  <span>{t.completed} / {t.total}</span>
                </div>

                {/* Progress bar */}
                <div className="mt-2 h-1.5 w-full overflow-hidden rounded-full bg-muted">
                  <div
                    className={cn(
                      "h-full rounded-full transition-all duration-300",
                      t.status === "completed"
                        ? "bg-emerald-500"
                        : t.status === "cancelled" || t.status === "interrupted"
                          ? "bg-red-400"
                          : "bg-blue-500",
                    )}
                    style={{ width: `${progress}%` }}
                  />
                </div>

                {/* Cancel button for running tasks */}
                {t.status === "running" && (
                  <button
                    onClick={(e) => {
                      e.preventDefault()
                      e.stopPropagation()
                      cancelMutation.mutate(t.batch_id)
                    }}
                    className="mt-2 rounded-md border px-3 py-1 text-xs font-medium text-red-600 transition-colors hover:bg-red-50"
                  >
                    取消
                  </button>
                )}
              </Link>
            )
          })}
        </div>
      )}
    </div>
  )
}
