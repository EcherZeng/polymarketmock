import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import { useParams, Link, useNavigate } from "react-router-dom"
import { useMemo, useState } from "react"
import { cn } from "@/lib/utils"
import {
  fetchPortfolio,
  fetchPortfolios,
  renamePortfolio,
  removePortfolioItems,
  addChildren,
  removeChildren,
  createPortfolio,
} from "@/api/client"
import { Checkbox } from "@/components/ui/checkbox"
import { Input } from "@/components/ui/input"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/ui/dialog"
import AddItemsToPortfolioDialog from "@/components/AddItemsToPortfolioDialog"
import type { Portfolio } from "@/types"

export default function PortfolioDetailPage() {
  const { portfolioId } = useParams<{ portfolioId: string }>()
  const queryClient = useQueryClient()
  const navigate = useNavigate()
  const [editing, setEditing] = useState(false)
  const [editName, setEditName] = useState("")
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set())
  const [memberSearch, setMemberSearch] = useState("")
  const [returnFilter, setReturnFilter] = useState<"all" | "positive" | "negative">("all")
  const [addDialogOpen, setAddDialogOpen] = useState(false)
  const [addChildOpen, setAddChildOpen] = useState(false)
  const [addChildMode, setAddChildMode] = useState<"existing" | "create">("existing")
  const [newChildName, setNewChildName] = useState("")
  const [selectedChildIds, setSelectedChildIds] = useState<Set<string>>(new Set())
  const [selectedGroupIds, setSelectedGroupIds] = useState<Set<string>>(new Set())

  const { data: portfolio, isLoading } = useQuery<Portfolio>({
    queryKey: ["portfolio", portfolioId],
    queryFn: () => fetchPortfolio(portfolioId!),
    enabled: !!portfolioId,
  })

  const { data: allPortfolios = [] } = useQuery<Portfolio[]>({
    queryKey: ["portfolios"],
    queryFn: fetchPortfolios,
  })

  const renameMutation = useMutation({
    mutationFn: (name: string) => renamePortfolio(portfolioId!, name),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["portfolio", portfolioId] })
      queryClient.invalidateQueries({ queryKey: ["portfolios"] })
      setEditing(false)
    },
  })

  const removeMutation = useMutation({
    mutationFn: (sessionIds: string[]) =>
      removePortfolioItems(portfolioId!, sessionIds),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["portfolio", portfolioId] })
      queryClient.invalidateQueries({ queryKey: ["portfolios"] })
      setSelectedIds(new Set())
    },
  })

  const addChildrenMutation = useMutation({
    mutationFn: (children: string[]) => addChildren(portfolioId!, children),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["portfolio", portfolioId] })
      queryClient.invalidateQueries({ queryKey: ["portfolios"] })
      setAddChildOpen(false)
      setSelectedChildIds(new Set())
    },
  })

  const createChildMutation = useMutation({
    mutationFn: async (name: string) => {
      const created = await createPortfolio({ name, items: [] })
      await addChildren(portfolioId!, [created.portfolio_id])
      return created
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["portfolio", portfolioId] })
      queryClient.invalidateQueries({ queryKey: ["portfolios"] })
      setAddChildOpen(false)
      setNewChildName("")
    },
  })

  const removeChildrenMutation = useMutation({
    mutationFn: (children: string[]) => removeChildren(portfolioId!, children),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["portfolio", portfolioId] })
      queryClient.invalidateQueries({ queryKey: ["portfolios"] })
      setSelectedChildIds(new Set())
    },
  })

  // Available portfolios that can be added as children (not self, not ancestors, not already children)
  const availableChildren = useMemo(() => {
    if (!portfolio) return []
    const childSet = new Set(portfolio.children)
    return allPortfolios.filter((p) => {
      if (p.portfolio_id === portfolioId) return false
      if (childSet.has(p.portfolio_id)) return false
      if (p.parent_id && p.parent_id !== portfolioId) return false // already belongs to another parent
      return true
    })
  }, [allPortfolios, portfolio, portfolioId])

  // Resolve children portfolios
  const childPortfolios = useMemo(() => {
    if (!portfolio?.is_container) return []
    const pMap = new Map(allPortfolios.map((p) => [p.portfolio_id, p]))
    return portfolio.children
      .map((cid) => pMap.get(cid))
      .filter((c): c is Portfolio => !!c)
  }, [allPortfolios, portfolio])

  // Strategy groups among children (for comparison entry from within container)
  const childStrategyGroups = useMemo(
    () => childPortfolios.filter((p) => p.is_strategy_group),
    [childPortfolios],
  )

  const stats = useMemo(() => {
    if (!portfolio || portfolio.items.length === 0) return null
    const items = portfolio.items
    const returns = items.map((it) => it.total_return_pct)
    const winCount = returns.filter((r) => r > 0).length
    return {
      count: items.length,
      avgReturn: returns.reduce((a, b) => a + b, 0) / returns.length * 100,
      winRate: (winCount / items.length) * 100,
      bestReturn: Math.max(...returns) * 100,
      worstReturn: Math.min(...returns) * 100,
      avgSharpe:
        items.reduce((a, it) => a + it.sharpe_ratio, 0) / items.length,
      avgDrawdown:
        items.reduce((a, it) => a + it.max_drawdown, 0) / items.length * 100,
      totalTrades: items.reduce((a, it) => a + it.total_trades, 0),
    }
  }, [portfolio])

  const filteredItems = useMemo(() => {
    if (!portfolio) return []
    let items = portfolio.items
    if (returnFilter === "positive") {
      items = items.filter((it) => it.total_return_pct > 0)
    } else if (returnFilter === "negative") {
      items = items.filter((it) => it.total_return_pct < 0)
    }
    if (memberSearch.trim()) {
      const term = memberSearch.trim().toLowerCase()
      items = items.filter(
        (it) =>
          it.slug.toLowerCase().includes(term) ||
          it.strategy.toLowerCase().includes(term),
      )
    }
    return items
  }, [portfolio, returnFilter, memberSearch])

  const existingSessionIds = useMemo(
    () => new Set(portfolio?.items.map((it) => it.session_id) ?? []),
    [portfolio],
  )

  const existingSlugs = useMemo(
    () => new Set(portfolio?.items.map((it) => it.slug) ?? []),
    [portfolio],
  )

  const toggleSelect = (sessionId: string) => {
    setSelectedIds((prev) => {
      const next = new Set(prev)
      if (next.has(sessionId)) next.delete(sessionId)
      else next.add(sessionId)
      return next
    })
  }

  const toggleSelectAll = () => {
    const visibleIds = filteredItems.map((it) => it.session_id)
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

  if (isLoading || !portfolio) {
    return <div className="py-12 text-center text-muted-foreground">加载中...</div>
  }

  return (
    <div className="flex flex-col gap-6">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          {editing ? (
            <div className="flex items-center gap-2">
              <Input
                value={editName}
                onChange={(e) => setEditName(e.target.value)}
                className="h-9 w-64"
                autoFocus
                maxLength={100}
              />
              <Button
                size="sm"
                disabled={!editName.trim() || renameMutation.isPending}
                onClick={() => renameMutation.mutate(editName.trim())}
              >
                保存
              </Button>
              <Button
                variant="outline"
                size="sm"
                onClick={() => setEditing(false)}
              >
                取消
              </Button>
            </div>
          ) : (
            <div className="flex items-center gap-3">
              <h1 className="text-2xl font-bold tracking-tight">
                {portfolio.name}
              </h1>
              <button
                onClick={() => {
                  setEditName(portfolio.name)
                  setEditing(true)
                }}
                className="text-xs text-muted-foreground hover:text-foreground"
              >
                编辑
              </button>
            </div>
          )}
          <div className="mt-1 flex gap-3 text-sm text-muted-foreground">
            <span>
              {portfolio.is_container
                ? `${portfolio.children.length} 个子组合`
                : `${portfolio.items.length} 条数据源`}
            </span>
            <span>·</span>
            <span>创建于 {portfolio.created_at.replace("T", " ").slice(0, 19)}</span>
            {portfolio.is_container && (
              <>
                <span>·</span>
                <Badge variant="outline" className="text-[10px]">容器</Badge>
              </>
            )}
          </div>
        </div>
        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            size="sm"
            disabled={portfolio.items.length > 0}
            onClick={() => {
              setAddChildMode("existing")
              setAddChildOpen(true)
            }}
            title={portfolio.items.length > 0 ? "组合已有数据源，不可新增子组合" : undefined}
          >
            新增组合
          </Button>
          <Button
            variant="outline"
            size="sm"
            disabled={portfolio.is_container}
            onClick={() => setAddDialogOpen(true)}
            title={portfolio.is_container ? "容器组合不可直接添加数据源" : undefined}
          >
            新增数据源
          </Button>
          <Link
            to="/portfolios"
            className="rounded-md border px-3 py-1.5 text-sm font-medium transition-colors hover:bg-muted"
          >
            返回列表
          </Link>
        </div>
      </div>

      {/* Strategy group header */}
      {portfolio.is_strategy_group && portfolio.group_strategy && portfolio.group_config && (
        <div className="rounded-lg border bg-muted/30 p-4">
          <div className="flex items-center gap-2">
            <span className="rounded-full bg-primary/10 px-2.5 py-0.5 text-xs font-medium text-primary">
              策略组
            </span>
            <span className="text-sm font-semibold">{portfolio.group_strategy}</span>
          </div>
          <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1">
            {Object.entries(portfolio.group_config).map(([key, val]) => (
              <div key={key} className="text-xs">
                <span className="text-muted-foreground">{key}:</span>{" "}
                <span className="font-mono">{String(val)}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* ── Container children section ──────────────────────────────────── */}
      {portfolio.is_container && (
        <>
          {/* Comparison bar for strategy groups within this container */}
          {childStrategyGroups.length >= 2 && (
            <div className="rounded-lg border bg-muted/30 p-4">
              <div className="text-sm font-medium">子策略组对照</div>
              <p className="mt-0.5 text-xs text-muted-foreground">
                此容器包含 {childStrategyGroups.length} 个策略组，可勾选进行参数对照
              </p>
              <div className="mt-2 flex flex-wrap gap-2">
                {childStrategyGroups.map((sg) => (
                  <label key={sg.portfolio_id} className="flex items-center gap-1.5">
                    <Checkbox
                      checked={selectedGroupIds.has(sg.portfolio_id)}
                      onCheckedChange={() => {
                        setSelectedGroupIds((prev) => {
                          const next = new Set(prev)
                          if (next.has(sg.portfolio_id)) next.delete(sg.portfolio_id)
                          else next.add(sg.portfolio_id)
                          return next
                        })
                      }}
                    />
                    <span className="text-xs">{sg.name}</span>
                    <Badge variant="secondary" className="text-[10px]">
                      {sg.group_strategy}
                    </Badge>
                  </label>
                ))}
              </div>
              {selectedGroupIds.size >= 2 && (
                <Button
                  size="sm"
                  className="mt-2"
                  onClick={() => {
                    const ids = [...selectedGroupIds].join(",")
                    navigate(`/comparison?ids=${ids}`)
                  }}
                >
                  参数对照 ({selectedGroupIds.size})
                </Button>
              )}
            </div>
          )}

          {/* Children list */}
          <div className="rounded-lg border">
            <div className="flex items-center justify-between border-b bg-muted/50 px-4 py-2">
              <h2 className="text-sm font-medium">子组合 ({portfolio.children.length})</h2>
              <div className="flex items-center gap-2">
                {selectedChildIds.size > 0 && (
                  <>
                    <span className="text-xs text-muted-foreground">
                      已选 {selectedChildIds.size}
                    </span>
                    <button
                      onClick={() => {
                        if (confirm(`确认从容器中移除 ${selectedChildIds.size} 个子组合？子组合不会被删除，将提升为顶层组合。`))
                          removeChildrenMutation.mutate([...selectedChildIds])
                      }}
                      disabled={removeChildrenMutation.isPending}
                      className="rounded-md border px-2.5 py-1 text-xs font-medium text-red-600 transition-colors hover:bg-red-50"
                    >
                      移除选中
                    </button>
                  </>
                )}
                <button
                  onClick={() => {
                    setAddChildMode("existing")
                    setAddChildOpen(true)
                  }}
                  className="rounded-md bg-primary px-3 py-1 text-xs font-medium text-primary-foreground transition-colors hover:bg-primary/90"
                >
                  添加子组合
                </button>
              </div>
            </div>
            {childPortfolios.length > 0 ? (
              <div className="divide-y">
                {childPortfolios.map((child) => {
                  const returns = child.items.map((it) => it.total_return_pct)
                  const avg = returns.length > 0 ? returns.reduce((a, b) => a + b, 0) / returns.length : 0
                  return (
                    <div
                      key={child.portfolio_id}
                      className={cn(
                        "flex items-center gap-3 px-4 py-3 transition-colors hover:bg-muted/30",
                        selectedChildIds.has(child.portfolio_id) && "bg-primary/5",
                      )}
                    >
                      <Checkbox
                        checked={selectedChildIds.has(child.portfolio_id)}
                        onCheckedChange={() => {
                          setSelectedChildIds((prev) => {
                            const next = new Set(prev)
                            if (next.has(child.portfolio_id)) next.delete(child.portfolio_id)
                            else next.add(child.portfolio_id)
                            return next
                          })
                        }}
                      />
                      <Link
                        to={`/portfolios/${child.portfolio_id}`}
                        className="flex flex-1 items-center justify-between"
                      >
                        <div>
                          <div className="flex items-center gap-2">
                            <span className="text-sm font-medium">{child.name}</span>
                            {child.is_strategy_group && (
                              <Badge variant="secondary" className="text-[10px]">
                                策略组 · {child.group_strategy}
                              </Badge>
                            )}
                            {child.is_container && (
                              <Badge variant="outline" className="text-[10px]">
                                容器 · {child.children.length} 子
                              </Badge>
                            )}
                          </div>
                          <div className="text-xs text-muted-foreground">
                            {child.is_container
                              ? `${child.children.length} 个子组合`
                              : `${child.items.length} 条数据源`}
                          </div>
                        </div>
                        {!child.is_container && child.items.length > 0 && (
                          <div className="text-right">
                            <div
                              className={cn(
                                "text-sm font-mono font-semibold",
                                avg >= 0 ? "text-emerald-600" : "text-red-500",
                              )}
                            >
                              {avg >= 0 ? "+" : ""}
                              {(avg * 100).toFixed(2)}%
                            </div>
                            <div className="text-[10px] text-muted-foreground">平均收益</div>
                          </div>
                        )}
                      </Link>
                    </div>
                  )
                })}
              </div>
            ) : (
              <div className="py-8 text-center text-sm text-muted-foreground">
                暂无子组合，点击顶部"新增组合"按钮添加
              </div>
            )}
          </div>
        </>
      )}

      {/* Add child dialog (available for any portfolio without items) */}
      <Dialog open={addChildOpen} onOpenChange={setAddChildOpen}>
        <DialogContent className="max-h-[80vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>新增组合</DialogTitle>
          </DialogHeader>

          {/* Mode toggle */}
          <div className="flex items-center gap-2">
            {(["existing", "create"] as const).map((mode) => (
              <button
                key={mode}
                onClick={() => setAddChildMode(mode)}
                className={cn(
                  "rounded-md px-3 py-1.5 text-sm font-medium transition-colors",
                  addChildMode === mode
                    ? "bg-foreground text-background"
                    : "bg-muted text-muted-foreground hover:bg-muted/80",
                )}
              >
                {mode === "existing" ? "选择现有组合" : "创建新组合"}
              </button>
            ))}
          </div>

          {addChildMode === "existing" ? (
            <>
              {availableChildren.length === 0 ? (
                <p className="py-4 text-center text-sm text-muted-foreground">
                  没有可添加的组合。组合需要是顶层组合（无父组合）才能被添加。
                </p>
              ) : (
                <div className="space-y-2">
                  {availableChildren.map((p) => (
                    <label
                      key={p.portfolio_id}
                      className={cn(
                        "flex cursor-pointer items-center gap-3 rounded-md border p-3 transition-colors hover:bg-muted/30",
                        selectedChildIds.has(p.portfolio_id) && "ring-2 ring-primary/50",
                      )}
                    >
                      <Checkbox
                        checked={selectedChildIds.has(p.portfolio_id)}
                        onCheckedChange={() => {
                          setSelectedChildIds((prev) => {
                            const next = new Set(prev)
                            if (next.has(p.portfolio_id)) next.delete(p.portfolio_id)
                            else next.add(p.portfolio_id)
                            return next
                          })
                        }}
                      />
                      <div className="flex-1">
                        <div className="flex items-center gap-2">
                          <span className="text-sm font-medium">{p.name}</span>
                          {p.is_strategy_group && (
                            <Badge variant="secondary" className="text-[10px]">
                              策略组
                            </Badge>
                          )}
                          {p.is_container && (
                            <Badge variant="outline" className="text-[10px]">容器</Badge>
                          )}
                        </div>
                        <div className="text-xs text-muted-foreground">
                          {p.is_container
                            ? `${p.children.length} 个子组合`
                            : `${p.items.length} 条数据源`}
                        </div>
                      </div>
                    </label>
                  ))}
                </div>
              )}
              <DialogFooter>
                <Button variant="outline" onClick={() => { setAddChildOpen(false); setSelectedChildIds(new Set()) }}>
                  取消
                </Button>
                <Button
                  disabled={selectedChildIds.size === 0 || addChildrenMutation.isPending}
                  onClick={() => addChildrenMutation.mutate([...selectedChildIds])}
                >
                  {addChildrenMutation.isPending ? "添加中..." : `添加 (${selectedChildIds.size})`}
                </Button>
              </DialogFooter>
            </>
          ) : (
            <>
              <Input
                placeholder="输入新组合名称"
                value={newChildName}
                onChange={(e) => setNewChildName(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" && newChildName.trim()) {
                    createChildMutation.mutate(newChildName.trim())
                  }
                }}
              />
              <DialogFooter>
                <Button variant="outline" onClick={() => { setAddChildOpen(false); setNewChildName("") }}>
                  取消
                </Button>
                <Button
                  disabled={!newChildName.trim() || createChildMutation.isPending}
                  onClick={() => createChildMutation.mutate(newChildName.trim())}
                >
                  {createChildMutation.isPending ? "创建中..." : "创建并添加"}
                </Button>
              </DialogFooter>
            </>
          )}
        </DialogContent>
      </Dialog>

      {/* ── Leaf portfolio content (stats + items) ─────────────────────── */}
      {!portfolio.is_container && (
      <>
      {/* Aggregate stats */}
      {stats && (
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4 lg:grid-cols-8">
          <StatCard label="数据源数" value={`${stats.count}`} />
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
          <StatCard label="平均回撤" value={`${stats.avgDrawdown.toFixed(2)}%`} />
          <StatCard label="总交易数" value={`${stats.totalTrades}`} />
        </div>
      )}

      {/* Items table */}
      {portfolio.items.length > 0 ? (
        <div className="rounded-lg border">
          <div className="flex flex-col gap-2 border-b bg-muted/50 px-4 py-2">
            <div className="flex items-center justify-between">
              <h2 className="text-sm font-medium">成员列表</h2>
              <div className="flex items-center gap-2">
                {selectedIds.size > 0 && (
                  <>
                    <span className="text-xs text-muted-foreground">
                      已选 {selectedIds.size} 条
                    </span>
                    <button
                      onClick={() => {
                        if (confirm(`确认从组合中移除 ${selectedIds.size} 条数据源？`))
                          removeMutation.mutate([...selectedIds])
                      }}
                      disabled={removeMutation.isPending}
                      className="rounded-md border px-2.5 py-1 text-xs font-medium text-red-600 transition-colors hover:bg-red-50"
                    >
                      移除选中
                    </button>
                  </>
                )}
                <button
                  onClick={() => setAddDialogOpen(true)}
                  className="rounded-md bg-primary px-3 py-1 text-xs font-medium text-primary-foreground transition-colors hover:bg-primary/90"
                >
                  新增
                </button>
              </div>
            </div>
            {/* Search + filter row */}
            <div className="flex items-center gap-2">
              <input
                type="text"
                placeholder="搜索 slug 或策略..."
                value={memberSearch}
                onChange={(e) => setMemberSearch(e.target.value)}
                className="h-7 w-48 rounded-md border bg-background px-2 text-xs"
              />
              {(["all", "positive", "negative"] as const).map((f) => (
                <button
                  key={f}
                  onClick={() => setReturnFilter(f)}
                  className={cn(
                    "rounded-md px-2 py-1 text-xs font-medium transition-colors",
                    returnFilter === f
                      ? "bg-foreground text-background"
                      : "bg-muted text-muted-foreground hover:bg-muted/80",
                  )}
                >
                  {f === "all" ? "全部" : f === "positive" ? "收益增加" : "收益减少"}
                </button>
              ))}
              <span className="text-xs text-muted-foreground">
                {filteredItems.length} / {portfolio.items.length} 条
              </span>
            </div>
          </div>
          <div className="overflow-auto">
            <table className="w-full text-sm">
              <thead className="bg-muted/30">
                <tr className="border-b text-left text-xs text-muted-foreground">
                  <th className="px-3 py-2">
                    <Checkbox
                      checked={
                        filteredItems.length > 0 &&
                        filteredItems.every((it) => selectedIds.has(it.session_id))
                      }
                      onCheckedChange={toggleSelectAll}
                    />
                  </th>
                  <th className="px-3 py-2">数据源</th>
                  <th className="px-3 py-2">策略</th>
                  <th className="px-3 py-2 text-right">收益率</th>
                  <th className="px-3 py-2 text-right">Sharpe</th>
                  <th className="px-3 py-2 text-right">胜率</th>
                  <th className="px-3 py-2 text-right">最大回撤</th>
                  <th className="px-3 py-2 text-right">盈亏比</th>
                  <th className="px-3 py-2 text-right">交易数</th>
                  <th className="px-3 py-2"></th>
                </tr>
              </thead>
              <tbody>
                {filteredItems.map((it) => (
                  <tr
                    key={it.session_id}
                    className={cn(
                      "border-b transition-colors hover:bg-muted/30",
                      selectedIds.has(it.session_id) && "bg-primary/5",
                    )}
                  >
                    <td className="px-3 py-2">
                      <Checkbox
                        checked={selectedIds.has(it.session_id)}
                        onCheckedChange={() => toggleSelect(it.session_id)}
                      />
                    </td>
                    <td className="px-3 py-2 font-mono text-xs">{it.slug}</td>
                    <td className="px-3 py-2 text-xs">{it.strategy}</td>
                    <td
                      className={cn(
                        "px-3 py-2 text-right font-mono",
                        it.total_return_pct >= 0 ? "text-emerald-600" : "text-red-500",
                      )}
                    >
                      {it.total_return_pct >= 0 ? "+" : ""}
                      {(it.total_return_pct * 100).toFixed(2)}%
                    </td>
                    <td className="px-3 py-2 text-right font-mono">
                      {it.sharpe_ratio.toFixed(4)}
                    </td>
                    <td className="px-3 py-2 text-right font-mono">
                      {(it.win_rate * 100).toFixed(1)}%
                    </td>
                    <td className="px-3 py-2 text-right font-mono text-red-500">
                      {(it.max_drawdown * 100).toFixed(2)}%
                    </td>
                    <td className="px-3 py-2 text-right font-mono">
                      {it.profit_factor === Infinity
                        ? "∞"
                        : it.profit_factor.toFixed(2)}
                    </td>
                    <td className="px-3 py-2 text-right font-mono">
                      {it.total_trades}
                    </td>
                    <td className="px-3 py-2 text-right">
                      <Link
                        to={`/results/${it.session_id}`}
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
      ) : (
        <div className="flex flex-col items-center gap-3 py-12">
          <div className="text-sm text-muted-foreground">组合为空</div>
          <button
            onClick={() => setAddDialogOpen(true)}
            className="rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/90"
          >
            新增数据源
          </button>
        </div>
      )}

      <AddItemsToPortfolioDialog
        open={addDialogOpen}
        onOpenChange={setAddDialogOpen}
        portfolioId={portfolioId!}
        existingSessionIds={existingSessionIds}
        existingSlugs={existingSlugs}
        groupStrategy={portfolio?.is_strategy_group ? (portfolio.group_strategy ?? undefined) : undefined}
      />
      </>
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
