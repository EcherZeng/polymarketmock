import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import { Link } from "react-router-dom"
import { useMemo } from "react"
import { cn } from "@/lib/utils"
import { fetchPortfolios, deletePortfolio } from "@/api/client"
import type { Portfolio } from "@/types"

export default function PortfoliosPage() {
  const queryClient = useQueryClient()

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

  const sorted = useMemo(
    () => [...portfolios].sort((a, b) => b.created_at.localeCompare(a.created_at)),
    [portfolios],
  )

  if (isLoading) {
    return <div className="py-12 text-center text-muted-foreground">加载中...</div>
  }

  if (sorted.length === 0) {
    return (
      <div className="py-20 text-center">
        <h2 className="text-lg font-semibold">暂无数据组合</h2>
        <p className="mt-1 text-sm text-muted-foreground">
          在批量回测详情页中选择成功结果，点击"加入组合"来创建
        </p>
      </div>
    )
  }

  return (
    <div className="flex flex-col gap-6">
      <h1 className="text-2xl font-bold tracking-tight">数据组合</h1>

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
