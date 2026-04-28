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
import { Save, RefreshCw, AlertTriangle } from "lucide-react"
import { cn } from "@/lib/utils"

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

      {config?.strategy && config.strategy.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">可用策略</CardTitle>
            <CardDescription>已注册的实时交易策略</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="flex flex-wrap gap-2">
              {config.strategy.map((s) => (
                <span
                  key={s.name}
                  className="rounded-md bg-muted px-2 py-1 text-sm font-mono"
                >
                  {s.name}
                  <span className="ml-1 text-xs text-muted-foreground">v{s.version}</span>
                </span>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      <Separator />

      <Card>
        <CardHeader>
          <CardTitle className="text-base">策略参数</CardTitle>
          <CardDescription>修改后点击保存生效（下一个 Session 生效）</CardDescription>
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
