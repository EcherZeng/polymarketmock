import { useState, useMemo, useCallback } from "react"
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import { useNavigate } from "react-router-dom"
import { cn, fmtDateTimeCst } from "@/lib/utils"
import {
  fetchStrategies,
  fetchArchives,
  savePreset,
  deletePreset,
  renamePreset,
  runBacktest,
  submitBatch,
  trackArchive,
  fetchTracked,
  fetchPortfolios,
} from "@/api/client"
import { PARAM_SCHEMA, PARAM_GROUPS, DEFAULT_UNIFIED_RULES } from "@/config/paramSchema"
import type {
  StrategyInfo,
  ArchiveInfo,
  RunRequest,
  BatchRequest,
  I18nLabel,
  Portfolio,
} from "@/types"
import StrategyConfigForm from "@/components/StrategyConfigForm"
import MechanismExplainer from "@/components/MechanismExplainer"
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from "@/components/ui/dialog"

/** Extract category prefix from slug: "btc-updown-5m-1774857300" → "btc-updown-5m" */
function extractCategory(slug: string): string {
  const match = slug.match(/^(.+)-\d{7,}$/)
  return match ? match[1] : slug
}

/** Get localised text from i18n label */
function t(label: I18nLabel | string | undefined): string {
  if (!label) return ""
  if (typeof label === "string") return label
  return label.zh || label.en
}

