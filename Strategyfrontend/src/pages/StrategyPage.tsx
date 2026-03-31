import { useState, useMemo } from "react"
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import { useNavigate } from "react-router-dom"
import { cn } from "@/lib/utils"
import { fetchStrategies, fetchArchives, runBacktest } from "@/api/client"
import type { StrategyInfo, ArchiveInfo, RunRequest } from "@/types"
import StrategyConfigForm from "@/components/StrategyConfigForm"
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from "@/components/ui/dialog"

export default function StrategyPage() {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [selectedStrategy, setSelectedStrategy] = useState<string>("")
  const [selectedSlug, setSelectedSlug] = useState<string>("")
  const [balance, setBalance] = useState(10000)
  const [configValues, setConfigValues] = useState<Record<string, unknown>>({})
  const [settlementMode, setSettlementMode] = useState<"auto" | "yes" | "no">("auto")
  const [configDialogOpen, setConfigDialogOpen] = useState(false)

  const { data: strategies = [], isLoading: loadingStrategies } = useQuery<StrategyInfo[]>({
    queryKey: ["strategies"],
    queryFn: fetchStrategies,
  })

  const { data: archives = [], isLoading: loadingArchives } = useQuery<ArchiveInfo[]>({
    queryKey: ["archives"],
    queryFn: fetchArchives,
  })

  const activeStrategy = useMemo(
    () => strategies.find((s) => s.name === selectedStrategy),
    [strategies, selectedStrategy],
  )

  const mutation = useMutation({
    mutationFn: (req: RunRequest) => runBacktest(req),
    onSuccess: (result) => {
      queryClient.invalidateQueries({ queryKey: ["results"] })
      navigate(`/results/${result.session_id}`)
    },
  })

  function handleStrategyClick(s: StrategyInfo) {
    setSelectedStrategy(s.name)
    setConfigValues(
      Object.fromEntries(
        Object.entries(s.default_config).map(([k, v]) => [k, v]),
      ),
    )
    setConfigDialogOpen(true)
  }

  function handleRun() {
    if (!selectedStrategy || !selectedSlug) return

    // Build settlement_result based on mode
    // For "yes"/"no" we need token_ids from the selected archive
    const selectedArchive = archives.find((a) => a.slug === selectedSlug)
    let settlement_result: Record<string, number> | undefined
    if (settlementMode === "yes" && selectedArchive) {
      settlement_result = Object.fromEntries(selectedArchive.token_ids.map((tid) => [tid, 1.0]))
    } else if (settlementMode === "no" && selectedArchive) {
      settlement_result = Object.fromEntries(selectedArchive.token_ids.map((tid) => [tid, 0.0]))
    }

    mutation.mutate({
      strategy: selectedStrategy,
      slug: selectedSlug,
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
                    <span className="text-xs text-muted-foreground">v{s.version}</span>
                  </div>
                  <p className="mt-1 text-sm text-muted-foreground">{s.description}</p>
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
              {mutation.isError && (
                <p className="text-sm text-destructive">
                  回测失败: {(mutation.error as Error).message}
                </p>
              )}
            </div>
          </div>
        </div>

        {/* Right: Data source */}
        <div className="flex flex-col gap-4 lg:col-span-8">
          {/* Data source selection */}
          <div className="rounded-lg border p-4">
            <h2 className="mb-3 text-sm font-medium text-muted-foreground">数据源</h2>
            {loadingArchives ? (
              <div className="text-sm text-muted-foreground">扫描中...</div>
            ) : archives.length === 0 ? (
              <div className="text-sm text-muted-foreground">
                暂无归档数据。请先在主平台采集数据。
              </div>
            ) : (
              <div className="flex flex-col gap-2">
                {archives.map((a) => (
                  <button
                    key={a.slug}
                    onClick={() => setSelectedSlug(a.slug)}
                    className={cn(
                      "rounded-lg border p-3 text-left transition-colors",
                      selectedSlug === a.slug
                        ? "border-primary bg-primary/5"
                        : "border-border hover:border-primary/50",
                    )}
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
                      {a.slug.includes("5m") ? (
                        <>
                          <span>·</span>
                          <span className="text-blue-500">5 分钟</span>
                        </>
                      ) : a.slug.includes("15m") ? (
                        <>
                          <span>·</span>
                          <span className="text-blue-500">15 分钟</span>
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
        <DialogContent className="sm:max-w-lg">
          <DialogHeader>
            <DialogTitle>策略参数 — {activeStrategy?.name}</DialogTitle>
            <DialogDescription>
              {activeStrategy?.description}
            </DialogDescription>
          </DialogHeader>
          {activeStrategy && (
            <div className="py-2">
              <StrategyConfigForm
                defaultConfig={activeStrategy.default_config}
                values={configValues}
                onChange={setConfigValues}
              />
            </div>
          )}
        </DialogContent>
      </Dialog>
    </div>
  )
}
