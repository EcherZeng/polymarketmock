import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import { Link, useNavigate } from "react-router-dom"
import { useMemo, useState } from "react"
import { cn } from "@/lib/utils"
import { fetchPortfolios, deletePortfolio, createPortfolio } from "@/api/client"
import type { Portfolio } from "@/types"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/ui/dialog"

export default function PortfoliosPage() {
  const queryClient = useQueryClient()
  const navigate = useNavigate()
  const [createOpen, setCreateOpen] = useState(false)
  const [newName, setNewName] = useState("")

  const { data: portfolios = [], isLoading } = useQuery<Portfolio[]>({
    queryKey: ["portfolios"],
    queryFn: fetchPortfolios,
  })

  const deleteMutation = useMutation({
    mutationFn: deletePortfolio,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["portfolios"] })
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

  const sorted = useMemo(
    () => [...portfolios].sort((a, b) => b.created_at.localeCompare(a.created_at)),
    [portfolios],
  )

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

  if (sorted.length === 0) {
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

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold tracking-tight">数据组合</h1>
        <Button onClick={() => setCreateOpen(true)}>创建组合</Button>
      </div>

      {createDialog}

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {sorted.map((p) => {
          const returns = p.items.map((it) => it.total_return_pct)
          const avgReturn =
            returns.length > 0
              ? returns.reduce((a, b) => a + b, 0) / returns.length
              : 0
          const positiveCount = returns.filter((r) => r > 0).length

          return (
            <div key={p.portfolio_id} className="rounded-lg border p-4 transition-colors hover:bg-muted/30">
              <div className="flex items-start justify-between">
                <Link to={`/portfolios/${p.portfolio_id}`} className="flex-1">
                  <h3 className="font-semibold">{p.name}</h3>
                  <p className="mt-0.5 text-xs text-muted-foreground">
                    {p.items.length} 条数据源 · 创建于{" "}
                    {p.created_at.replace("T", " ").slice(0, 10)}
                  </p>
                </Link>
                <button
                  onClick={() => {
                    if (confirm(`确定删除组合「${p.name}」？`))
                      deleteMutation.mutate(p.portfolio_id)
                  }}
                  className="text-xs text-muted-foreground transition-colors hover:text-red-500"
                >
                  删除
                </button>
              </div>

              {p.items.length > 0 && (
                <Link to={`/portfolios/${p.portfolio_id}`}>
                  <div className="mt-3 grid grid-cols-3 gap-2">
                    <div>
                      <div className="text-[10px] text-muted-foreground">平均收益</div>
                      <div
                        className={cn(
                          "text-sm font-semibold",
                          avgReturn >= 0 ? "text-emerald-600" : "text-red-500",
                        )}
                      >
                        {avgReturn >= 0 ? "+" : ""}
                        {avgReturn.toFixed(2)}%
                      </div>
                    </div>
                    <div>
                      <div className="text-[10px] text-muted-foreground">盈利占比</div>
                      <div className="text-sm font-semibold">
                        {returns.length > 0
                          ? ((positiveCount / returns.length) * 100).toFixed(0)
                          : 0}
                        %
                      </div>
                    </div>
                    <div>
                      <div className="text-[10px] text-muted-foreground">数据源数</div>
                      <div className="text-sm font-semibold">{p.items.length}</div>
                    </div>
                  </div>
                </Link>
              )}
            </div>
          )
        })}
      </div>
    </div>
  )
}