export default function StrategyPage() {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [selectedStrategy, setSelectedStrategy] = useState<string>("")
  const [selectedSlug, setSelectedSlug] = useState<string>("")
  const [selectedSlugs, setSelectedSlugs] = useState<Set<string>>(new Set())
  const [balance, setBalance] = useState(10000)
  const [configValues, setConfigValues] = useState<Record<string, unknown>>({})
  const [settlementMode, setSettlementMode] = useState<"auto" | "yes" | "no">("auto")
  const [configDialogOpen, setConfigDialogOpen] = useState(false)
  const [searchTerm, setSearchTerm] = useState("")
  const [activeCategory, setActiveCategory] = useState<string>("")
  const [archiveSort, setArchiveSort] = useState<"time" | "name">("time")
  const [batchSize, setBatchSize] = useState<number>(0) // 0=all, 10/20/50=top N, -50=random 50, -1=custom
  const [customBatchMode, setCustomBatchMode] = useState<"top" | "random">("top")
  const [customBatchCount, setCustomBatchCount] = useState<number>(30)
  const [savePresetName, setSavePresetName] = useState("")
  const [savePresetDesc, setSavePresetDesc] = useState("")
  const [createStrategyOpen, setCreateStrategyOpen] = useState(false)
  const [newStrategyName, setNewStrategyName] = useState("")
  const [newStrategyDesc, setNewStrategyDesc] = useState("")
  const [newStrategyValues, setNewStrategyValues] = useState<Record<string, unknown>>({})
  const [dataTab, setDataTab] = useState<"archives" | "portfolios">("archives")
  const [portfolioSearch, setPortfolioSearch] = useState("")
  const [selectedPortfolioId, setSelectedPortfolioId] = useState<string>("")
  const [cumulativeCapital, setCumulativeCapital] = useState(false)
  const [configActiveParams, setConfigActiveParams] = useState<Set<string>>(new Set())
  const [newStrategyActiveParams, setNewStrategyActiveParams] = useState<Set<string>>(new Set())
  const [renameEditing, setRenameEditing] = useState(false)
  const [renameValue, setRenameValue] = useState("")

  const { data: strategies = [], isLoading: loadingStrategies } = useQuery<StrategyInfo[]>({
    queryKey: ["strategies"],
    queryFn: fetchStrategies,
  })

  const { data: archives = [], isLoading: loadingArchives } = useQuery<ArchiveInfo[]>({
    queryKey: ["archives"],
    queryFn: fetchArchives,
  })

  const { data: trackedSlugs = [] } = useQuery<string[]>({
    queryKey: ["tracked"],
    queryFn: fetchTracked,
  })

  const { data: portfolios = [] } = useQuery<Portfolio[]>({
    queryKey: ["portfolios"],
    queryFn: fetchPortfolios,
  })

  const filteredPortfolios = useMemo(() => {
    let list = [...portfolios]
    // Sort newest first
    list.sort((a, b) => (b.created_at ?? "").localeCompare(a.created_at ?? ""))
    if (!portfolioSearch.trim()) return list
    const term = portfolioSearch.trim().toLowerCase()
    return list.filter(
      (p) =>
        p.name.toLowerCase().includes(term) ||
        p.items.some((it) => it.slug.toLowerCase().includes(term)),
    )
  }, [portfolios, portfolioSearch])

  const selectedPortfolio = useMemo(
    () => portfolios.find((p) => p.portfolio_id === selectedPortfolioId),
    [portfolios, selectedPortfolioId],
  )

  const trackMutation = useMutation({
    mutationFn: (slug: string) => trackArchive(slug),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["tracked"] })
    },
  })

  const paramSchema = PARAM_SCHEMA
  const paramGroups = PARAM_GROUPS

  const activeStrategy = useMemo(
    () => strategies.find((s) => s.name === selectedStrategy),
    [strategies, selectedStrategy],
  )

  /** Set of config keys relevant for the selected strategy — use full schema so existing strategies can add any param */
  const visibleKeys = useMemo(() => new Set(Object.keys(paramSchema)), [paramSchema])

  // ── Save preset mutation ──────────────────────────────────────────────────

  const savePresetMutation = useMutation({
    mutationFn: (args: { name: string; desc: string; params: Record<string, unknown> }) =>
      savePreset(args.name, { description: args.desc, params: args.params }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["strategies"] })
      setSavePresetName("")
      setSavePresetDesc("")
    },
  })

  const deletePresetMutation = useMutation({
    mutationFn: (name: string) => deletePreset(name),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["strategies"] })
    },
  })

  const renamePresetMutation = useMutation({
    mutationFn: (args: { oldName: string; newName: string }) =>
      renamePreset(args.oldName, args.newName),
    onSuccess: (_data, variables) => {
      queryClient.invalidateQueries({ queryKey: ["strategies"] })
      setSelectedStrategy(variables.newName)
      setRenameEditing(false)
    },
  })

  // ── Category & filtered archives ──────────────────────────────────────────

  const categories = useMemo(() => {
    const cats = [...new Set(archives.map((a) => extractCategory(a.slug)))]
    cats.sort()
    return cats
  }, [archives])

  const filteredArchives = useMemo(() => {
    let list = archives
    if (activeCategory) {
      list = list.filter((a) => extractCategory(a.slug) === activeCategory)
    }
    if (searchTerm.trim()) {
      const term = searchTerm.trim().toLowerCase()
      list = list.filter((a) => a.slug.toLowerCase().includes(term))
    }
    const sorted = [...list]
    if (archiveSort === "time") {
      sorted.sort((a, b) => (b.time_range?.start ?? "").localeCompare(a.time_range?.start ?? ""))
    } else {
      sorted.sort((a, b) => a.slug.localeCompare(b.slug))
    }
    return sorted
  }, [archives, activeCategory, searchTerm, archiveSort])

  // ── Settlement helper ─────────────────────────────────────────────────────

  const buildSettlementResult = useCallback(
    (tokenIds: string[]): Record<string, number> | undefined => {
      if (settlementMode === "yes") {
        return Object.fromEntries(tokenIds.map((tid) => [tid, 1.0]))
      }
      if (settlementMode === "no") {
        return Object.fromEntries(tokenIds.map((tid) => [tid, 0.0]))
      }
      return undefined
    },
    [settlementMode],
  )

  // ── Single run mutation ───────────────────────────────────────────────────

  const mutation = useMutation({
    mutationFn: (req: RunRequest) => runBacktest(req),
    onSuccess: (result) => {
      queryClient.invalidateQueries({ queryKey: ["results"] })
      navigate(`/results/${result.session_id}`)
    },
  })

  // ── Batch submit mutation ─────────────────────────────────────────────────

  const batchMutation = useMutation({
    mutationFn: (req: BatchRequest) => submitBatch(req),
    onSuccess: (result) => {
      queryClient.invalidateQueries({ queryKey: ["batchTasks"] })
      navigate(`/batch/${result.batch_id}`)
    },
  })

  // ── Handlers ──────────────────────────────────────────────────────────────

  function handleStrategyClick(s: StrategyInfo) {
    setSelectedStrategy(s.name)
    setConfigValues(
      Object.fromEntries(
        Object.entries(s.default_config).map(([k, v]) => [k, v]),
      ),
    )
    setConfigActiveParams(new Set(Object.keys(s.default_config)))
    setConfigDialogOpen(true)
  }

  function handleArchiveClick(slug: string) {
    setSelectedSlug(slug)
  }

  function handleToggleSelect(slug: string) {
    setSelectedSlugs((prev) => {
      const next = new Set(prev)
      if (next.has(slug)) next.delete(slug)
      else next.add(slug)
      return next
    })
  }

  function handleSelectAll() {
    let picked: typeof filteredArchives
    if (batchSize === -1) {
      // Custom mode
      const count = Math.min(customBatchCount, filteredArchives.length)
      if (customBatchMode === "random") {
        const shuffled = [...filteredArchives].sort(() => Math.random() - 0.5)
        picked = shuffled.slice(0, count)
      } else {
        picked = filteredArchives.slice(0, count)
      }
    } else if (batchSize === -50) {
      // Random 50
      const shuffled = [...filteredArchives].sort(() => Math.random() - 0.5)
      picked = shuffled.slice(0, Math.min(50, filteredArchives.length))
    } else if (batchSize > 0) {
      picked = filteredArchives.slice(0, batchSize)
    } else {
      picked = filteredArchives
    }
    setSelectedSlugs(new Set(picked.map((a) => a.slug)))
  }

  function handleDeselectAll() {
    setSelectedSlugs(new Set())
  }

  /** Build config: only include active params */
  function buildConfig(vals: Record<string, unknown>, activeP: Set<string>): Record<string, unknown> {
    const result: Record<string, unknown> = {}
    for (const key of activeP) {
      if (key in vals) result[key] = vals[key]
    }
    return result
  }

  /** Filter config to only include active params */
  function activeConfig(): Record<string, unknown> {
    return buildConfig(configValues, configActiveParams)
  }

  function handleRun() {
    if (!selectedStrategy || !selectedSlug) return
    const selectedArchive = archives.find((a) => a.slug === selectedSlug)
    const settlement_result = selectedArchive
      ? buildSettlementResult(selectedArchive.token_ids)
      : undefined

    mutation.mutate({
      strategy: selectedStrategy,
      slug: selectedSlug,
      initial_balance: balance,
      config: activeConfig(),
      ...(settlement_result ? { settlement_result } : {}),
    })
  }

  function handleBatchRun() {
    if (!selectedStrategy || selectedSlugs.size === 0) return
    // Use first selected archive's token_ids for settlement (all same market type)
    const firstSlug = [...selectedSlugs][0]
    const firstArchive = archives.find((a) => a.slug === firstSlug)
    const settlement_result = firstArchive
      ? buildSettlementResult(firstArchive.token_ids)
      : undefined

    batchMutation.mutate({
      strategy: selectedStrategy,
      slugs: [...selectedSlugs],
      initial_balance: balance,
      config: activeConfig(),
      ...(settlement_result ? { settlement_result } : {}),
      cumulative_capital: cumulativeCapital,
    })
  }

  function handlePortfolioBatchRun() {
    if (!selectedStrategy || !selectedPortfolio) return
    const slugs = [...new Set(selectedPortfolio.items.map((it) => it.slug))]
    if (slugs.length === 0) return
    const firstArchive = archives.find((a) => a.slug === slugs[0])
    const settlement_result = firstArchive
      ? buildSettlementResult(firstArchive.token_ids)
      : undefined
    batchMutation.mutate({
      strategy: selectedStrategy,
      slugs,
      initial_balance: balance,
      config: activeConfig(),
      ...(settlement_result ? { settlement_result } : {}),
      cumulative_capital: cumulativeCapital,
    })
  }

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">策略回测</h1>
        <p className="text-muted-foreground">选择策略和数据源，配置参数后运行回测</p>
      </div>

      <MechanismExplainer />

      <div className="grid gap-6 lg:grid-cols-12">
        {/* Left: Strategy selection + run controls */}
        <div className="flex flex-col gap-4 lg:col-span-4">
          <h2 className="text-sm font-medium text-muted-foreground">可用策略</h2>
          {loadingStrategies ? (
            <div className="text-sm text-muted-foreground">加载中...</div>
          ) : (
            <div className="flex flex-col gap-2">
              {strategies.map((s) => (
                <button
                  key={s.name}
                  onClick={() => handleStrategyClick(s)}
                  className={cn(
                    "rounded-lg border p-4 text-left transition-colors",
                    selectedStrategy === s.name
                      ? "border-primary bg-primary/5"
                      : "border-border hover:border-primary/50",
                  )}
                >
                  <div className="flex items-center justify-between">
                    <span className="font-medium">{s.name}</span>
                    <div className="flex items-center gap-2">
                      <span className="text-xs text-muted-foreground">v{s.version}</span>
                    </div>
                  </div>
                  <p className="mt-1 text-sm text-muted-foreground">{t(s.description)}</p>
                  <button
                    onClick={(e) => {
                      e.stopPropagation()
                      if (confirm(`确定删除自定义预设 "${s.name}"？`)) {
                        deletePresetMutation.mutate(s.name)
                      }
                    }}
                    className="mt-1 text-xs text-destructive hover:underline"
                  >
                    删除
                  </button>
                </button>
              ))}
              <button
                onClick={() => {
                  // Base values from unified_rules + param_schema defaults
                  const base: Record<string, unknown> = { ...DEFAULT_UNIFIED_RULES }
                  for (const [k, s] of Object.entries(paramSchema)) {
                    if (!(k in base) && s.disable_value != null) base[k] = s.disable_value
                  }

                  setNewStrategyValues(base)

                  // Active params: only core params (non-advanced, non-child)
                  const coreKeys = new Set(
                    Object.entries(paramSchema)
                      .filter(([, s]) =>
                        s.visibility !== "advanced" &&
                        !s.depends_on &&
                        !s.pool_hidden
                      )
                      .map(([k]) => k)
                  )
                  setNewStrategyActiveParams(coreKeys)
                  setNewStrategyName("")
                  setNewStrategyDesc("")
                  setCreateStrategyOpen(true)
                }}
                className="rounded-lg border border-dashed border-muted-foreground/30 p-4 text-center text-sm text-muted-foreground hover:border-primary/50 hover:text-foreground transition-colors"
              >
                + 创建策略
              </button>
            </div>
          )}

          {/* Balance + Settlement + Run */}
          <div className="rounded-lg border p-4">
            <div className="flex flex-col gap-3">
              <div className="flex flex-col gap-1">
                <label className="text-sm text-muted-foreground">初始资金</label>
                <input
                  type="number"
                  value={balance}
                  onChange={(e) => setBalance(Number(e.target.value))}
                  min={1}
                  className="h-9 w-full rounded-md border bg-background px-3 text-sm"
                />
              </div>
              <div className="flex flex-col gap-1">
                <label className="text-sm text-muted-foreground">结算方式</label>
                <select
                  value={settlementMode}
                  onChange={(e) => setSettlementMode(e.target.value as "auto" | "yes" | "no")}
                  className="h-9 w-full rounded-md border bg-background px-3 text-sm"
                >
                  <option value="auto">自动推断</option>
                  <option value="yes">指定 YES</option>
                  <option value="no">指定 NO</option>
                </select>
              </div>

              {/* Single run */}
              <button
                onClick={handleRun}
                disabled={!selectedStrategy || !selectedSlug || mutation.isPending}
                className={cn(
                  "h-9 w-full rounded-md text-sm font-medium transition-colors",
                  "bg-primary text-primary-foreground hover:bg-primary/90",
                  "disabled:pointer-events-none disabled:opacity-50",
                )}
              >
                {mutation.isPending ? "运行中..." : "运行回测"}
              </button>

              {/* Cumulative capital toggle */}
              <label className="flex items-center gap-2 text-sm">
                <input
                  type="checkbox"
                  checked={cumulativeCapital}
                  onChange={(e) => setCumulativeCapital(e.target.checked)}
                  className="size-4 rounded border accent-emerald-600"
                />
                <span className="text-muted-foreground">累计本金模式</span>
                {cumulativeCapital && (
                  <span className="text-xs text-amber-600">(串行执行)</span>
                )}
              </label>

              {/* Batch run */}
              <button
                onClick={handleBatchRun}
                disabled={
                  !selectedStrategy || selectedSlugs.size === 0 || batchMutation.isPending
                }
                className={cn(
                  "h-9 w-full rounded-md text-sm font-medium transition-colors",
                  "bg-emerald-600 text-white hover:bg-emerald-700",
                  "disabled:pointer-events-none disabled:opacity-50",
                )}
              >
                {batchMutation.isPending
                  ? "提交中..."
                  : `批量回测 (${selectedSlugs.size} 条)`}
              </button>

              {mutation.isError && (
                <p className="text-sm text-destructive">
                  回测失败: {(mutation.error as Error).message}
                </p>
              )}
              {batchMutation.isError && (
                <p className="text-sm text-destructive">
                  批量提交失败: {(batchMutation.error as Error).message}
                </p>
              )}
            </div>
          </div>
        </div>

        {/* Right: Data source */}
        <div className="flex flex-col gap-4 lg:col-span-8">
          <div className="rounded-lg border p-4">
            {/* Tab switcher: 数据源 / 组合 */}
            <div className="mb-3 flex items-center gap-2">
              <button
                onClick={() => setDataTab("archives")}
                className={cn(
                  "rounded-md px-3 py-1.5 text-sm font-medium transition-colors",
                  dataTab === "archives"
                    ? "bg-foreground text-background"
                    : "text-muted-foreground hover:text-foreground",
                )}
              >
                数据源
              </button>
              <button
                onClick={() => setDataTab("portfolios")}
                className={cn(
                  "rounded-md px-3 py-1.5 text-sm font-medium transition-colors",
                  dataTab === "portfolios"
                    ? "bg-foreground text-background"
                    : "text-muted-foreground hover:text-foreground",
                )}
              >
                组合
              </button>
            </div>

            {dataTab === "archives" && (
              <>
            {/* Category filter tabs */}
            {categories.length > 1 && (
              <div className="mb-3 flex flex-wrap gap-2">
                <button
                  onClick={() => setActiveCategory("")}
                  className={cn(
                    "h-7 rounded-md border px-3 text-xs font-medium transition-colors",
                    !activeCategory
                      ? "border-primary bg-primary/10 text-primary"
                      : "hover:border-primary/50",
                  )}
                >
                  全部
                </button>
                {categories.map((cat) => (
                  <button
                    key={cat}
                    onClick={() => setActiveCategory(cat)}
                    className={cn(
                      "h-7 rounded-md border px-3 text-xs font-medium transition-colors",
                      activeCategory === cat
                        ? "border-primary bg-primary/10 text-primary"
                        : "hover:border-primary/50",
                    )}
                  >
                    {cat}
                  </button>
                ))}
              </div>
            )}

            {/* Search + batch controls */}
            <div className="mb-3 flex flex-wrap items-center gap-2">
              <input
                type="text"
                placeholder="搜索 slug..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                className="h-8 w-48 rounded-md border bg-background px-3 text-sm"
              />
              <select
                value={archiveSort}
                onChange={(e) => setArchiveSort(e.target.value as "time" | "name")}
                className="h-8 rounded-md border bg-background px-2 text-xs"
              >
                <option value="time">时间最新</option>
                <option value="name">名称排序</option>
              </select>
              <div className="flex items-center gap-1">
                <select
                  value={batchSize}
                  onChange={(e) => setBatchSize(Number(e.target.value))}
                  className="h-8 rounded-md border bg-background px-2 text-xs"
                >
                  <option value={0}>全部</option>
                  <option value={10}>前 10 条</option>
                  <option value={20}>前 20 条</option>
                  <option value={50}>前 50 条</option>
                  <option value={-50}>随机 50 条</option>
                  <option value={-1}>自定义</option>
                </select>
                {batchSize === -1 && (
                  <>
                    <select
                      value={customBatchMode}
                      onChange={(e) => setCustomBatchMode(e.target.value as "top" | "random")}
                      className="h-8 rounded-md border bg-background px-2 text-xs"
                    >
                      <option value="top">前</option>
                      <option value="random">随机</option>
                    </select>
                    <input
                      type="number"
                      min={1}
                      max={filteredArchives.length || 999}
                      value={customBatchCount}
                      onChange={(e) => setCustomBatchCount(Math.max(1, Number(e.target.value)))}
                      className="h-8 w-16 rounded-md border bg-background px-2 text-xs"
                    />
                    <span className="text-xs text-muted-foreground">条</span>
                  </>
                )}
                <button
                  onClick={handleSelectAll}
                  className="h-8 rounded-md border px-3 text-xs font-medium transition-colors hover:bg-muted"
                >
                  选择
                </button>
                <button
                  onClick={handleDeselectAll}
                  className="h-8 rounded-md border px-3 text-xs font-medium transition-colors hover:bg-muted"
                >
                  清除
                </button>
              </div>
              <span className="text-xs text-muted-foreground">
                {filteredArchives.length} 条数据 · 已选 {selectedSlugs.size} 条
              </span>
            </div>

            {/* Archive list */}
            {loadingArchives ? (
              <div className="text-sm text-muted-foreground">扫描中...</div>
            ) : archives.length === 0 ? (
              <div className="text-sm text-muted-foreground">
                暂无归档数据。请先在主平台采集数据。
              </div>
            ) : (
              <div className="flex max-h-[520px] flex-col gap-2 overflow-y-auto pr-1">
                {filteredArchives.map((a) => (
                  <div
                    key={a.slug}
                    className={cn(
                      "flex items-center gap-2 rounded-lg border p-3 transition-colors",
                      selectedSlug === a.slug
                        ? "border-primary bg-primary/5"
                        : "border-border hover:border-primary/50",
                    )}
                  >
                    {/* Checkbox for batch selection */}
                    <input
                      type="checkbox"
                      checked={selectedSlugs.has(a.slug)}
                      onChange={() => handleToggleSelect(a.slug)}
                      className="h-4 w-4 shrink-0 rounded border accent-emerald-600"
                    />
                    {/* Clickable area for single selection */}
                    <button
                      onClick={() => handleArchiveClick(a.slug)}
                      className="flex-1 text-left"
                    >
                      <div className="flex items-center justify-between">
                        <span className="font-mono text-sm font-medium">{a.slug}</span>
                        <span className="text-xs text-muted-foreground">{a.size_mb} MB</span>
                      </div>
                      <div className="mt-1 flex flex-wrap gap-2 text-xs text-muted-foreground">
                        <span>{a.prices_count} 价格</span>
                        <span>·</span>
                        <span>{a.orderbooks_count} 盘口</span>
                        <span>·</span>
                        <span>{a.live_trades_count} 成交</span>
                        {a.slug.includes("-5m-") ? (
                          <>
                            <span>·</span>
                            <span className="text-blue-500">5 分钟</span>
                          </>
                        ) : a.slug.includes("-15m-") ? (
                          <>
                            <span>·</span>
                            <span className="text-blue-500">15 分钟</span>
                          </>
                        ) : a.slug.includes("-30m-") ? (
                          <>
                            <span>·</span>
                            <span className="text-blue-500">30 分钟</span>
                          </>
                        ) : null}
                        {a.time_range.start && (
                          <>
                            <span>·</span>
                            <span>{fmtDateTimeCst(a.time_range.start)}</span>
                          </>
                        )}
                      </div>
                    </button>
                    {/* Track / Upload button */}
                    {selectedSlug === a.slug && (
                      <button
                        onClick={(e) => {
                          e.stopPropagation()
                          trackMutation.mutate(a.slug)
                        }}
                        disabled={
                          trackMutation.isPending || trackedSlugs.includes(a.slug)
                        }
                        className={cn(
                          "shrink-0 rounded-md border px-3 py-1.5 text-xs font-medium transition-colors",
                          trackedSlugs.includes(a.slug)
                            ? "border-emerald-500 bg-emerald-50 text-emerald-700 dark:bg-emerald-900/20 dark:text-emerald-400"
                            : "border-primary/50 text-primary hover:bg-primary/10",
                          "disabled:pointer-events-none disabled:opacity-60",
                        )}
                      >
                        {trackedSlugs.includes(a.slug)
                          ? "已上传"
                          : trackMutation.isPending &&
                              trackMutation.variables === a.slug
                            ? "上传中..."
                            : "上传"}
                      </button>
                    )}
                  </div>
                ))}
              </div>
            )}
              </>
            )}

            {dataTab === "portfolios" && (
              <>
                {/* Portfolio search */}
                <div className="mb-3 flex items-center gap-2">
                  <input
                    type="text"
                    placeholder="搜索组合名称或数据源..."
                    value={portfolioSearch}
                    onChange={(e) => setPortfolioSearch(e.target.value)}
                    className="h-8 w-64 rounded-md border bg-background px-3 text-sm"
                  />
                  <span className="text-xs text-muted-foreground">
                    {filteredPortfolios.length} 个组合
                  </span>
                </div>

                {filteredPortfolios.length === 0 ? (
                  <div className="py-8 text-center text-sm text-muted-foreground">
                    暂无组合。在批量回测详情页中选择成功结果来创建组合。
                  </div>
                ) : (
                  <div className="flex max-h-[520px] flex-col gap-2 overflow-y-auto pr-1">
                    {filteredPortfolios.map((p) => {
                      const avgReturn =
                        p.items.length > 0
                          ? p.items.reduce((a, it) => a + it.total_return_pct, 0) /
                            p.items.length
                          : 0
                      const isSelected = selectedPortfolioId === p.portfolio_id
                      return (
                        <button
                          key={p.portfolio_id}
                          onClick={() => setSelectedPortfolioId(isSelected ? "" : p.portfolio_id)}
                          className={cn(
                            "rounded-lg border p-3 text-left transition-colors",
                            isSelected
                              ? "border-primary bg-primary/5"
                              : "border-border hover:border-primary/50",
                          )}
                        >
                          <div className="flex items-center justify-between">
                            <span className="font-medium">{p.name}</span>
                            <span className="text-xs text-muted-foreground">
                              {p.items.length} 条数据源
                            </span>
                          </div>
                          <div className="mt-1 flex flex-wrap gap-2 text-xs text-muted-foreground">
                            <span
                              className={cn(
                                "font-mono",
                                avgReturn >= 0 ? "text-emerald-600" : "text-red-500",
                              )}
                            >
                              平均收益: {avgReturn >= 0 ? "+" : ""}
                              {avgReturn.toFixed(2)}%
                            </span>
                            <span>·</span>
                            <span>
                              创建于 {p.created_at.replace("T", " ").slice(0, 10)}
                            </span>
                          </div>
                          {isSelected && (
                            <div className="mt-2 flex flex-wrap gap-1">
                              {p.items.slice(0, 8).map((it) => (
                                <span
                                  key={it.session_id}
                                  className="rounded bg-muted px-1.5 py-0.5 font-mono text-[10px]"
                                >
                                  {it.slug}
                                </span>
                              ))}
                              {p.items.length > 8 && (
                                <span className="text-[10px] text-muted-foreground">
                                  +{p.items.length - 8} 更多
                                </span>
                              )}
                            </div>
                          )}
                        </button>
                      )
                    })}
                  </div>
                )}

                {/* Run batch on selected portfolio */}
                {selectedPortfolio && (
                  <div className="mt-3 flex items-center justify-between rounded-lg border bg-muted/30 p-3">
                    <div className="text-sm">
                      <span className="text-muted-foreground">已选组合: </span>
                      <span className="font-medium">{selectedPortfolio.name}</span>
                      <span className="ml-2 text-xs text-muted-foreground">
                        ({selectedPortfolio.items.length} 条数据源)
                      </span>
                    </div>
                    <button
                      onClick={handlePortfolioBatchRun}
                      disabled={
                        !selectedStrategy ||
                        selectedPortfolio.items.length === 0 ||
                        batchMutation.isPending
                      }
                      className={cn(
                        "rounded-md px-4 py-1.5 text-sm font-medium transition-colors",
                        "bg-emerald-600 text-white hover:bg-emerald-700",
                        "disabled:pointer-events-none disabled:opacity-50",
                      )}
                    >
                      {batchMutation.isPending
                        ? "提交中..."
                        : `批量回测 (${selectedPortfolio.items.length} 条)`}
                    </button>
                  </div>
                )}
              </>
            )}
          </div>

          {/* Selected strategy indicator */}
          {activeStrategy && (
            <div className="flex items-center gap-3 rounded-lg border p-3">
              <div className="flex-1">
                <span className="text-sm text-muted-foreground">当前策略: </span>
                <span className="text-sm font-medium">{activeStrategy.name}</span>
                <span className="ml-2 text-xs text-muted-foreground">v{activeStrategy.version}</span>
              </div>
              <button
                onClick={() => setConfigDialogOpen(true)}
                className="rounded-md border px-3 py-1.5 text-xs font-medium transition-colors hover:bg-muted"
              >
                配置参数
              </button>
            </div>
          )}
        </div>
      </div>

      {/* Strategy config dialog */}
      <Dialog open={configDialogOpen} onOpenChange={(open) => {
        setConfigDialogOpen(open)
        if (!open) setRenameEditing(false)
      }}>
        <DialogContent className="max-h-[85vh] overflow-y-auto sm:max-w-5xl">
          <DialogHeader>
            <DialogTitle>
              <div className="flex items-center gap-2">
                <span>策略参数 —</span>
                {renameEditing ? (
                  <div className="flex items-center gap-1.5">
                    <input
                      type="text"
                      value={renameValue}
                      onChange={(e) => setRenameValue(e.target.value)}
                      onKeyDown={(e) => {
                        if (e.key === "Enter") {
                          const trimmed = renameValue.trim()
                          if (trimmed && trimmed !== activeStrategy?.name) {
                            renamePresetMutation.mutate({ oldName: activeStrategy!.name, newName: trimmed })
                          } else {
                            setRenameEditing(false)
                          }
                        }
                        if (e.key === "Escape") setRenameEditing(false)
                      }}
                      autoFocus
                      className="h-7 rounded-md border bg-background px-2 text-sm font-medium"
                    />
                    <button
                      onClick={() => {
                        const trimmed = renameValue.trim()
                        if (trimmed && trimmed !== activeStrategy?.name) {
                          renamePresetMutation.mutate({ oldName: activeStrategy!.name, newName: trimmed })
                        } else {
                          setRenameEditing(false)
                        }
                      }}
                      disabled={renamePresetMutation.isPending}
                      className="rounded-md bg-primary px-2 py-0.5 text-xs text-primary-foreground hover:bg-primary/90"
                    >
                      {renamePresetMutation.isPending ? "..." : "确定"}
                    </button>
                    <button
                      onClick={() => setRenameEditing(false)}
                      className="rounded-md border px-2 py-0.5 text-xs hover:bg-muted"
                    >
                      取消
                    </button>
                  </div>
                ) : (
                  <div className="flex items-center gap-1.5">
                    <span>{activeStrategy?.name}</span>
                    {activeStrategy && !activeStrategy.builtin && (
                      <button
                        onClick={() => {
                          setRenameValue(activeStrategy.name)
                          setRenameEditing(true)
                        }}
                        className="rounded-md border px-1.5 py-0.5 text-xs font-normal text-muted-foreground hover:bg-muted hover:text-foreground"
                        title="重命名策略"
                      >
                        重命名
                      </button>
                    )}
                  </div>
                )}
              </div>
              {renamePresetMutation.isError && (
                <span className="text-xs font-normal text-destructive">
                  重命名失败: {(renamePresetMutation.error as Error).message}
                </span>
              )}
            </DialogTitle>
            <DialogDescription>
              {t(activeStrategy?.description)}
            </DialogDescription>
          </DialogHeader>
          {activeStrategy && (
            <div className="flex flex-col gap-4 py-2">
              <StrategyConfigForm
                values={configValues}
                onChange={setConfigValues}
                paramSchema={paramSchema}
                paramGroups={paramGroups}
                visibleKeys={visibleKeys}
                activeParams={configActiveParams}
                onActiveParamsChange={setConfigActiveParams}
              />

              {/* Save as preset */}
              <div className="border-t pt-4">
                <h3 className="mb-2 text-sm font-medium text-muted-foreground">
                  保存为自定义预设
                </h3>
                <div className="flex flex-col gap-2">
                  <div className="flex gap-2">
                    <input
                      type="text"
                      placeholder="预设名称"
                      value={savePresetName}
                      onChange={(e) => setSavePresetName(e.target.value)}
                      className="h-8 flex-1 rounded-md border bg-background px-3 text-sm"
                    />
                    <input
                      type="text"
                      placeholder="描述（可选）"
                      value={savePresetDesc}
                      onChange={(e) => setSavePresetDesc(e.target.value)}
                      className="h-8 flex-1 rounded-md border bg-background px-3 text-sm"
                    />
                  </div>
                  <div className="flex items-center gap-2">
                    <button
                      onClick={() => {
                        const name = savePresetName.trim() || selectedStrategy
                        savePresetMutation.mutate({
                          name,
                          desc: savePresetDesc.trim(),
                          params: activeConfig(),
                        })
                      }}
                      disabled={savePresetMutation.isPending}
                      className={cn(
                        "h-8 rounded-md px-4 text-sm font-medium transition-colors",
                        "bg-primary text-primary-foreground hover:bg-primary/90",
                        "disabled:pointer-events-none disabled:opacity-50",
                      )}
                    >
                      {savePresetMutation.isPending ? "保存中..." : "保存预设"}
                    </button>
                    {savePresetMutation.isSuccess && (
                      <span className="text-xs text-emerald-600">已保存</span>
                    )}
                    {savePresetMutation.isError && (
                      <span className="text-xs text-destructive">
                        保存失败: {(savePresetMutation.error as Error).message}
                      </span>
                    )}
                  </div>
                </div>
              </div>
            </div>
          )}
        </DialogContent>
      </Dialog>

      {/* ── Create Strategy Dialog ─────────────────────────────────────── */}
      <Dialog open={createStrategyOpen} onOpenChange={setCreateStrategyOpen}>
        <DialogContent className="max-h-[85vh] overflow-y-auto sm:max-w-5xl">
          <DialogHeader>
            <DialogTitle>创建策略</DialogTitle>
            <DialogDescription>
              设置名称、描述和参数，保存为自定义策略预设
            </DialogDescription>
          </DialogHeader>
          <div className="flex flex-col gap-4 py-2">
            <div className="grid grid-cols-2 gap-3">
              <div className="flex flex-col gap-1">
                <label className="text-sm text-muted-foreground">策略名称 <span className="text-destructive">*</span></label>
                <input
                  type="text"
                  placeholder="输入策略名称"
                  value={newStrategyName}
                  onChange={(e) => setNewStrategyName(e.target.value)}
                  className="h-9 w-full rounded-md border bg-background px-3 text-sm"
                />
              </div>
              <div className="flex flex-col gap-1">
                <label className="text-sm text-muted-foreground">描述</label>
                <input
                  type="text"
                  placeholder="策略描述（可选）"
                  value={newStrategyDesc}
                  onChange={(e) => setNewStrategyDesc(e.target.value)}
                  className="h-9 w-full rounded-md border bg-background px-3 text-sm"
                />
              </div>
            </div>

            <StrategyConfigForm
              values={newStrategyValues}
              onChange={setNewStrategyValues}
              paramSchema={paramSchema}
              paramGroups={paramGroups}
              visibleKeys={new Set(Object.keys(paramSchema))}
              activeParams={newStrategyActiveParams}
              onActiveParamsChange={setNewStrategyActiveParams}
            />

            <div className="flex items-center justify-end gap-2 border-t pt-4">
              <button
                onClick={() => setCreateStrategyOpen(false)}
                className="h-9 rounded-md border px-4 text-sm hover:bg-muted"
              >
                取消
              </button>
              <button
                disabled={!newStrategyName.trim() || savePresetMutation.isPending}
                onClick={() => {
                  savePresetMutation.mutate(
                    {
                      name: newStrategyName.trim(),
                      desc: newStrategyDesc.trim(),
                      params: buildConfig(newStrategyValues, newStrategyActiveParams),
                    },
                    { onSuccess: () => setCreateStrategyOpen(false) },
                  )
                }}
                className={cn(
                  "h-9 rounded-md px-4 text-sm font-medium transition-colors",
                  "bg-primary text-primary-foreground hover:bg-primary/90",
                  "disabled:pointer-events-none disabled:opacity-50",
                )}
              >
                {savePresetMutation.isPending ? "创建中..." : "创建策略"}
              </button>
            </div>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  )
}
