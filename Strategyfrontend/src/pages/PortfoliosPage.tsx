import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import { Link, useNavigate } from "react-router-dom"
import { useMemo, useState } from "react"
import { cn } from "@/lib/utils"
import {
  fetchPortfolios,
  fetchStrategyGroups,
  deletePortfolio,
  createPortfolio,
} from "@/api/client"
import type { Portfolio } from "@/types"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Checkbox } from "@/components/ui/checkbox"
import { Badge } from "@/components/ui/badge"
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/ui/dialog"

type ViewMode = "tree" | "strategy-groups"

export default function PortfoliosPage() {
  const queryClient = useQueryClient()
  const navigate = useNavigate()
  const [createOpen, setCreateOpen] = useState(false)
  const [newName, setNewName] = useState("")
  const [selectedGroupIds, setSelectedGroupIds] = useState<Set<string>>(new Set())
  const [expandedIds, setExpandedIds] = useState<Set<string>>(new Set())
  const [viewMode, setViewMode] = useState<ViewMode>("tree")

  const { data: portfolios = [], isLoading } = useQuery<Portfolio[]>({
    queryKey: ["portfolios"],
    queryFn: fetchPortfolios,
  })

  const { data: strategyGroups = [], isLoading: sgLoading } = useQuery<Portfolio[]>({
    queryKey: ["strategy-groups"],
    queryFn: fetchStrategyGroups,
    enabled: viewMode === "strategy-groups",
  })

  const deleteMutation = useMutation({
    mutationFn: deletePortfolio,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["portfolios"] })
      queryClient.invalidateQueries({ queryKey: ["strategy-groups"] })
    },
  })

  const createMutation = useMutation({
    mutationFn: createPortfolio,
    onSuccess: (created) => {
      queryClient.invalidateQueries({ queryKey: ["portfolios"] })
      setCreateOpen(false)
      setNewName("")
      navigate(`/portfolios/${created.portfolio_id}`)
    },
  })

  // Build lookup and top-level list
  const portfolioMap = useMemo(() => {
    const m = new Map<string, Portfolio>()
    for (const p of portfolios) m.set(p.portfolio_id, p)
    return m
  }, [portfolios])

  const topLevel = useMemo(
    () =>
      [...portfolios]
        .filter((p) => !p.parent_id)
        .sort((a, b) => b.created_at.localeCompare(a.created_at)),
    [portfolios],
  )

  const toggleExpand = (id: string) => {
    setExpandedIds((prev) => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  const toggleGroupSelect = (portfolioId: string) => {
    setSelectedGroupIds((prev) => {
      const next = new Set(prev)
      if (next.has(portfolioId)) next.delete(portfolioId)
      else next.add(portfolioId)
      return next
    })
  }

  const handleCompare = () => {
    const ids = [...selectedGroupIds].join(",")
    navigate(`/comparison?ids=${ids}`)
  }

  if (isLoading) {
    return <div className="py-12 text-center text-muted-foreground">加载中...</div>
  }

  const createDialog = (
    <Dialog open={createOpen} onOpenChange={setCreateOpen}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>创建数据组合</DialogTitle>
        </DialogHeader>
        <Input
          placeholder="输入组合名称"
          value={newName}
          onChange={(e) => setNewName(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && newName.trim()) {
              createMutation.mutate({ name: newName.trim(), items: [] })
            }
          }}
        />
        <DialogFooter>
          <Button variant="outline" onClick={() => setCreateOpen(false)}>
            取消
          </Button>
          <Button
            disabled={!newName.trim() || createMutation.isPending}
            onClick={() => createMutation.mutate({ name: newName.trim(), items: [] })}
          >
            {createMutation.isPending ? "创建中..." : "创建"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )

  if (portfolios.length === 0) {
    return (
      <div className="py-20 text-center">
        <h2 className="text-lg font-semibold">暂无数据组合</h2>
        <p className="mt-1 text-sm text-muted-foreground">
          点击下方按钮创建新的数据组合，或在批量回测详情页中选择成功结果加入组合
        </p>
        <Button className="mt-4" onClick={() => setCreateOpen(true)}>
          创建组合
        </Button>
        {createDialog}
      </div>
    )
  }

  // Render a single portfolio row
  function renderRow(p: Portfolio, depth: number) {
    const isContainer = p.is_container
    const isGroup = p.is_strategy_group
    const isChecked = selectedGroupIds.has(p.portfolio_id)
    const isExpanded = expandedIds.has(p.portfolio_id)
    const childPortfolios = p.children
      .map((cid) => portfolioMap.get(cid))
      .filter((c): c is Portfolio => !!c)

    const returns = p.items.map((it) => it.total_return_pct)
    const avgReturn =
      returns.length > 0
        ? returns.reduce((a, b) => a + b, 0) / returns.length
        : 0
    const positiveCount = returns.filter((r) => r > 0).length

    return (
      <div key={p.portfolio_id}>
        <div
          className={cn(
            "flex items-center gap-3 rounded-lg border px-4 py-3 transition-colors hover:bg-muted/30",
            isChecked && "ring-2 ring-primary/50",
          )}
        >
          {/* Left: expand / checkbox */}
          <div className="flex items-center gap-2 shrink-0">
            {isContainer ? (
              <button
                onClick={() => toggleExpand(p.portfolio_id)}
                className="text-muted-foreground transition-transform hover:text-foreground"
              >
                <svg
                  className={cn(
                    "h-4 w-4 transition-transform",
                    isExpanded && "rotate-90",
                  )}
                  fill="none"
                  viewBox="0 0 24 24"
                  stroke="currentColor"
                  strokeWidth={2}
                >
                  <path strokeLinecap="round" strokeLinejoin="round" d="M9 5l7 7-7 7" />
                </svg>
              </button>
            ) : (
              <div className="w-4" />
            )}
            {isGroup && (
              <Checkbox
                checked={isChecked}
                onCheckedChange={() => toggleGroupSelect(p.portfolio_id)}
              />
            )}
          </div>

          {/* Middle: name + badges + meta */}
          <Link to={`/portfolios/${p.portfolio_id}`} className="flex-1 min-w-0">
            <div className="flex items-center gap-2">
              <h3 className="font-semibold truncate">{p.name}</h3>
              {isContainer && (
                <Badge variant="outline" className="text-[10px] shrink-0">
                  容器 · {p.children.length} 子组合
                </Badge>
              )}
              {isGroup && (
                <Badge variant="secondary" className="text-[10px] shrink-0">
                  策略组 · {p.group_strategy}
                </Badge>
              )}
              {p.parent_id && (
                <Badge variant="outline" className="text-[10px] text-muted-foreground shrink-0">
                  子组合
                </Badge>
              )}
            </div>
            <p className="mt-0.5 text-xs text-muted-foreground truncate">
              {isContainer
                ? `${p.children.length} 个子组合`
                : `${p.items.length} 条数据源`}
              {" · "}创建于 {p.created_at.replace("T", " ").slice(0, 10)}
            </p>
          </Link>

          {/* Right: stats (leaf only) */}
          {!isContainer && (
            <div className="hidden sm:flex items-center gap-6 shrink-0 text-right">
              <div>
                <div className="text-[10px] text-muted-foreground">平均收益</div>
                <div
                  className={cn(
                    "text-sm font-semibold font-mono",
                    p.items.length === 0
                      ? "text-muted-foreground"
                      : avgReturn >= 0 ? "text-emerald-600" : "text-red-500",
                  )}
                >
                  {p.items.length === 0 ? "—" : `${avgReturn >= 0 ? "+" : ""}${(avgReturn * 100).toFixed(2)}%`}
                </div>
              </div>
              <div>
                <div className="text-[10px] text-muted-foreground">盈利占比</div>
                <div className="text-sm font-semibold font-mono">
                  {p.items.length === 0
                    ? "—"
                    : `${returns.length > 0
                        ? ((positiveCount / returns.length) * 100).toFixed(0)
                        : 0}%`}
                </div>
              </div>
              <div>
                <div className="text-[10px] text-muted-foreground">数据源</div>
                <div className="text-sm font-semibold font-mono">{p.items.length}</div>
              </div>
            </div>
          )}

          {/* Delete */}
          <button
            onClick={() => {
              if (confirm(`确定删除组合「${p.name}」？${isContainer ? "子组合将提升为顶层组合。" : ""}`))
                deleteMutation.mutate(p.portfolio_id)
            }}
            className="text-xs text-muted-foreground transition-colors hover:text-red-500 shrink-0"
          >
            删除
          </button>
        </div>

        {/* Expanded children */}
        {isContainer && isExpanded && (
          <div className="mt-1 space-y-1 border-l-2 border-l-primary/20 pl-4 ml-4">
            {childPortfolios.length > 0 ? (
              childPortfolios.map((child) => renderRow(child, depth + 1))
            ) : (
              <div className="py-2 text-xs text-muted-foreground">
                暂无子组合，进入详情页添加
              </div>
            )}
          </div>
        )}
      </div>
    )
  }

  // Strategy groups flat view
  const renderStrategyGroupsView = () => {
    if (sgLoading) {
      return <div className="py-8 text-center text-muted-foreground">加载中...</div>
    }
    if (strategyGroups.length === 0) {
      return (
        <div className="py-8 text-center text-muted-foreground">
          暂无策略组。当组合中所有数据源使用同一策略和配置时，将自动标记为策略组。
        </div>
      )
    }
    return (
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {strategyGroups.map((p) => {
          const isChecked = selectedGroupIds.has(p.portfolio_id)
          const returns = p.items.map((it) => it.total_return_pct)
          const avgReturn =
            returns.length > 0
              ? returns.reduce((a, b) => a + b, 0) / returns.length
              : 0
          return (
            <div
              key={p.portfolio_id}
              className={cn(
                "rounded-lg border p-4 transition-colors hover:bg-muted/30",
                isChecked && "ring-2 ring-primary/50",
              )}
            >
              <div className="flex items-start gap-2">
                <Checkbox
                  checked={isChecked}
                  onCheckedChange={() => toggleGroupSelect(p.portfolio_id)}
                  className="mt-1"
                />
                <Link to={`/portfolios/${p.portfolio_id}`} className="flex-1">
                  <div className="flex items-center gap-2">
                    <h3 className="font-semibold">{p.name}</h3>
                    <Badge variant="secondary" className="text-[10px]">
                      {p.group_strategy}
                    </Badge>
                  </div>
                  <p className="mt-0.5 text-xs text-muted-foreground">
                    {p.items.length} 条数据源 · 均值{" "}
                    <span
                      className={cn(
                        "font-semibold",
                        avgReturn >= 0 ? "text-emerald-600" : "text-red-500",
                      )}
                    >
                      {avgReturn >= 0 ? "+" : ""}
                      {(avgReturn * 100).toFixed(2)}%
                    </span>
                    {p.parent_id && " · 嵌套于父组合"}
                  </p>
                </Link>
              </div>
            </div>
          )
        })}
      </div>
    )
  }

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold tracking-tight">数据组合</h1>
        <Button onClick={() => setCreateOpen(true)}>创建组合</Button>
      </div>

      {createDialog}

      {/* View mode toggle */}
      <div className="flex items-center gap-2">
        {(["tree", "strategy-groups"] as const).map((mode) => (
          <button
            key={mode}
            onClick={() => {
              setViewMode(mode)
              setSelectedGroupIds(new Set())
            }}
            className={cn(
              "rounded-md px-3 py-1.5 text-sm font-medium transition-colors",
              viewMode === mode
                ? "bg-foreground text-background"
                : "bg-muted text-muted-foreground hover:bg-muted/80",
            )}
          >
            {mode === "tree" ? "组合树" : "全部策略组"}
          </button>
        ))}
      </div>

      {/* Comparison action bar */}
      {selectedGroupIds.size > 0 && (
        <div className="flex items-center gap-3 rounded-lg border bg-muted/50 px-4 py-2">
          <span className="text-sm text-muted-foreground">
            已选 {selectedGroupIds.size} 个策略组
          </span>
          <Button
            size="sm"
            disabled={selectedGroupIds.size < 2}
            onClick={handleCompare}
          >
            参数对照
          </Button>
          <Button
            variant="outline"
            size="sm"
            onClick={() => setSelectedGroupIds(new Set())}
          >
            取消选择
          </Button>
        </div>
      )}

      {viewMode === "tree" ? (
        <div className="space-y-2">
          {topLevel.map((p) => renderRow(p, 0))}
        </div>
      ) : (
        renderStrategyGroupsView()
      )}
    </div>
  )
}
