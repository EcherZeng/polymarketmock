import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import { useParams, Link } from "react-router-dom"
import { useMemo, useState } from "react"
import { cn } from "@/lib/utils"
import {
  fetchPortfolio,
  renamePortfolio,
  removePortfolioItems,
} from "@/api/client"
import { Checkbox } from "@/components/ui/checkbox"
import { Input } from "@/components/ui/input"
import { Button } from "@/components/ui/button"
import AddItemsToPortfolioDialog from "@/components/AddItemsToPortfolioDialog"
import type { Portfolio } from "@/types"

export default function PortfolioDetailPage() {
  const { portfolioId } = useParams<{ portfolioId: string }>()
  const queryClient = useQueryClient()
  const [editing, setEditing] = useState(false)
  const [editName, setEditName] = useState("")
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set())
  const [memberSearch, setMemberSearch] = useState("")
  const [returnFilter, setReturnFilter] = useState<"all" | "positive" | "negative">("all")
  const [addDialogOpen, setAddDialogOpen] = useState(false)

  const { data: portfolio, isLoading } = useQuery<Portfolio>({
    queryKey: ["portfolio", portfolioId],
    queryFn: () => fetchPortfolio(portfolioId!),
    enabled: !!portfolioId,
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
            <span>{portfolio.items.length} 条数据源</span>
            <span>·</span>
            <span>创建于 {portfolio.created_at.replace("T", " ").slice(0, 19)}</span>
          </div>
        </div>
        <Link
          to="/portfolios"
          className="rounded-md border px-3 py-1.5 text-sm font-medium transition-colors hover:bg-muted"
        >
          返回列表
        </Link>
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
