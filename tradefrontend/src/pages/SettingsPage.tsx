import { useState } from "react"
import { useConfig } from "@/hooks/useTradeData"
import { useMutation, useQueryClient } from "@tanstack/react-query"
import { tradeApi } from "@/api/trade"
import { Card, CardHeader, CardTitle, CardDescription, CardContent, CardFooter } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Skeleton } from "@/components/ui/skeleton"
import { Separator } from "@/components/ui/separator"
import { Switch } from "@/components/ui/switch"
import { Badge } from "@/components/ui/badge"
import { toast } from "sonner"
import { Save, RefreshCw, AlertTriangle, Download, Layers, X } from "lucide-react"
import { cn, descText } from "@/lib/utils"

function ExecutorModeToggle() {
  const queryClient = useQueryClient()
  const { data: config } = useConfig()
  const currentMode = config?.executor_mode ?? "mock"
  const isReal = currentMode === "real"

  const modeMut = useMutation({
    mutationFn: (mode: string) => tradeApi.setExecutorMode(mode),
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ["trade", "config"] })
      toast.success(`已切换为${data.executor_mode === "real" ? "真实" : "模拟"}交易模式`)
    },
    onError: (err: Error) => {
      toast.error(`切换失败: ${err.message}`)
    },
  })

  const handleToggle = (checked: boolean) => {
    const newMode = checked ? "real" : "mock"
    modeMut.mutate(newMode)
  }

  return (
    <div className="flex items-center justify-between">
      <div className="flex items-center gap-3">
        <Badge className={cn(
          "text-xs",
          isReal
            ? "bg-red-100 text-red-700 dark:bg-red-900 dark:text-red-300"
            : "bg-blue-100 text-blue-700 dark:bg-blue-900 dark:text-blue-300",
        )}>
          {isReal ? "真实交易" : "模拟交易"}
        </Badge>
        {isReal && (
          <span className="flex items-center gap-1 text-xs text-orange-600 dark:text-orange-400">
            <AlertTriangle className="h-3 w-3" />
            真实资金交易中
          </span>
        )}
      </div>
      <div className="flex items-center gap-2">
        <Label htmlFor="mode-toggle" className="text-sm text-muted-foreground">
          模拟
        </Label>
        <Switch
          id="mode-toggle"
          checked={isReal}
          onCheckedChange={handleToggle}
          disabled={modeMut.isPending}
        />
        <Label htmlFor="mode-toggle" className="text-sm text-muted-foreground">
          真实
        </Label>
      </div>
    </div>
  )
}

