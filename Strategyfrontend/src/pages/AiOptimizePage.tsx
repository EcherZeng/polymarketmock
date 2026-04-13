import { useState, useMemo } from "react"
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import { Link, useNavigate } from "react-router-dom"
import { cn } from "@/lib/utils"
import {
  fetchStrategies,
  fetchPortfolios,
  fetchAiOptimizeTasks,
  submitAiOptimize,
  stopAiOptimize,
  fetchAiModels,
} from "@/api/client"
import { PARAM_SCHEMA, PARAM_GROUPS } from "@/config/paramSchema"
import type {
  StrategyInfo,
  Portfolio,
  AiOptimizeTask,
  AiOptimizeRequest,
  AiModelsResponse,
  I18nLabel,
} from "@/types"
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip"

function t(label: I18nLabel | string | undefined): string {
  if (!label) return ""
  if (typeof label === "string") return label
  return label.zh || label.en
}

const statusLabel: Record<string, string> = {
  running: "运行中",
  completed: "已完成",
  cancelled: "已停止",
  failed: "失败",
  interrupted: "已中断",
}

const statusColor: Record<string, string> = {
  running: "bg-blue-100 text-blue-700",
  completed: "bg-emerald-100 text-emerald-700",
  cancelled: "bg-amber-100 text-amber-700",
  failed: "bg-red-100 text-red-700",
  interrupted: "bg-orange-100 text-orange-700",
}

const PCT_METRICS = new Set(["total_return_pct", "win_rate", "max_drawdown", "hold_to_settlement_ratio", "annualized_return"])

function fmtMetric(target: string, value: number): string {
  if (PCT_METRICS.has(target)) return `${(value * 100).toFixed(2)}%`
  return value.toFixed(4)
}

const optimizeTargets = [
  { value: "sharpe_ratio", label: "Sharpe Ratio", desc: "风险调整后收益指标。每承担 1 单位波动率获得的超额回报，值越高说明收益/风险比越优。通常 >1 为可接受，>2 为优秀。" },
  { value: "total_return_pct", label: "总收益率 %", desc: "回测期间总盈亏占初始本金的百分比。" },
  { value: "profit_factor", label: "盈亏比", desc: "总盈利 / 总亏损。>1 表示盈利大于亏损，>2 为优秀。" },
  { value: "win_rate", label: "胜率", desc: "盈利交易次数占总交易次数的比例。" },
  { value: "sortino_ratio", label: "Sortino Ratio", desc: "类似 Sharpe 但仅考虑下行波动率（只惩罚亏损方向的波动），对上行波动不做惩罚，更适合评估非对称收益分布的策略。" },
  { value: "calmar_ratio", label: "Calmar Ratio", desc: "年化收益率 / 最大回撤。衡量每承受 1% 最大回撤所获得的年化回报，值越高说明策略在控制极端亏损的同时仍能获得可观收益。" },
]

