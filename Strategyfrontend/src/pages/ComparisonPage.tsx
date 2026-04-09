import { useQuery } from "@tanstack/react-query"
import { useSearchParams, Link } from "react-router-dom"
import { useMemo, useState } from "react"
import { cn } from "@/lib/utils"
import { fetchPortfolio, fetchPresets } from "@/api/client"
import { Badge } from "@/components/ui/badge"
import { Checkbox } from "@/components/ui/checkbox"
import type { Portfolio, PresetsResponse } from "@/types"

export default function ComparisonPage() {
  const [searchParams] = useSearchParams()
  const ids = useMemo(
    () => (searchParams.get("ids") ?? "").split(",").filter(Boolean),
    [searchParams],
  )
  const [diffOnly, setDiffOnly] = useState(false)

  // Fetch all selected portfolios
  const portfolioQueries = ids.map((id) => ({
    queryKey: ["portfolio", id],
    queryFn: () => fetchPortfolio(id),
  }))

  const results = portfolioQueries.map((opts) =>
    // eslint-disable-next-line react-hooks/rules-of-hooks
    useQuery<Portfolio>(opts),
  )

  const { data: presets } = useQuery<PresetsResponse>({
    queryKey: ["presets"],
    queryFn: fetchPresets,
  })

  const isLoading = results.some((r) => r.isLoading)
  const portfolios = results
    .map((r) => r.data)
    .filter((p): p is Portfolio => !!p)

  // Derive comparison data
  const comparison = useMemo(() => {
    if (portfolios.length < 2) return null

    const configs = portfolios.map((p) => p.group_config ?? {})

    // Collect all param keys
    const allKeys = new Set<string>()
    for (const cfg of configs) {
      for (const key of Object.keys(cfg)) allKeys.add(key)
    }
    const sortedKeys = [...allKeys].sort()

    // Find which keys have differences
    const diffKeys = new Set<string>()
    for (const key of sortedKeys) {
      const values = configs.map((c) => JSON.stringify(c[key] ?? null))
      if (new Set(values).size > 1) diffKeys.add(key)
    }

    // Stats per portfolio
    const stats = portfolios.map((p) => {
      const returns = p.items.map((it) => it.total_return_pct)
      const avg =
        returns.length > 0
          ? returns.reduce((a, b) => a + b, 0) / returns.length
          : 0
      return {
        slugCount: p.items.length,
        avgReturn: avg,
        minReturn: returns.length > 0 ? Math.min(...returns) : 0,
        maxReturn: returns.length > 0 ? Math.max(...returns) : 0,
      }
    })

    return { configs, sortedKeys, diffKeys, stats }
  }, [portfolios])

  if (ids.length < 2) {
    return (
      <div className="py-12 text-center text-muted-foreground">
        需要选择至少 2 个策略组进行对照。
        <Link to="/portfolios" className="ml-2 text-primary hover:underline">
          返回组合列表
        </Link>
      </div>
    )
  }

  if (isLoading) {
    return <div className="py-12 text-center text-muted-foreground">加载中...</div>
  }

  if (!comparison || portfolios.length < 2) {
    return (
      <div className="py-12 text-center text-muted-foreground">
        无法加载对照数据。
        <Link to="/portfolios" className="ml-2 text-primary hover:underline">
          返回组合列表
        </Link>
      </div>
    )
  }

  const { configs, sortedKeys, diffKeys, stats } = comparison
  const displayKeys = diffOnly ? sortedKeys.filter((k) => diffKeys.has(k)) : sortedKeys

  const getParamLabel = (key: string) => {
    if (!presets?.param_schema?.[key]) return key
    return presets.param_schema[key].label?.zh ?? key
  }

  return (
    <div className="flex flex-col gap-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">策略组参数对照</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            对比 {portfolios.length} 个策略组的参数配置与收益表现
          </p>
        </div>
        <Link
          to="/portfolios"
          className="rounded-md border px-3 py-1.5 text-sm font-medium transition-colors hover:bg-muted"
        >
          返回列表
        </Link>
      </div>

      {/* Summary cards */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <SummaryCard label="参数差异数" value={`${diffKeys.size} / ${sortedKeys.length}`} />
        {stats.map((s, i) => (
          <SummaryCard
            key={portfolios[i].portfolio_id}
            label={portfolios[i].name}
            value={`${s.slugCount} 数据源`}
            sub={`收益 ${(s.minReturn * 100).toFixed(1)}% ~ ${(s.maxReturn * 100).toFixed(1)}%，均值 ${s.avgReturn >= 0 ? "+" : ""}${(s.avgReturn * 100).toFixed(2)}%`}
          />
        ))}
      </div>

      {/* Filter toggle */}
      <div className="flex items-center gap-2">
        <label className="flex cursor-pointer items-center gap-2 text-sm">
          <Checkbox
            checked={diffOnly}
            onCheckedChange={(v) => setDiffOnly(v === true)}
          />
          仅显示有差异的参数
          {diffOnly && (
            <span className="text-xs text-muted-foreground">
              ({diffKeys.size} 项)
            </span>
          )}
        </label>
      </div>

      {/* Comparison table */}
      <div className="overflow-auto rounded-lg border">
        <table className="w-full text-sm">
          <thead className="bg-muted/50">
            <tr className="border-b text-left text-xs text-muted-foreground">
              <th className="sticky left-0 bg-muted/50 px-4 py-2.5 font-medium">参数</th>
              {portfolios.map((p) => (
                <th key={p.portfolio_id} className="min-w-[160px] px-4 py-2.5">
                  <div className="font-medium text-foreground">{p.name}</div>
                  <div className="mt-0.5 font-normal">
                    {p.group_strategy} · {stats[portfolios.indexOf(p)].slugCount} slug
                  </div>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {displayKeys.length === 0 ? (
              <tr>
                <td
                  colSpan={1 + portfolios.length}
                  className="py-8 text-center text-muted-foreground"
                >
                  {diffOnly ? "所有参数完全相同" : "无参数数据"}
                </td>
              </tr>
            ) : (
              displayKeys.map((key) => {
                const isDiff = diffKeys.has(key)
                const values = configs.map((c) => c[key])
                return (
                  <tr
                    key={key}
                    className={cn(
                      "border-b transition-colors hover:bg-muted/30",
                      isDiff && "bg-amber-50/50 dark:bg-amber-950/20",
                    )}
                  >
                    <td className="sticky left-0 bg-background px-4 py-2">
                      <div className="flex items-center gap-2">
                        <span className="font-mono text-xs">{key}</span>
                        {isDiff && (
                          <Badge variant="outline" className="text-[10px] text-amber-600">
                            差异
                          </Badge>
                        )}
                      </div>
                      <div className="text-[10px] text-muted-foreground">
                        {getParamLabel(key)}
                      </div>
                    </td>
                    {values.map((val, i) => {
                      const strVal = val === undefined ? "—" : String(val)
                      const isUnique =
                        isDiff &&
                        values.filter(
                          (v) => JSON.stringify(v) === JSON.stringify(val),
                        ).length === 1
                      return (
                        <td
                          key={portfolios[i].portfolio_id}
                          className={cn(
                            "px-4 py-2 font-mono text-xs",
                            isUnique && "font-semibold text-amber-700 dark:text-amber-400",
                          )}
                        >
                          {strVal}
                        </td>
                      )
                    })}
                  </tr>
                )
              })
            )}
          </tbody>
        </table>
      </div>
    </div>
  )
}

function SummaryCard({
  label,
  value,
  sub,
}: {
  label: string
  value: string
  sub?: string
}) {
  return (
    <div className="rounded-lg border p-3">
      <div className="text-xs text-muted-foreground">{label}</div>
      <div className="mt-1 text-sm font-semibold">{value}</div>
      {sub && <div className="mt-0.5 text-[10px] text-muted-foreground">{sub}</div>}
    </div>
  )
}