export default function SettingsPage() {
  const queryClient = useQueryClient()
  const { data: config, isLoading } = useConfig()
  const [draft, setDraft] = useState<Record<string, string>>({})
  const [initialized, setInitialized] = useState(false)

  // Initialize draft from config on first load
  if (config?.current_config && !initialized) {
    const flat: Record<string, string> = {}
    for (const [k, v] of Object.entries(config.current_config)) {
      flat[k] = String(v)
    }
    setDraft(flat)
    setInitialized(true)
  }

  const updateMut = useMutation({
    mutationFn: (cfg: Record<string, unknown>) => tradeApi.updateConfig(cfg),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["trade", "config"] })
      toast.success("配置已更新")
    },
    onError: (err: Error) => {
      toast.error(`更新失败: ${err.message}`)
    },
  })

  const loadPresetMut = useMutation({
    mutationFn: (presetName: string) => tradeApi.loadPreset(presetName),
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ["trade", "config"] })
      setInitialized(false)
      const appliedCount = Object.keys(data.applied).length
      const skippedCount = data.skipped.length
      toast.success(
        `已加载预设「${data.preset_name}」：${appliedCount} 个参数已应用` +
          (skippedCount > 0 ? `，${skippedCount} 个不兼容已跳过` : ""),
      )
    },
    onError: (err: Error) => {
      toast.error(`加载预设失败: ${err.message}`)
    },
  })

  const loadCompositeMut = useMutation({
    mutationFn: (name: string) => tradeApi.loadComposite(name),
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ["trade", "config"] })
      setInitialized(false)
      toast.success(`已加载复合策略「${data.composite_name}」：${data.branches} 个分支`)
    },
    onError: (err: Error) => {
      toast.error(`加载复合策略失败: ${err.message}`)
    },
  })

  const clearCompositeMut = useMutation({
    mutationFn: () => tradeApi.clearComposite(),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["trade", "config"] })
      toast.success("已清除复合策略，恢复单策略模式")
    },
    onError: (err: Error) => {
      toast.error(`清除失败: ${err.message}`)
    },
  })

  const handleSave = () => {
    const parsed: Record<string, unknown> = {}
    for (const [k, v] of Object.entries(draft)) {
      const num = Number(v)
      parsed[k] = isNaN(num) ? v : num
    }
    updateMut.mutate(parsed)
  }

  const handleChange = (key: string, value: string) => {
    setDraft((prev) => ({ ...prev, [key]: value }))
  }

  if (isLoading) {
    return (
      <div className="flex flex-col gap-4">
        <Skeleton className="h-8 w-48" />
        <Skeleton className="h-64" />
      </div>
    )
  }

  const paramKeys = Object.keys(draft)

  return (
    <div className="flex flex-col gap-6">
      <h1 className="text-2xl font-semibold tracking-tight">策略配置</h1>

      {/* ── Executor Mode Toggle ──────────── */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">交易模式</CardTitle>
          <CardDescription>切换真实交易与模拟交易模式</CardDescription>
        </CardHeader>
        <CardContent>
          <ExecutorModeToggle />
        </CardContent>
      </Card>

      {/* ── Active Live Strategy ──────────── */}
      {config?.local_strategies && config.local_strategies.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">实时交易策略</CardTitle>
            <CardDescription>当前服务使用的实时策略</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="flex flex-wrap gap-2">
              {config.local_strategies.map((s) => (
                <span
                  key={s.name}
                  className={cn(
                    "rounded-md px-2 py-1 text-sm font-mono",
                    s.name === config.active_strategy ? "bg-primary text-primary-foreground" : "bg-muted",
                  )}
                >
                  {s.name}
                  <span className="ml-1 text-xs opacity-60">v{s.version}</span>
                  {s.name === config.active_strategy && (
                    <span className="ml-1 text-xs">✓ 运行中</span>
                  )}
                </span>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {/* ── Active Composite Strategy ──────── */}
      {config?.composite_config && (
        <Card className="border-purple-200 dark:border-purple-800">
          <CardHeader>
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Layers className="h-4 w-4 text-purple-600" />
                <CardTitle className="text-base">当前复合策略</CardTitle>
              </div>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => clearCompositeMut.mutate()}
                disabled={clearCompositeMut.isPending}
              >
                <X className="mr-1 h-3 w-3" />
                清除
              </Button>
            </div>
            <CardDescription>
              复合策略根据 BTC 动量振幅自动选择分支 — 每个 Session 独立匹配
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            <div className="flex items-center gap-4 text-sm">
              <Badge variant="outline" className="font-mono">{config.composite_config.composite_name}</Badge>
              <span className="text-muted-foreground">
                窗口: {config.composite_config.btc_windows.btc_trend_window_1}m / {config.composite_config.btc_windows.btc_trend_window_2}m
              </span>
            </div>
            <div className="space-y-2">
              <p className="text-xs text-muted-foreground mb-1">分支（按动量阈值降序匹配）</p>
              {config.composite_config.branches.map((b, i) => (
                <div key={i} className="rounded-md border px-3 py-2 space-y-1.5">
                  <div className="flex items-center gap-3 text-sm">
                    <Badge variant="secondary" className="text-xs font-mono">{b.label}</Badge>
                    <span className="text-muted-foreground">≥ {b.min_momentum}</span>
                    <span className="ml-auto font-mono text-xs text-muted-foreground">{b.preset_name}</span>
                  </div>
                  {b.config && Object.keys(b.config).length > 0 && (
                    <div className="flex flex-wrap gap-x-3 gap-y-0.5 pl-1">
                      {Object.entries(b.config).map(([k, v]) => (
                        <span key={k} className="text-xs text-muted-foreground font-mono">
                          {k}={String(v)}
                        </span>
                      ))}
                    </div>
                  )}
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {/* ── Backtest Strategies from Strategy Service ── */}
      {config?.backtest_strategies && config.backtest_strategies.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">可用回测策略</CardTitle>
            <CardDescription>
              来自策略回测服务的预设策略 — 点击「加载」将其参数应用到实时交易（下一个 Session 生效）
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="space-y-2">
              {config.backtest_strategies.map((s) => (
                <div
                  key={s.name}
                  className="flex items-center justify-between rounded-md border px-3 py-2"
                >
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-mono font-medium">{s.name}</span>
                    {s.builtin && (
                      <Badge variant="secondary" className="text-xs">内置</Badge>
                    )}
                    {descText(s.description) && (
                      <span className="text-xs text-muted-foreground">{descText(s.description)}</span>
                    )}
                  </div>
                  <Button
                    variant="outline"
                    size="sm"
                    disabled={loadPresetMut.isPending}
                    onClick={() => loadPresetMut.mutate(s.name)}
                  >
                    <Download className="mr-1 h-3 w-3" />
                    加载参数
                  </Button>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {/* ── Composite Presets from Strategy Service ── */}
      {config?.composite_presets && config.composite_presets.length > 0 && (
        <Card>
          <CardHeader>
            <div className="flex items-center gap-2">
              <Layers className="h-4 w-4 text-purple-600" />
              <CardTitle className="text-base">可用复合策略</CardTitle>
            </div>
            <CardDescription>
              复合策略：根据 BTC 双窗口动量振幅 |a1+a2| 自动匹配策略分支，每个 Session 独立决策
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              {config.composite_presets.map((cp) => (
                <div
                  key={cp.name}
                  className="rounded-md border px-3 py-2 space-y-2"
                >
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-mono font-medium">{cp.name}</span>
                      <span className="text-xs text-muted-foreground">
                        W1={cp.btc_windows.btc_trend_window_1}m W2={cp.btc_windows.btc_trend_window_2}m
                      </span>
                    </div>
                    <Button
                      variant="outline"
                      size="sm"
                      disabled={loadCompositeMut.isPending}
                      onClick={() => loadCompositeMut.mutate(cp.name)}
                    >
                      <Layers className="mr-1 h-3 w-3" />
                      加载
                    </Button>
                  </div>
                  <div className="space-y-1.5">
                    {cp.branches.map((b, i) => (
                      <div key={i} className="rounded border px-2 py-1.5 space-y-1">
                        <div className="flex items-center gap-2 text-xs">
                          <Badge variant="outline" className="font-mono">
                            {b.label} ≥{b.min_momentum}
                          </Badge>
                          <span className="text-muted-foreground font-mono">{b.preset_name}</span>
                        </div>
                        {b.config && Object.keys(b.config).length > 0 && (
                          <div className="flex flex-wrap gap-x-3 gap-y-0.5 pl-1">
                            {Object.entries(b.config).map(([k, v]) => (
                              <span key={k} className="text-xs text-muted-foreground font-mono">
                                {k}={String(v)}
                              </span>
                            ))}
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      <Separator />

      <Card>
        <CardHeader>
          <CardTitle className="text-base">策略参数</CardTitle>
          <CardDescription>
            当前运行的策略参数 — 加载回测预设后自动同步，也可手动微调（下一个 Session 生效）
          </CardDescription>
        </CardHeader>
        <CardContent>
          {paramKeys.length === 0 ? (
            <p className="py-4 text-center text-sm text-muted-foreground">暂无可配置参数</p>
          ) : (
            <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
              {paramKeys.map((key) => (
                <div key={key} className="flex flex-col gap-1.5">
                  <Label htmlFor={key} className="font-mono text-xs">
                    {key}
                  </Label>
                  <Input
                    id={key}
                    value={draft[key] ?? ""}
                    onChange={(e) => handleChange(key, e.target.value)}
                  />
                </div>
              ))}
            </div>
          )}
        </CardContent>
        <CardFooter className="flex gap-2">
          <Button onClick={handleSave} disabled={updateMut.isPending}>
            <Save data-icon="inline-start" />
            保存配置
          </Button>
          <Button
            variant="outline"
            onClick={() => {
              setInitialized(false)
              queryClient.invalidateQueries({ queryKey: ["trade", "config"] })
            }}
          >
            <RefreshCw data-icon="inline-start" />
            重新加载
          </Button>
        </CardFooter>
      </Card>
    </div>
  )
}
