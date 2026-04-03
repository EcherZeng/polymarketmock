import { useState, useMemo, useCallback } from "react"
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import { useNavigate } from "react-router-dom"
import { cn } from "@/lib/utils"
import {
  fetchStrategies,
  fetchArchives,
  fetchPresets,
  savePreset,
  deletePreset,
  runBacktest,
  submitBatch,
  trackArchive,
  fetchTracked,
} from "@/api/client"
import type {
  StrategyInfo,
  ArchiveInfo,
  RunRequest,
  BatchRequest,
  PresetsResponse,
  I18nLabel,
} from "@/types"
import StrategyConfigForm from "@/components/StrategyConfigForm"
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
  const [batchSize, setBatchSize] = useState<number>(0) // 0 = all
  const [savePresetName, setSavePresetName] = useState("")
  const [savePresetDesc, setSavePresetDesc] = useState("")

  const { data: strategies = [], isLoading: loadingStrategies } = useQuery<StrategyInfo[]>({
    queryKey: ["strategies"],
    queryFn: fetchStrategies,
  })

  const { data: archives = [], isLoading: loadingArchives } = useQuery<ArchiveInfo[]>({
    queryKey: ["archives"],
    queryFn: fetchArchives,
  })

  const { data: presetsData } = useQuery<PresetsResponse>({
    queryKey: ["presets"],
    queryFn: fetchPresets,
  })

  const { data: trackedSlugs = [] } = useQuery<string[]>({
    queryKey: ["tracked"],
    queryFn: fetchTracked,
  })

  const trackMutation = useMutation({
    mutationFn: (slug: string) => trackArchive(slug),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["tracked"] })
    },
  })

  const paramSchema = presetsData?.param_schema ?? {}
  const paramGroups = presetsData?.param_groups ?? {}

  const activeStrategy = useMemo(
    () => strategies.find((s) => s.name === selectedStrategy),
    [strategies, selectedStrategy],
  )

  /** Set of config keys relevant for the selected strategy */
  const visibleKeys = useMemo(() => {
    if (!activeStrategy) return new Set<string>()
    return new Set(Object.keys(activeStrategy.default_config))
  }, [activeStrategy])

  // ── Save preset mutation ──────────────────────────────────────────────────

  const savePresetMutation = useMutation({
    mutationFn: (args: { name: string; desc: string; params: Record<string, unknown> }) =>
      savePreset(args.name, { description: args.desc, params: args.params }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["strategies"] })
      queryClient.invalidateQueries({ queryKey: ["presets"] })
      setSavePresetName("")
      setSavePresetDesc("")
    },
  })

  const deletePresetMutation = useMutation({
    mutationFn: (name: string) => deletePreset(name),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["strategies"] })
      queryClient.invalidateQueries({ queryKey: ["presets"] })
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
    return list
  }, [archives, activeCategory, searchTerm])

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
    const slugs = batchSize > 0 ? filteredArchives.slice(0, batchSize) : filteredArchives
    setSelectedSlugs(new Set(slugs.map((a) => a.slug)))
  }

  function handleDeselectAll() {
    setSelectedSlugs(new Set())
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
      config: configValues,
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
      config: configValues,
      ...(settlement_result ? { settlement_result } : {}),
    })
  }

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">策略回测</h1>
        <p className="text-muted-foreground">选择策略和数据源，配置参数后运行回测</p>
      </div>

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
                      {s.builtin && (
                        <span className="rounded bg-muted px-1.5 py-0.5 text-[10px] font-medium text-muted-foreground">
                          内置
                        </span>
                      )}
                      <span className="text-xs text-muted-foreground">v{s.version}</span>
                    </div>
                  </div>
                  <p className="mt-1 text-sm text-muted-foreground">{t(s.description)}</p>
                  {!s.builtin && (
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
                  )}
                </button>
              ))}
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
            <h2 className="mb-3 text-sm font-medium text-muted-foreground">数据源</h2>

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
              <div className="flex items-center gap-1">
                <select
                  value={batchSize}
                  onChange={(e) => setBatchSize(Number(e.target.value))}
                  className="h-8 rounded-md border bg-background px-2 text-xs"
                >
                  <option value={0}>全部</option>
                  <option value={10}>前 10 条</option>
                  <option value={20}>前 20 条</option>
                </select>
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
                            <span>{a.time_range.start.slice(11, 19)}</span>
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
      <Dialog open={configDialogOpen} onOpenChange={setConfigDialogOpen}>
        <DialogContent className="max-h-[85vh] overflow-y-auto sm:max-w-2xl">
          <DialogHeader>
            <DialogTitle>策略参数 — {activeStrategy?.name}</DialogTitle>
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
                        // Strip unified rule keys out — only save strategy-specific params
                        const params: Record<string, unknown> = {}
                        for (const [k, v] of Object.entries(configValues)) {
                          params[k] = v
                        }
                        savePresetMutation.mutate({
                          name,
                          desc: savePresetDesc.trim(),
                          params,
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
    </div>
  )
}
