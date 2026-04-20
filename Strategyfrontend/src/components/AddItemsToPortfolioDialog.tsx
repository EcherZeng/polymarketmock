import { useState, useMemo } from "react"
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import { cn, fmtDateTimeCst } from "@/lib/utils"
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from "@/components/ui/dialog"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { ScrollArea } from "@/components/ui/scroll-area"
import { Checkbox } from "@/components/ui/checkbox"
import {
  fetchArchives,
  fetchBatchTasks,
  fetchBatchTask,
  fetchPortfolios,
  addPortfolioItems,
} from "@/api/client"
import type {
  PortfolioItem,
  ArchiveInfo,
  BatchTask,
  BatchTaskDetail,
  Portfolio,
} from "@/types"

type SourceTab = "archives" | "batches" | "portfolios"

interface AddItemsToPortfolioDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  portfolioId: string
  existingSessionIds: Set<string>
  existingSlugs: Set<string>
  groupStrategy?: string
}

export default function AddItemsToPortfolioDialog({
  open,
  onOpenChange,
  portfolioId,
  existingSessionIds,
  existingSlugs,
  groupStrategy,
}: AddItemsToPortfolioDialogProps) {
  const queryClient = useQueryClient()
  const [tab, setTab] = useState<SourceTab>("archives")
  const [search, setSearch] = useState("")
  const [selectedItems, setSelectedItems] = useState<Map<string, PortfolioItem>>(new Map())
  const [expandedBatchId, setExpandedBatchId] = useState<string | null>(null)
  const [archivePage, setArchivePage] = useState(1)
  const ARCHIVE_PAGE_SIZE = 20

  // ── Data queries ──────────────────────────────────────────────────────────

  const { data: archives = [] } = useQuery<ArchiveInfo[]>({
    queryKey: ["archives"],
    queryFn: fetchArchives,
    enabled: open && tab === "archives",
  })

  const { data: batchTasks = [] } = useQuery<BatchTask[]>({
    queryKey: ["batchTasks"],
    queryFn: fetchBatchTasks,
    enabled: open && tab === "batches",
  })

  const { data: batchDetail } = useQuery<BatchTaskDetail>({
    queryKey: ["batchTask", expandedBatchId],
    queryFn: () => fetchBatchTask(expandedBatchId!),
    enabled: open && tab === "batches" && !!expandedBatchId,
  })

  const { data: portfolios = [] } = useQuery<Portfolio[]>({
    queryKey: ["portfolios"],
    queryFn: fetchPortfolios,
    enabled: open && tab === "portfolios",
  })

  // ── Mutation ──────────────────────────────────────────────────────────────

  const addMutation = useMutation({
    mutationFn: (items: PortfolioItem[]) => addPortfolioItems(portfolioId, items),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["portfolio", portfolioId] })
      queryClient.invalidateQueries({ queryKey: ["portfolios"] })
      handleClose()
    },
  })

  // ── Filtering ─────────────────────────────────────────────────────────────

  const term = search.trim().toLowerCase()

  const filteredArchives = useMemo(() => {
    const list = term
      ? archives.filter((a) => a.slug.toLowerCase().includes(term))
      : archives
    return list.filter((a) => !existingSlugs.has(a.slug))
  }, [archives, term, existingSlugs])

  const archiveTotalPages = Math.max(1, Math.ceil(filteredArchives.length / ARCHIVE_PAGE_SIZE))
  const pagedArchives = useMemo(() => {
    const start = (archivePage - 1) * ARCHIVE_PAGE_SIZE
    return filteredArchives.slice(start, start + ARCHIVE_PAGE_SIZE)
  }, [filteredArchives, archivePage, ARCHIVE_PAGE_SIZE])

  const filteredBatchTasks = useMemo(() => {
    let completed = batchTasks.filter((t) => t.status === "completed")
    if (groupStrategy) {
      completed = completed.filter((t) => t.strategy === groupStrategy)
    }
    if (!term) return completed
    return completed.filter(
      (t) =>
        t.batch_id.toLowerCase().includes(term) ||
        t.strategy.toLowerCase().includes(term),
    )
  }, [batchTasks, term, groupStrategy])

  const filteredPortfolios = useMemo(() => {
    const others = portfolios.filter((p) => p.portfolio_id !== portfolioId)
    if (!term && !groupStrategy) return others
    return others.filter((p) => {
      const hasMatchingItems = groupStrategy
        ? p.items.some((it) => it.strategy === groupStrategy)
        : true
      if (!hasMatchingItems) return false
      if (!term) return true
      return (
        p.name.toLowerCase().includes(term) ||
        p.items.some((it) => it.slug.toLowerCase().includes(term))
      )
    })
  }, [portfolios, term, portfolioId, groupStrategy])

  // ── Batch detail results (deduplicated) ───────────────────────────────────

  const batchResults = useMemo<[string, PortfolioItem][]>(() => {
    if (!batchDetail?.results) return []
    return Object.entries(batchDetail.results)
      .filter(([, r]) => !existingSessionIds.has(r.session_id))
      .map(([slug, r]) => [
        slug,
        {
          session_id: r.session_id,
          strategy: batchDetail.strategy,
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
          btc_momentum: (r as unknown as Record<string, unknown>).btc_momentum as number ?? 0,
          config: batchDetail.config ?? {},
        } as PortfolioItem,
      ])
  }, [batchDetail, existingSessionIds])

  // ── Selection helpers ─────────────────────────────────────────────────────

  function toggleItem(item: PortfolioItem) {
    setSelectedItems((prev) => {
      const next = new Map(prev)
      if (next.has(item.session_id)) {
        next.delete(item.session_id)
      } else {
        next.set(item.session_id, item)
      }
      return next
    })
  }

  function addArchiveAsPlaceholder(a: ArchiveInfo) {
    const key = `archive:${a.slug}`
    setSelectedItems((prev) => {
      const next = new Map(prev)
      if (next.has(key)) {
        next.delete(key)
      } else {
        next.set(key, {
          session_id: key,
          strategy: "",
          slug: a.slug,
          total_return_pct: 0,
          sharpe_ratio: 0,
          win_rate: 0,
          max_drawdown: 0,
          profit_factor: 0,
          total_trades: 0,
          avg_slippage: 0,
          initial_balance: 0,
          final_equity: 0,
          btc_momentum: 0,
          config: {},
        })
      }
      return next
    })
  }

  function addPortfolioItems_bulk(items: PortfolioItem[]) {
    setSelectedItems((prev) => {
      const next = new Map(prev)
      for (const it of items) {
        if (!existingSessionIds.has(it.session_id) && !next.has(it.session_id)) {
          next.set(it.session_id, it)
        }
      }
      return next
    })
  }

  function selectAllBatchResults() {
    for (const [, item] of batchResults) {
      if (!selectedItems.has(item.session_id)) {
        setSelectedItems((prev) => new Map([...prev, [item.session_id, item]]))
      }
    }
  }

  const allFilteredArchivesSelected = filteredArchives.length > 0 &&
    filteredArchives.every((a) => selectedItems.has(`archive:${a.slug}`))

  function toggleSelectAllArchives() {
    if (allFilteredArchivesSelected) {
      setSelectedItems((prev) => {
        const next = new Map(prev)
        for (const a of filteredArchives) {
          next.delete(`archive:${a.slug}`)
        }
        return next
      })
    } else {
      setSelectedItems((prev) => {
        const next = new Map(prev)
        for (const a of filteredArchives) {
          const key = `archive:${a.slug}`
          if (!next.has(key)) {
            next.set(key, {
              session_id: key,
              strategy: "",
              slug: a.slug,
              total_return_pct: 0,
              sharpe_ratio: 0,
              win_rate: 0,
              max_drawdown: 0,
              profit_factor: 0,
              total_trades: 0,
              avg_slippage: 0,
              initial_balance: 0,
              final_equity: 0,
              btc_momentum: 0,
              config: {},
            })
          }
        }
        return next
      })
    }
  }

  function handleClose() {
    setSelectedItems(new Map())
    setSearch("")
    setExpandedBatchId(null)
    setArchivePage(1)
    onOpenChange(false)
  }

  function handleConfirm() {
    const items = [...selectedItems.values()]
    if (items.length === 0) return
    addMutation.mutate(items)
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-2xl">
        <DialogHeader>
          <DialogTitle>新增数据源到组合</DialogTitle>
          <DialogDescription>
            从数据源、批量回测结果或其他组合中选取项目（已去重）
          </DialogDescription>
        </DialogHeader>

        {/* Tab switcher */}
        <div className="flex items-center gap-2">
          {(["archives", "batches", "portfolios"] as const).map((t) => (
            <button
              key={t}
              onClick={() => {
                setTab(t)
                setSearch("")
                setExpandedBatchId(null)
                setArchivePage(1)
              }}
              className={cn(
                "rounded-md px-3 py-1.5 text-sm font-medium transition-colors",
                tab === t
                  ? "bg-foreground text-background"
                  : "text-muted-foreground hover:text-foreground",
              )}
            >
              {t === "archives" ? "数据源" : t === "batches" ? "批量回测" : "组合"}
            </button>
          ))}
        </div>

        {/* Search */}
        <Input
          placeholder={
            tab === "archives"
              ? "搜索 slug..."
              : tab === "batches"
                ? "搜索批次 ID 或策略..."
                : "搜索组合名称..."
          }
          value={search}
          onChange={(e) => {
            setSearch(e.target.value)
            setArchivePage(1)
          }}
        />

        {/* Content area */}
        <ScrollArea className="max-h-80">
          <div className="flex flex-col gap-1 pr-3">
            {/* Archives tab */}
            {tab === "archives" &&
              (filteredArchives.length === 0 ? (
                <div className="py-6 text-center text-sm text-muted-foreground">
                  {archives.length === 0 ? "暂无数据源" : "全部数据源已在组合中或无匹配"}
                </div>
              ) : (
                <>
                  <div className="flex items-center gap-2 pb-1">
                    <label className="flex cursor-pointer items-center gap-2 text-xs text-primary">
                      <Checkbox
                        checked={allFilteredArchivesSelected}
                        onCheckedChange={toggleSelectAllArchives}
                      />
                      {allFilteredArchivesSelected ? "取消全选" : `全选 (${filteredArchives.length})`}
                    </label>
                    <span className="ml-auto text-xs text-muted-foreground">
                      {archivePage} / {archiveTotalPages} 页 · 共 {filteredArchives.length} 条
                    </span>
                  </div>
                  {pagedArchives.map((a) => {
                    const key = `archive:${a.slug}`
                    const checked = selectedItems.has(key)
                    return (
                      <label
                        key={a.slug}
                        className={cn(
                          "flex cursor-pointer items-center gap-2 rounded-md px-3 py-2 text-sm transition-colors",
                          checked ? "bg-primary/5" : "hover:bg-muted",
                        )}
                      >
                        <Checkbox
                          checked={checked}
                          onCheckedChange={() => addArchiveAsPlaceholder(a)}
                        />
                        <span className="flex-1 font-mono text-xs">{a.slug}</span>
                        <span className="text-xs text-muted-foreground">
                          {a.size_mb} MB · {a.prices_count} 价格
                        </span>
                      </label>
                    )
                  })}
                  {archiveTotalPages > 1 && (
                    <div className="flex items-center justify-center gap-2 pt-2">
                      <Button
                        variant="outline"
                        size="sm"
                        disabled={archivePage <= 1}
                        onClick={() => setArchivePage((p) => p - 1)}
                      >
                        上一页
                      </Button>
                      <span className="text-xs text-muted-foreground">
                        {archivePage} / {archiveTotalPages}
                      </span>
                      <Button
                        variant="outline"
                        size="sm"
                        disabled={archivePage >= archiveTotalPages}
                        onClick={() => setArchivePage((p) => p + 1)}
                      >
                        下一页
                      </Button>
                    </div>
                  )}
                </>
              ))}

            {/* Batches tab */}
            {tab === "batches" && !expandedBatchId &&
              (filteredBatchTasks.length === 0 ? (
                <div className="py-6 text-center text-sm text-muted-foreground">
                  暂无已完成的批量回测
                </div>
              ) : (
                filteredBatchTasks.map((t) => (
                  <button
                    key={t.batch_id}
                    onClick={() => setExpandedBatchId(t.batch_id)}
                    className="flex items-center justify-between rounded-md px-3 py-2 text-left text-sm transition-colors hover:bg-muted"
                  >
                    <div>
                      <div className="font-medium">{t.strategy}</div>
                      <div className="font-mono text-[10px] text-muted-foreground">
                        {t.batch_id}
                      </div>
                    </div>
                    <div className="text-right text-xs text-muted-foreground">
                      <div>{t.completed}/{t.total} 完成</div>
                      <div>{fmtDateTimeCst(t.created_at)}</div>
                    </div>
                  </button>
                ))
              ))}

            {tab === "batches" && expandedBatchId && (
              <>
                <div className="flex items-center gap-2 pb-1">
                  <button
                    onClick={() => setExpandedBatchId(null)}
                    className="text-xs text-primary hover:underline"
                  >
                    ← 返回批次列表
                  </button>
                  {batchResults.length > 0 && (
                    <button
                      onClick={selectAllBatchResults}
                      className="ml-auto text-xs text-primary hover:underline"
                    >
                      全选未添加
                    </button>
                  )}
                </div>
                {batchResults.length === 0 ? (
                  <div className="py-6 text-center text-sm text-muted-foreground">
                    该批次中的所有结果已在组合中
                  </div>
                ) : (
                  batchResults.map(([slug, item]) => {
                    const checked = selectedItems.has(item.session_id)
                    return (
                      <label
                        key={item.session_id}
                        className={cn(
                          "flex cursor-pointer items-center gap-2 rounded-md px-3 py-2 text-sm transition-colors",
                          checked ? "bg-primary/5" : "hover:bg-muted",
                        )}
                      >
                        <Checkbox
                          checked={checked}
                          onCheckedChange={() => toggleItem(item)}
                        />
                        <span className="flex-1 font-mono text-xs">{slug}</span>
                        <span
                          className={cn(
                            "font-mono text-xs",
                            item.total_return_pct >= 0
                              ? "text-emerald-600"
                              : "text-red-500",
                          )}
                        >
                          {item.total_return_pct >= 0 ? "+" : ""}
                          {(item.total_return_pct * 100).toFixed(2)}%
                        </span>
                      </label>
                    )
                  })
                )}
              </>
            )}

            {/* Portfolios tab */}
            {tab === "portfolios" &&
              (filteredPortfolios.length === 0 ? (
                <div className="py-6 text-center text-sm text-muted-foreground">
                  暂无其他组合
                </div>
              ) : (
                filteredPortfolios.map((p) => {
                  let newItems = p.items.filter(
                    (it) => !existingSessionIds.has(it.session_id),
                  )
                  if (groupStrategy) {
                    newItems = newItems.filter((it) => it.strategy === groupStrategy)
                  }
                  return (
                    <div
                      key={p.portfolio_id}
                      className="flex items-center justify-between rounded-md px-3 py-2 text-sm transition-colors hover:bg-muted"
                    >
                      <div className="flex-1">
                        <div className="font-medium">{p.name}</div>
                        <div className="text-xs text-muted-foreground">
                          {p.items.length} 条数据源 ·{" "}
                          <span className="text-primary">
                            {newItems.length} 条可新增
                          </span>
                        </div>
                      </div>
                      <Button
                        variant="outline"
                        size="sm"
                        disabled={newItems.length === 0}
                        onClick={() => addPortfolioItems_bulk(newItems)}
                      >
                        添加 ({newItems.length})
                      </Button>
                    </div>
                  )
                })
              ))}
          </div>
        </ScrollArea>

        {/* Footer */}
        <div className="flex items-center justify-between gap-2 border-t pt-3">
          <span className="text-xs text-muted-foreground">
            已选 {selectedItems.size} 条
          </span>
          <div className="flex gap-2">
            <Button variant="outline" size="sm" onClick={handleClose}>
              取消
            </Button>
            <Button
              size="sm"
              disabled={selectedItems.size === 0 || addMutation.isPending}
              onClick={handleConfirm}
            >
              {addMutation.isPending ? "添加中..." : "确认添加"}
            </Button>
          </div>
        </div>

        {addMutation.isError && (
          <div className="text-xs text-red-500">操作失败，请重试</div>
        )}
      </DialogContent>
    </Dialog>
  )
}
