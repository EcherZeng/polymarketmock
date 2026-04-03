import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import { useState, useMemo } from "react"
import { cn } from "@/lib/utils"
import { fetchIncomplete, cleanupSlugs, deleteArchive } from "@/api/client"
import type { IncompleteResponse } from "@/api/client"

function fmtSize(mb: number) {
  return mb >= 1 ? `${mb.toFixed(1)} MB` : `${(mb * 1024).toFixed(0)} KB`
}

function fmtTime(iso: string) {
  if (!iso) return "—"
  try {
    return new Date(iso).toLocaleString("zh-CN", { hour12: false })
  } catch {
    return iso.slice(0, 19)
  }
}

export default function DataCleanupPage() {
  const queryClient = useQueryClient()
  const [selected, setSelected] = useState<Set<string>>(new Set())
  const [confirmBulk, setConfirmBulk] = useState(false)
  const [min5m, setMin5m] = useState(100)
  const [min15m, setMin15m] = useState(1000)

  const { data, isLoading, refetch } = useQuery<IncompleteResponse>({
    queryKey: ["incomplete", min5m, min15m],
    queryFn: () => fetchIncomplete(min5m, min15m),
  })

  const items = data?.items ?? []

  const deleteSingleMut = useMutation({
    mutationFn: deleteArchive,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["incomplete"] })
      queryClient.invalidateQueries({ queryKey: ["archives"] })
    },
  })

  const bulkDeleteMut = useMutation({
    mutationFn: (slugs: string[]) => cleanupSlugs(slugs),
    onSuccess: () => {
      setSelected(new Set())
      setConfirmBulk(false)
      queryClient.invalidateQueries({ queryKey: ["incomplete"] })
      queryClient.invalidateQueries({ queryKey: ["archives"] })
    },
  })

  const allSelected = items.length > 0 && selected.size === items.length

  function toggleAll() {
    if (allSelected) {
      setSelected(new Set())
    } else {
      setSelected(new Set(items.map((i) => i.slug)))
    }
  }

  function toggleOne(slug: string) {
    setSelected((prev) => {
      const next = new Set(prev)
      if (next.has(slug)) next.delete(slug)
      else next.add(slug)
      return next
    })
  }

  const totalSize = useMemo(
    () => items.reduce((sum, i) => sum + i.size_mb, 0),
    [items],
  )
  const selectedSize = useMemo(
    () => items.filter((i) => selected.has(i.slug)).reduce((sum, i) => sum + i.size_mb, 0),
    [items, selected],
  )

  // Group by duration for summary
  const groupedSummary = useMemo(() => {
    const groups: Record<number, { count: number; sizeMb: number }> = {}
    for (const item of items) {
      const dur = item.duration_min || 0
      if (!groups[dur]) groups[dur] = { count: 0, sizeMb: 0 }
      groups[dur].count++
      groups[dur].sizeMb += item.size_mb
    }
    return groups
  }, [items])

  return (
    <div className="flex flex-col gap-4">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold tracking-tight">数据源清理</h1>
        <p className="text-sm text-muted-foreground">
          扫描不完整的录制数据，可批量删除释放空间
        </p>
      </div>

      {/* Threshold controls */}
      <div className="flex flex-wrap items-end gap-4 rounded-lg border p-4">
        <div className="flex flex-col gap-1">
          <label className="text-xs text-muted-foreground">5 分钟场次最低成交量</label>
          <input
            type="number"
            min={0}
            value={min5m}
            onChange={(e) => setMin5m(Number(e.target.value))}
            className="h-9 w-28 rounded-md border bg-background px-3 text-sm"
          />
        </div>
        <div className="flex flex-col gap-1">
          <label className="text-xs text-muted-foreground">15 分钟场次最低成交量</label>
          <input
            type="number"
            min={0}
            value={min15m}
            onChange={(e) => setMin15m(Number(e.target.value))}
            className="h-9 w-28 rounded-md border bg-background px-3 text-sm"
          />
        </div>
        <button
          onClick={() => refetch()}
          className="h-9 rounded-md border px-4 text-sm hover:bg-accent"
        >
          扫描
        </button>
      </div>

      {/* Summary cards */}
      {data && (
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          <div className="rounded-lg border p-3">
            <p className="text-xs text-muted-foreground">总数据源</p>
            <p className="text-xl font-semibold">{data.total_archives}</p>
          </div>
          <div className="rounded-lg border p-3">
            <p className="text-xs text-muted-foreground">不完整</p>
            <p className="text-xl font-semibold text-destructive">
              {data.incomplete_count}
            </p>
          </div>
          {Object.entries(groupedSummary).map(([dur, g]) => (
            <div key={dur} className="rounded-lg border p-3">
              <p className="text-xs text-muted-foreground">{dur}m 不完整</p>
              <p className="text-lg font-semibold">
                {g.count} <span className="text-xs text-muted-foreground">({fmtSize(g.sizeMb)})</span>
              </p>
            </div>
          ))}
          <div className="rounded-lg border p-3">
            <p className="text-xs text-muted-foreground">总占用</p>
            <p className="text-lg font-semibold">{fmtSize(totalSize)}</p>
          </div>
        </div>
      )}

      {/* Bulk actions */}
      {items.length > 0 && (
        <div className="flex items-center gap-3">
          <span className="text-sm text-muted-foreground">
            已选 {selected.size} / {items.length}
            {selected.size > 0 && ` (${fmtSize(selectedSize)})`}
          </span>
          {confirmBulk ? (
            <div className="flex items-center gap-2">
              <span className="text-sm text-destructive">
                确认删除 {selected.size} 个数据源?
              </span>
              <button
                disabled={bulkDeleteMut.isPending}
                onClick={() => bulkDeleteMut.mutate([...selected])}
                className="h-8 rounded-md bg-destructive px-3 text-sm text-white disabled:opacity-50"
              >
                {bulkDeleteMut.isPending ? "删除中..." : "确认删除"}
              </button>
              <button
                onClick={() => setConfirmBulk(false)}
                className="h-8 rounded-md border px-3 text-sm"
              >
                取消
              </button>
            </div>
          ) : (
            <button
              disabled={selected.size === 0}
              onClick={() => setConfirmBulk(true)}
              className="h-8 rounded-md border border-destructive px-3 text-sm text-destructive hover:bg-destructive/10 disabled:opacity-30"
            >
              批量删除
            </button>
          )}
          <button
            onClick={toggleAll}
            className="h-8 rounded-md border px-3 text-sm text-muted-foreground hover:text-foreground"
          >
            {allSelected ? "取消全选" : "全选"}
          </button>
        </div>
      )}

      {/* Table */}
      {isLoading ? (
        <div className="py-12 text-center text-muted-foreground">扫描中...</div>
      ) : items.length === 0 ? (
        <div className="py-12 text-center text-muted-foreground">
          没有不完整的数据源 🎉
        </div>
      ) : (
        <div className="overflow-x-auto rounded-lg border">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b bg-muted/50 text-left text-xs text-muted-foreground">
                <th className="w-10 px-3 py-2">
                  <input
                    type="checkbox"
                    checked={allSelected}
                    onChange={toggleAll}
                    className="size-4 rounded border"
                  />
                </th>
                <th className="px-3 py-2">数据源</th>
                <th className="px-3 py-2 text-right">时长</th>
                <th className="px-3 py-2 text-right">成交量</th>
                <th className="px-3 py-2 text-right">阈值</th>
                <th className="px-3 py-2 text-right">订单簿</th>
                <th className="px-3 py-2 text-right">大小</th>
                <th className="px-3 py-2">来源</th>
                <th className="px-3 py-2">时间范围</th>
                <th className="w-20 px-3 py-2" />
              </tr>
            </thead>
            <tbody>
              {items.map((item) => (
                <tr
                  key={item.slug}
                  className={cn(
                    "border-b transition-colors hover:bg-muted/30",
                    selected.has(item.slug) && "bg-muted/20",
                  )}
                >
                  <td className="px-3 py-2">
                    <input
                      type="checkbox"
                      checked={selected.has(item.slug)}
                      onChange={() => toggleOne(item.slug)}
                      className="size-4 rounded border"
                    />
                  </td>
                  <td className="px-3 py-2 font-mono text-xs">{item.slug}</td>
                  <td className="px-3 py-2 text-right">{item.duration_min}m</td>
                  <td className="px-3 py-2 text-right">
                    <span
                      className={cn(
                        "font-medium",
                        item.live_trades_count < item.threshold
                          ? "text-destructive"
                          : "text-foreground",
                      )}
                    >
                      {item.live_trades_count.toLocaleString()}
                    </span>
                  </td>
                  <td className="px-3 py-2 text-right text-muted-foreground">
                    {item.threshold.toLocaleString()}
                  </td>
                  <td className="px-3 py-2 text-right">
                    {item.orderbooks_count.toLocaleString()}
                  </td>
                  <td className="px-3 py-2 text-right">{fmtSize(item.size_mb)}</td>
                  <td className="px-3 py-2">
                    <span
                      className={cn(
                        "inline-flex rounded-full px-2 py-0.5 text-xs",
                        item.source === "archive"
                          ? "bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-400"
                          : "bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-400",
                      )}
                    >
                      {item.source}
                    </span>
                  </td>
                  <td className="px-3 py-2 text-xs text-muted-foreground">
                    {fmtTime(item.time_range?.start)}
                  </td>
                  <td className="px-3 py-2">
                    <button
                      onClick={() => {
                        if (confirm(`确认删除 ${item.slug}？`)) {
                          deleteSingleMut.mutate(item.slug)
                        }
                      }}
                      disabled={deleteSingleMut.isPending}
                      className="h-7 rounded-md border border-destructive/50 px-2 text-xs text-destructive hover:bg-destructive/10 disabled:opacity-50"
                    >
                      删除
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
