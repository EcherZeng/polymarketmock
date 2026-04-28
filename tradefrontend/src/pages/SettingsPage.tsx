import { useState } from "react"
import { useCatalog, useConfigState } from "@/hooks/useTradeData"
import { useMutation, useQueryClient } from "@tanstack/react-query"
import { tradeApi } from "@/api/trade"
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"
import { Switch } from "@/components/ui/switch"
import { Badge } from "@/components/ui/badge"
import { Label } from "@/components/ui/label"
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs"
import { toast } from "sonner"
import { AlertTriangle, Layers, CheckCircle2, X } from "lucide-react"
import { cn, descText } from "@/lib/utils"

function ExecutorModeToggle() {
  const queryClient = useQueryClient()
  const { data: config } = useConfigState()
  const currentMode = config?.executor_mode ?? "mock"
  const isReal = currentMode === "real"

  const modeMut = useMutation({
    mutationFn: (mode: string) => tradeApi.setExecutorMode(mode),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["trade", "config-state"] })
      toast.success(`已切换为${isReal ? "模拟" : "真实"}交易模式`)
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
  const { data: catalog, isLoading: catalogLoading } = useCatalog()
  const { data: config, isLoading: stateLoading } = useConfigState()
  const [strategyTab, setStrategyTab] = useState<"single" | "composite">("composite")

  const loadPresetMut = useMutation({
    mutationFn: (presetName: string) => tradeApi.loadPreset(presetName),
    onSuccess: (data) => {
      queryClient.setQueryData(["trade", "config-state"], data.state)
      toast.success(`已加载单一策略「${data.preset_name}」，下一场次生效`)
    },
    onError: (err: Error) => {
      toast.error(`加载失败: ${err.message}`)
    },
  })

  const loadCompositeMut = useMutation({
    mutationFn: (name: string) => tradeApi.loadComposite(name),
    onSuccess: (data) => {
      queryClient.setQueryData(["trade", "config-state"], data.state)
      toast.success(`已加载复合策略「${data.state.active_preset_name}」，下一场次生效`)
    },
    onError: (err: Error) => {
      toast.error(`加载复合策略失败: ${err.message}`)
    },
  })

  const clearMut = useMutation({
    mutationFn: () => tradeApi.clearComposite(),
    onSuccess: (data) => {
      queryClient.setQueryData(["trade", "config-state"], data.state)
      toast.success("已清除当前策略")
    },
    onError: (err: Error) => {
      toast.error(`清除失败: ${err.message}`)
    },
  })

  const isLoading = catalogLoading || stateLoading

  if (isLoading) {
    return (
      <div className="flex flex-col gap-4">
        <Skeleton className="h-8 w-48" />
        <Skeleton className="h-64" />
      </div>
    )
  }

  const presetName = config?.active_preset_name
  const presetType = config?.active_preset_type ?? "none"
  const isActive = presetType !== "none" && !!presetName
  const isPending = loadPresetMut.isPending || loadCompositeMut.isPending

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

      {/* ── Active Strategy ──────────── */}
      <Card className={cn(
        isActive && presetType === "composite" && "border-purple-200 dark:border-purple-800",
        isActive && presetType === "single" && "border-blue-200 dark:border-blue-800",
      )}>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              {presetType === "composite" && <Layers className="h-4 w-4 text-purple-600" />}
              {presetType === "single" && <CheckCircle2 className="h-4 w-4 text-blue-600" />}
              <CardTitle className="text-base">当前策略</CardTitle>
            </div>
            {isActive && (
              <Button
                variant="ghost"
                size="sm"
                onClick={() => clearMut.mutate()}
                disabled={clearMut.isPending}
              >
                <X className="mr-1 h-3 w-3" />
                清除
              </Button>
            )}
          </div>
          <CardDescription>
            {isActive
              ? `已加载${presetType === "composite" ? "复合" : "单一"}策略 — 下一个 Session 自动应用`
              : "尚未加载策略 — 请从下方选择一个策略加载"}
          </CardDescription>
        </CardHeader>
        <CardContent>
          {!isActive ? (
            <p className="py-2 text-center text-sm text-muted-foreground">无活跃策略</p>
          ) : presetType === "composite" && config?.composite_config ? (
            <div className="space-y-3">
              <div className="flex items-center gap-3 text-sm">
                <Badge variant="outline" className="font-mono">{config.composite_config.composite_name}</Badge>
                <span className="text-muted-foreground">
                  BTC 窗口: W1={config.composite_config.btc_windows.btc_trend_window_1}m / W2={config.composite_config.btc_windows.btc_trend_window_2}m
                </span>
              </div>
              <div className="space-y-2">
                <p className="text-xs text-muted-foreground">分支（按 BTC 动量振幅 |a1+a2| 降序匹配，命中即用该分支参数入场）</p>
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
            </div>
          ) : presetType === "single" ? (
            <div className="space-y-3">
              <div className="flex items-center gap-2 text-sm">
                <Badge variant="outline" className="font-mono">{presetName}</Badge>
              </div>
              {config?.current_config && Object.keys(config.current_config).length > 0 && (
                <div className="flex flex-wrap gap-x-4 gap-y-1">
                  {Object.entries(config.current_config).map(([k, v]) => (
                    <span key={k} className="text-xs text-muted-foreground font-mono">
                      {k}={String(v)}
                    </span>
                  ))}
                </div>
              )}
            </div>
          ) : null}
        </CardContent>
      </Card>

      {/* ── Strategy Selector ──────────── */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">策略选择</CardTitle>
          <CardDescription>
            从策略服务加载策略 — 复合策略根据每场 BTC 动量自动匹配分支，单一策略所有场次使用相同参数
          </CardDescription>
        </CardHeader>
        <CardContent>
          <Tabs value={strategyTab} onValueChange={(v) => setStrategyTab(v as "single" | "composite")}>
            <TabsList className="mb-4">
              <TabsTrigger value="composite" className="gap-1">
                <Layers className="h-3.5 w-3.5" />
                复合策略
              </TabsTrigger>
              <TabsTrigger value="single">单一策略</TabsTrigger>
            </TabsList>

            <TabsContent value="composite">
              {!catalog?.composite_presets || catalog.composite_presets.length === 0 ? (
                <p className="py-4 text-center text-sm text-muted-foreground">
                  暂无复合策略 — 请在策略回测服务中创建
                </p>
              ) : (
                <div className="space-y-3">
                  {catalog.composite_presets.map((cp) => {
                    const isLoaded = presetType === "composite" && presetName === cp.name
                    return (
                      <div
                        key={cp.name}
                        className={cn(
                          "rounded-md border px-3 py-3 space-y-2",
                          isLoaded && "border-purple-400 bg-purple-50/50 dark:bg-purple-950/20",
                        )}
                      >
                        <div className="flex items-center justify-between">
                          <div className="flex items-center gap-2">
                            <span className="text-sm font-mono font-medium">{cp.name}</span>
                            {cp.description && (
                              <span className="text-xs text-muted-foreground">{cp.description}</span>
                            )}
                            <span className="text-xs text-muted-foreground">
                              W1={cp.btc_windows.btc_trend_window_1}m W2={cp.btc_windows.btc_trend_window_2}m
                            </span>
                            {isLoaded && <Badge className="text-xs bg-purple-600">当前</Badge>}
                          </div>
                          <Button
                            variant={isLoaded ? "secondary" : "outline"}
                            size="sm"
                            disabled={isPending || isLoaded}
                            onClick={() => loadCompositeMut.mutate(cp.name)}
                          >
                            {isLoaded ? "已加载" : "加载"}
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
                    )
                  })}
                </div>
              )}
            </TabsContent>

            <TabsContent value="single">
              {!catalog?.backtest_strategies || catalog.backtest_strategies.length === 0 ? (
                <p className="py-4 text-center text-sm text-muted-foreground">
                  暂无单一策略 — 请在策略回测服务中创建预设
                </p>
              ) : (
                <div className="space-y-2">
                  {catalog.backtest_strategies.map((s) => {
                    const isLoaded = presetType === "single" && presetName === s.name
                    return (
                      <div
                        key={s.name}
                        className={cn(
                          "flex items-center justify-between rounded-md border px-3 py-2",
                          isLoaded && "border-blue-400 bg-blue-50/50 dark:bg-blue-950/20",
                        )}
                      >
                        <div className="flex items-center gap-2">
                          <span className="text-sm font-mono font-medium">{s.name}</span>
                          {s.builtin && (
                            <Badge variant="secondary" className="text-xs">内置</Badge>
                          )}
                          {descText(s.description) && (
                            <span className="text-xs text-muted-foreground">{descText(s.description)}</span>
                          )}
                          {isLoaded && <Badge className="text-xs bg-blue-600">当前</Badge>}
                        </div>
                        <Button
                          variant={isLoaded ? "secondary" : "outline"}
                          size="sm"
                          disabled={isPending || isLoaded}
                          onClick={() => loadPresetMut.mutate(s.name)}
                        >
                          {isLoaded ? "已加载" : "加载"}
                        </Button>
                      </div>
                    )
                  })}
                </div>
              )}
            </TabsContent>
          </Tabs>
        </CardContent>
      </Card>
    </div>
  )
}
