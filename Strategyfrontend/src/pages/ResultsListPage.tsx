import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import { Link } from "react-router-dom"
import { cn } from "@/lib/utils"
import { fetchResults, deleteResult, clearResults } from "@/api/client"
import type { BacktestResultSummary } from "@/types"
import { useState, useMemo } from "react"

export default function ResultsListPage() {
  const queryClient = useQueryClient()
  const [sortField, setSortField] = useState<string>("created_at")
  const [sortDir, setSortDir] = useState<"asc" | "desc">("desc")
  const [confirmClear, setConfirmClear] = useState(false)

  const { data: results = [], isLoading } = useQuery<BacktestResultSummary[]>({
    queryKey: ["results"],
    queryFn: fetchResults,
  })

  const deleteMut = useMutation({
    mutationFn: deleteResult,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["results"] }),
  })

  const clearMut = useMutation({
    mutationFn: clearResults,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["results"] })
      setConfirmClear(false)
    },
  })

  const sorted = useMemo(() => {
    const list = [...results]
    list.sort((a, b) => {
      let va: number | string = 0
      let vb: number | string = 0
      if (sortField === "created_at") { va = a.created_at; vb = b.created_at }
      else if (sortField === "return") { va = a.metrics.total_return_pct; vb = b.metrics.total_return_pct }
      else if (sortField === "sharpe") { va = a.metrics.sharpe_ratio; vb = b.metrics.sharpe_ratio }
      else if (sortField === "trades") { va = a.metrics.total_trades; vb = b.metrics.total_trades }
      else if (sortField === "win_rate") { va = a.metrics.win_rate; vb = b.metrics.win_rate }
      if (va < vb) return sortDir === "asc" ? -1 : 1
      if (va > vb) return sortDir === "asc" ? 1 : -1
      return 0
    })
    return list
  }, [results, sortField, sortDir])

  function toggleSort(field: string) {
    if (sortField === field) {
      setSortDir(sortDir === "asc" ? "desc" : "asc")
    } else {
      setSortField(field)
      setSortDir("desc")
    }
  }

  function fmtPct(v: number) {
    const pct = v * 100
    return `${pct >= 0 ? "+" : ""}${pct.toFixed(2)}%`
  }

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">回测结果</h1>
          <p className="text-sm text-muted-foreground">{results.length} 条记录</p>
        </div>
        {results.length > 0 && (
          <div>
            {confirmClear ? (
              <div className="flex items-center gap-2">
                <span className="text-sm text-muted-foreground">确认清空?</span>
                <button
                  onClick={() => clearMut.mutate()}
                  className="h-8 rounded-md bg-destructive px-3 text-sm text-white"
                >
                  确认
                </button>
                <button
                  onClick={() => setConfirmClear(false)}
                  className="h-8 rounded-md border px-3 text-sm"
                >
                  取消
                </button>
              </div>
            ) : (
              <button
                onClick={() => setConfirmClear(true)}
                className="h-8 rounded-md border px-3 text-sm text-muted-foreground hover:text-foreground"
              >
                清空全部
              </button>
            )}
          </div>
        )}
      </div>

      {isLoading ? (
        <div className="py-12 text-center text-muted-foreground">加载中...</div>
      ) : results.length === 0 ? (
        <div className="py-12 text-center text-muted-foreground">
          暂无回测结果。
          <Link to="/" className="ml-1 underline hover:text-foreground">去运行回测</Link>
        </div>
      ) : (
        <div className="overflow-x-auto rounded-lg border">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b bg-muted/50">
                <Th>策略</Th>
                <Th>数据源</Th>
                <ThSort field="return" current={sortField} dir={sortDir} onClick={toggleSort}>
                  收益率
                </ThSort>
                <ThSort field="sharpe" current={sortField} dir={sortDir} onClick={toggleSort}>
                  Sharpe
                </ThSort>
                <ThSort field="win_rate" current={sortField} dir={sortDir} onClick={toggleSort}>
                  胜率
                </ThSort>
                <ThSort field="trades" current={sortField} dir={sortDir} onClick={toggleSort}>
                  交易数
                </ThSort>
                <Th>最大回撤</Th>
                <ThSort field="created_at" current={sortField} dir={sortDir} onClick={toggleSort}>
                  时间
                </ThSort>
                <Th />
              </tr>
            </thead>
            <tbody>
              {sorted.map((r) => (
                <tr key={r.session_id} className="border-b hover:bg-muted/30">
                  <td className="px-3 py-2 font-medium">{r.strategy}</td>
                  <td className="px-3 py-2 font-mono text-xs">{r.slug}</td>
                  <td className={cn("px-3 py-2 font-medium", r.metrics.total_return_pct >= 0 ? "text-emerald-600" : "text-red-500")}>
                    {fmtPct(r.metrics.total_return_pct)}
                  </td>
                  <td className="px-3 py-2">{r.metrics.sharpe_ratio.toFixed(2)}</td>
                  <td className="px-3 py-2">{(r.metrics.win_rate * 100).toFixed(1)}%</td>
                  <td className="px-3 py-2">{r.metrics.total_trades}</td>
                  <td className="px-3 py-2">{(r.metrics.max_drawdown * 100).toFixed(2)}%</td>
                  <td className="px-3 py-2 text-xs text-muted-foreground">
                    {r.created_at.slice(0, 19).replace("T", " ")}
                  </td>
                  <td className="px-3 py-2">
                    <div className="flex items-center gap-2">
                      <Link
                        to={`/results/${r.session_id}`}
                        className="text-xs text-primary underline hover:text-primary/80"
                      >
                        详情
                      </Link>
                      <button
                        onClick={() => deleteMut.mutate(r.session_id)}
                        className="text-xs text-muted-foreground hover:text-destructive"
                      >
                        删除
                      </button>
                    </div>
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

function Th({ children }: { children?: React.ReactNode }) {
  return <th className="px-3 py-2 text-left text-xs font-medium text-muted-foreground">{children}</th>
}

function ThSort({
  children,
  field,
  current,
  dir,
  onClick,
}: {
  children: React.ReactNode
  field: string
  current: string
  dir: "asc" | "desc"
  onClick: (field: string) => void
}) {
  return (
    <th
      className="cursor-pointer px-3 py-2 text-left text-xs font-medium text-muted-foreground hover:text-foreground"
      onClick={() => onClick(field)}
    >
      {children}
      {current === field && <span className="ml-1">{dir === "asc" ? "↑" : "↓"}</span>}
    </th>
  )
}