export default function AiOptimizePage() {
  const navigate = useNavigate()
  const queryClient = useQueryClient()

  // ── Form state ──────────────────────────────────────────────────────────
  const [dialogOpen, setDialogOpen] = useState(false)
  const [selectedStrategy, setSelectedStrategy] = useState("")
  const [selectedPortfolioId, setSelectedPortfolioId] = useState("")
  const [optimizeTarget, setOptimizeTarget] = useState("sharpe_ratio")
  const [maxRounds, setMaxRounds] = useState(5)
  const [runsPerRound, setRunsPerRound] = useState(5)
  const [balance, setBalance] = useState(10000)
  const [llmModel, setLlmModel] = useState("")
  const [selectedParamKeys, setSelectedParamKeys] = useState<Set<string>>(new Set())

  // ── Queries ─────────────────────────────────────────────────────────────
  const { data: strategies = [] } = useQuery<StrategyInfo[]>({
    queryKey: ["strategies"],
    queryFn: fetchStrategies,
  })

  const { data: portfolios = [] } = useQuery<Portfolio[]>({
    queryKey: ["portfolios"],
    queryFn: fetchPortfolios,
  })

  const { data: tasks = [], isLoading } = useQuery<AiOptimizeTask[]>({
    queryKey: ["aiOptimizeTasks"],
    queryFn: fetchAiOptimizeTasks,
    refetchInterval: (query) => {
      const data = query.state.data
      return data?.some((t) => t.status === "running") ? 3000 : false
    },
  })

  const { data: modelsData } = useQuery<AiModelsResponse>({
    queryKey: ["aiModels"],
    queryFn: fetchAiModels,
  })

  const sortedTasks = useMemo(
    () => [...tasks].sort((a, b) => b.created_at.localeCompare(a.created_at)),
    [tasks],
  )

  // ── Derived ─────────────────────────────────────────────────────────────
  const paramSchema = PARAM_SCHEMA
  const activeStrategy = strategies.find((s) => s.name === selectedStrategy)
  const selectedPortfolio = portfolios.find((p) => p.portfolio_id === selectedPortfolioId)

  // Tunable params: non-bool, non-hidden params that exist in the selected strategy's default_config,
  // excluding child params whose parent toggle is OFF in the strategy config.
  const tunableParams = useMemo(() => {
    if (!activeStrategy) return []
    const strategyKeys = new Set(Object.keys(activeStrategy.default_config))
    const toggleOffKeys = new Set(
      Object.entries(paramSchema)
        .filter(([k, s]) => s.type === "bool" && strategyKeys.has(k) && !activeStrategy.default_config[k])
        .map(([k]) => k)
    )
    return Object.entries(paramSchema)
      .filter(([key, info]) => {
        if (info.type === "bool") return false
        if (info.pool_hidden) return false
        if (!strategyKeys.has(key)) return false
        // Exclude child params whose parent toggle is off
        const deps = info.depends_on ? (Array.isArray(info.depends_on) ? info.depends_on : [info.depends_on]) : []
        if (deps.some(d => toggleOffKeys.has(d))) return false
        return true
      })
      .map(([key, info]) => ({ key, ...info }))
  }, [paramSchema, activeStrategy])

  // Unique slugs from selected portfolio
  const portfolioSlugs = useMemo(() => {
    if (!selectedPortfolio) return []
    return [...new Set(selectedPortfolio.items.map((it) => it.slug))]
  }, [selectedPortfolio])

  // ── Mutations ───────────────────────────────────────────────────────────
  const submitMutation = useMutation({
    mutationFn: (req: AiOptimizeRequest) => submitAiOptimize(req),
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ["aiOptimizeTasks"] })
      setDialogOpen(false)
      navigate(`/ai-optimize/${data.task_id}`)
    },
  })

  const stopMutation = useMutation({
    mutationFn: (taskId: string) => stopAiOptimize(taskId),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["aiOptimizeTasks"] }),
  })

  function buildDefaultSelectedKeys(params: typeof tunableParams): Set<string> {
    return new Set(params.filter((p) => p.group !== "risk").map((p) => p.key))
  }

  // ── Handlers ────────────────────────────────────────────────────────────
  function handleSelectStrategy(name: string) {
    setSelectedStrategy(name)
    // Recompute tunable params for the newly selected strategy inline
    const strat = strategies.find((s) => s.name === name)
    if (!strat) { setSelectedParamKeys(new Set()); return }
    const strategyKeys = new Set(Object.keys(strat.default_config))
    const toggleOffKeys = new Set(
      Object.entries(paramSchema)
        .filter(([k, s]) => s.type === "bool" && strategyKeys.has(k) && !strat.default_config[k])
        .map(([k]) => k)
    )
    const newTunable = Object.entries(paramSchema)
      .filter(([key, info]) => {
        if (info.type === "bool") return false
        if (info.pool_hidden) return false
        if (!strategyKeys.has(key)) return false
        const deps = info.depends_on ? (Array.isArray(info.depends_on) ? info.depends_on : [info.depends_on]) : []
        if (deps.some(d => toggleOffKeys.has(d))) return false
        return true
      })
      .map(([key, info]) => ({ key, ...info }))
    setSelectedParamKeys(buildDefaultSelectedKeys(newTunable))
  }

  function handleOpenDialog() {
    const firstStrategy = selectedStrategy || strategies[0]?.name || ""
    if (!selectedStrategy && firstStrategy) {
      handleSelectStrategy(firstStrategy)
    } else if (selectedParamKeys.size === 0 && tunableParams.length > 0) {
      setSelectedParamKeys(buildDefaultSelectedKeys(tunableParams))
    }
    if (!llmModel && modelsData) setLlmModel(modelsData.default_model)
    setDialogOpen(true)
  }

  function handleSubmit() {
    if (!selectedStrategy || !selectedPortfolio || portfolioSlugs.length === 0) return
    if (!llmModel) return

    const fullConfig = activeStrategy?.default_config ?? {}

    // Filter active params: exclude bool toggles that are OFF and their dependent children
    const disabledToggles = new Set(
      Object.entries(paramSchema)
        .filter(([k, s]) => s.type === "bool" && k in fullConfig && !fullConfig[k])
        .map(([k]) => k),
    )
    const activeKeys = Object.keys(fullConfig).filter((k) => {
      if (disabledToggles.has(k)) return false
      const info = paramSchema[k]
      const deps = info?.depends_on ? (Array.isArray(info.depends_on) ? info.depends_on : [info.depends_on]) : []
      if (deps.some(d => disabledToggles.has(d))) return false
      return true
    })
    const baseConfig: Record<string, unknown> = {}
    for (const k of activeKeys) baseConfig[k] = fullConfig[k]

    const req: AiOptimizeRequest = {
      strategy: selectedStrategy,
      slugs: portfolioSlugs,
      base_config: baseConfig,
      optimize_target: optimizeTarget,
      max_rounds: maxRounds,
      runs_per_round: runsPerRound,
      initial_balance: balance,
      param_keys: [...selectedParamKeys],
      active_params: activeKeys,
      llm_model: llmModel,
    }

    submitMutation.mutate(req)
  }

  function toggleParamKey(key: string) {
    setSelectedParamKeys((prev) => {
      const next = new Set(prev)
      if (next.has(key)) next.delete(key)
      else next.add(key)
      return next
    })
  }

  // ── Render ──────────────────────────────────────────────────────────────
  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">AI 参数优化</h1>
          <p className="text-sm text-muted-foreground">
            LLM 驱动的多轮迭代参数探索 · {tasks.length} 个任务
          </p>
        </div>
        <button
          onClick={handleOpenDialog}
          className="rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90"
        >
          新建优化任务
        </button>
      </div>

      {/* ── Task list ──────────────────────────────────────────────────── */}
      {isLoading ? (
        <div className="py-12 text-center text-muted-foreground">加载中...</div>
      ) : sortedTasks.length === 0 ? (
        <div className="flex flex-col items-center gap-3 py-12 text-muted-foreground">
          <p>暂无优化任务</p>
          <p className="text-xs">点击「新建优化任务」开始 AI 参数探索</p>
        </div>
      ) : (
        <div className="flex flex-col gap-3">
          {sortedTasks.map((t) => {
            const progress = t.total_runs > 0 ? (t.completed_runs / t.total_runs) * 100 : 0
            return (
              <Link
                key={t.task_id}
                to={`/ai-optimize/${t.task_id}`}
                className="rounded-lg border p-4 transition-colors hover:border-primary/50"
              >
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <span className="font-mono text-sm font-medium">{t.task_id}</span>
                    <span
                      className={cn(
                        "rounded-full px-2 py-0.5 text-xs font-medium",
                        statusColor[t.status] ?? "bg-muted text-muted-foreground",
                      )}
                    >
                      {statusLabel[t.status] ?? t.status}
                    </span>
                  </div>
                  <span className="text-xs text-muted-foreground">
                    {t.created_at.replace("T", " ").slice(0, 19)}
                  </span>
                </div>

                <div className="mt-2 flex items-center gap-4 text-sm text-muted-foreground">
                  <span>策略: <span className="font-medium text-foreground">{t.strategy}</span></span>
                  <span>·</span>
                  <span>目标: <span className="font-medium text-foreground">{t.optimize_target}</span></span>
                  <span>·</span>
                  <span>轮次: {t.current_round}/{t.max_rounds}</span>
                  <span>·</span>
                  <span>回测: {t.completed_runs}/{t.total_runs}</span>
                </div>

                {t.best_metric !== null && (
                  <div className="mt-1 text-sm">
                    最优 {t.optimize_target}: <span className="font-medium text-emerald-600">{fmtMetric(t.optimize_target, t.best_metric)}</span>
                    <span className="ml-1 text-xs text-muted-foreground">
                      ({t.best_total_trades}笔{t.best_total_trades < 5 ? " · 低可信" : ""})
                    </span>
                  </div>
                )}

                {/* Progress bar */}
                <div className="mt-2 h-1.5 w-full overflow-hidden rounded-full bg-muted">
                  <div
                    className={cn(
                      "h-full rounded-full transition-all duration-300",
                      t.status === "completed" ? "bg-emerald-500"
                        : t.status === "failed" ? "bg-red-400"
                        : "bg-blue-500",
                    )}
                    style={{ width: `${progress}%` }}
                  />
                </div>

                {t.status === "running" && (
                  <div className="mt-2 flex justify-end">
                    <button
                      onClick={(e) => {
                        e.preventDefault()
                        stopMutation.mutate(t.task_id)
                      }}
                      className="rounded px-3 py-1 text-xs text-red-600 hover:bg-red-50"
                    >
                      停止
                    </button>
                  </div>
                )}
              </Link>
            )
          })}
        </div>
      )}

      {/* ── Submit dialog ──────────────────────────────────────────────── */}
      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent className="max-h-[85vh] max-w-2xl overflow-y-auto">
          <DialogHeader>
            <DialogTitle>新建 AI 优化任务</DialogTitle>
          </DialogHeader>

          <div className="flex flex-col gap-5 py-2">
            {/* Strategy selection */}
            <div className="flex flex-col gap-1.5">
              <label className="text-sm font-medium">策略</label>
              <select
                value={selectedStrategy}
                onChange={(e) => handleSelectStrategy(e.target.value)}
                className="rounded-md border bg-background px-3 py-2 text-sm"
              >
                <option value="">选择策略...</option>
                {strategies.map((s) => (
                  <option key={s.name} value={s.name}>{s.name}</option>
                ))}
              </select>
            </div>

            {/* Portfolio (data source) selection */}
            <div className="flex flex-col gap-1.5">
              <label className="text-sm font-medium">数据源组合 (Portfolio)</label>
              <select
                value={selectedPortfolioId}
                onChange={(e) => setSelectedPortfolioId(e.target.value)}
                className="rounded-md border bg-background px-3 py-2 text-sm"
              >
                <option value="">选择组合...</option>
                {portfolios.map((p) => (
                  <option key={p.portfolio_id} value={p.portfolio_id}>
                    {p.name} ({p.items.length} 项)
                  </option>
                ))}
              </select>
              {selectedPortfolio && (
                <p className="text-xs text-muted-foreground">
                  将使用 {portfolioSlugs.length} 个数据源: {portfolioSlugs.slice(0, 3).join(", ")}
                  {portfolioSlugs.length > 3 && ` 等`}
                </p>
              )}
            </div>

            {/* Optimize target */}
            <div className="flex flex-col gap-1.5">
              <label className="text-sm font-medium">优化目标</label>
              <select
                value={optimizeTarget}
                onChange={(e) => setOptimizeTarget(e.target.value)}
                className="rounded-md border bg-background px-3 py-2 text-sm"
              >
                {optimizeTargets.map((t) => (
                  <option key={t.value} value={t.value}>{t.label}</option>
                ))}
              </select>
              {(() => {
                const target = optimizeTargets.find((x) => x.value === optimizeTarget)
                return target?.desc ? (
                  <div className="flex items-start gap-1.5 mt-0.5">
                    <Tooltip>
                      <TooltipTrigger asChild>
                        <span className="mt-0.5 inline-flex h-4 w-4 shrink-0 cursor-help items-center justify-center rounded-full border text-[10px] font-medium text-muted-foreground">
                          i
                        </span>
                      </TooltipTrigger>
                      <TooltipContent side="right" className="max-w-xs text-xs">
                        {target.desc}
                      </TooltipContent>
                    </Tooltip>
                    <p className="text-xs text-muted-foreground">{target.desc}</p>
                  </div>
                ) : null
              })()}
            </div>

            {/* Rounds & runs */}
            <div className="grid grid-cols-3 gap-4">
              <div className="flex flex-col gap-1.5">
                <label className="text-sm font-medium">最大轮数</label>
                <input
                  type="number"
                  min={1}
                  max={20}
                  value={maxRounds}
                  onChange={(e) => setMaxRounds(Number(e.target.value))}
                  className="rounded-md border bg-background px-3 py-2 text-sm"
                />
              </div>
              <div className="flex flex-col gap-1.5">
                <label className="text-sm font-medium">每轮参数组数</label>
                <input
                  type="number"
                  min={1}
                  max={20}
                  value={runsPerRound}
                  onChange={(e) => setRunsPerRound(Number(e.target.value))}
                  className="rounded-md border bg-background px-3 py-2 text-sm"
                />
              </div>
              <div className="flex flex-col gap-1.5">
                <label className="text-sm font-medium">初始余额</label>
                <input
                  type="number"
                  min={1}
                  value={balance}
                  onChange={(e) => setBalance(Number(e.target.value))}
                  className="rounded-md border bg-background px-3 py-2 text-sm"
                />
              </div>
            </div>

            <p className="text-xs text-muted-foreground">
              预计总回测次数: {portfolioSlugs.length + maxRounds * runsPerRound * portfolioSlugs.length} 次
              (基准 1×{portfolioSlugs.length} + AI {maxRounds} 轮×{runsPerRound} 组×{portfolioSlugs.length} 数据源)
            </p>

            {/* Tunable parameters */}
            <div className="flex flex-col gap-1.5">
              <label className="text-sm font-medium">AI 可调参数</label>
              <p className="text-xs text-muted-foreground">
                仅显示所选策略中存在的参数（bool 开关及未启用开关的子参数已排除）
              </p>
              {!activeStrategy ? (
                <p className="rounded-md border border-dashed p-3 text-center text-xs text-muted-foreground">
                  请先选择策略
                </p>
              ) : tunableParams.length === 0 ? (
                <p className="rounded-md border border-dashed p-3 text-center text-xs text-muted-foreground">
                  该策略无可调数值参数
                </p>
              ) : (
                <div className="rounded-md border p-3 max-h-52 overflow-y-auto">
                  {/* Group by schema group */}
                  {(() => {
                    const groups = new Map<string, typeof tunableParams>()
                    for (const p of tunableParams) {
                      if (!groups.has(p.group)) groups.set(p.group, [])
                      groups.get(p.group)!.push(p)
                    }
                    const groupDefs = PARAM_GROUPS
                    const sorted = [...groups.entries()].sort((a, b) =>
                      (groupDefs[a[0]]?.order ?? 99) - (groupDefs[b[0]]?.order ?? 99)
                    )
                    return sorted.map(([grpKey, params]) => (
                      <div key={grpKey} className="mb-2 last:mb-0">
                        <p className="mb-1 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
                          {groupDefs[grpKey] ? t(groupDefs[grpKey]) : grpKey}
                        </p>
                        <div className="grid grid-cols-2 gap-x-4 gap-y-1">
                          {params.map((p) => (
                            <label key={p.key} className="flex items-center gap-2 text-sm cursor-pointer">
                              <input
                                type="checkbox"
                                checked={selectedParamKeys.has(p.key)}
                                onChange={() => toggleParamKey(p.key)}
                                className="rounded"
                              />
                              <span className="truncate">{t(p.label)}</span>
                            </label>
                          ))}
                        </div>
                      </div>
                    ))
                  })()}
                  <div className="mt-2 flex gap-2 border-t pt-2">
                    <button
                      type="button"
                      onClick={() => setSelectedParamKeys(new Set(tunableParams.map((p) => p.key)))}
                      className="text-xs text-primary hover:underline"
                    >
                      全选
                    </button>
                    <button
                      type="button"
                      onClick={() => setSelectedParamKeys(new Set())}
                      className="text-xs text-muted-foreground hover:underline"
                    >
                      清空
                    </button>
                    <span className="ml-auto text-xs text-muted-foreground">
                      已选 {selectedParamKeys.size} / {tunableParams.length}
                    </span>
                  </div>
                </div>
              )}
            </div>

            {/* LLM model */}
            <div className="flex flex-col gap-1.5">
              <label className="text-sm font-medium">LLM 模型</label>
              <select
                value={llmModel}
                onChange={(e) => setLlmModel(e.target.value)}
                className="rounded-md border bg-background px-3 py-2 text-sm"
              >
                {(modelsData?.models ?? []).map((m) => (
                  <option key={m} value={m}>{m}</option>
                ))}
              </select>
              {modelsData && !modelsData.api_key_configured && (
                <p className="text-xs text-amber-600">
                  后端未配置 API Key（环境变量 STRATEGY_LLM_API_KEY），提交将失败
                </p>
              )}
            </div>

            {/* Submit */}
            <button
              onClick={handleSubmit}
              disabled={
                !selectedStrategy ||
                !selectedPortfolioId ||
                portfolioSlugs.length === 0 ||
                !llmModel ||
                submitMutation.isPending
              }
              className={cn(
                "w-full rounded-md px-4 py-2.5 text-sm font-medium text-primary-foreground",
                "bg-primary hover:bg-primary/90 disabled:opacity-50 disabled:cursor-not-allowed",
              )}
            >
              {submitMutation.isPending ? "提交中..." : "开始优化"}
            </button>

            {submitMutation.isError && (
              <p className="text-sm text-red-500">
                提交失败: {(submitMutation.error as Error).message}
              </p>
            )}
          </div>
        </DialogContent>
      </Dialog>
    </div>
  )
}
