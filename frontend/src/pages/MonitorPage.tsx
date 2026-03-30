import { useEffect, useRef, useState } from "react"
import { useQuery } from "@tanstack/react-query"
import { fetchLogs, fetchMetrics } from "@/api/client"
import type { LogEntry, MetricsSnapshot } from "@/types"
import { Card, CardContent } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Separator } from "@/components/ui/separator"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { Switch } from "@/components/ui/switch"
import { cn } from "@/lib/utils"
import { Wifi, WifiOff } from "lucide-react"

const LEVEL_COLORS: Record<string, string> = {
  DEBUG: "text-muted-foreground",
  INFO: "text-blue-500",
  WARNING: "text-yellow-500",
  ERROR: "text-red-500",
  CRITICAL: "text-red-700 font-bold",
}

const LEVEL_BADGE: Record<string, string> = {
  DEBUG: "bg-muted text-muted-foreground",
  INFO: "bg-blue-500/15 text-blue-600",
  WARNING: "bg-yellow-500/15 text-yellow-600",
  ERROR: "bg-red-500/15 text-red-600",
  CRITICAL: "bg-red-700/15 text-red-700",
}

function formatUptime(seconds: number): string {
  const h = Math.floor(seconds / 3600)
  const m = Math.floor((seconds % 3600) / 60)
  const s = Math.floor(seconds % 60)
  if (h > 0) return `${h}h ${m}m ${s}s`
  if (m > 0) return `${m}m ${s}s`
  return `${s}s`
}

export default function MonitorPage() {
  const [levelFilter, setLevelFilter] = useState<string>("ALL")
  const [moduleFilter, setModuleFilter] = useState("")
  const [autoRefresh, setAutoRefresh] = useState(true)
  const scrollRef = useRef<HTMLDivElement>(null)
  const autoScrollRef = useRef(true)

  // ── REST polling ─────────────────────────────────────────

  const { data: logs } = useQuery({
    queryKey: ["logs", levelFilter, moduleFilter],
    queryFn: () =>
      fetchLogs(
        500,
        levelFilter === "ALL" ? undefined : levelFilter,
        moduleFilter || undefined,
      ),
    refetchInterval: autoRefresh ? 2000 : false,
  })

  const { data: metricsData } = useQuery<MetricsSnapshot>({
    queryKey: ["metrics"],
    queryFn: fetchMetrics,
    refetchInterval: autoRefresh ? 3000 : false,
  })

  // Auto-scroll to bottom when logs update
  useEffect(() => {
    if (autoScrollRef.current && scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight
    }
  }, [logs])

  const filteredLogs = logs ?? []
  const modules = Array.from(new Set(filteredLogs.map((l) => l.module))).sort()

  // ── Metrics cards ────────────────────────────────────────

  const counters = metricsData?.counters ?? {}
  const gauges = metricsData?.gauges ?? {}

  return (
    <div className="flex flex-col gap-4">
      <h1 className="text-2xl font-bold tracking-tight">Monitor</h1>

      {/* ── Metrics ─────────────────────────────────── */}
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
        <MetricCard
          label="Uptime"
          value={formatUptime(metricsData?.uptime_seconds ?? 0)}
        />
        <MetricCard
          label="WS Upstream"
          value={
            <span className="flex items-center gap-1.5">
              {gauges["ws.upstream_connected"] ? (
                <>
                  <Wifi className="text-green-500" /> Connected
                </>
              ) : (
                <>
                  <WifiOff className="text-red-500" /> Disconnected
                </>
              )}
            </span>
          }
        />
        <MetricCard
          label="WS Clients"
          value={gauges["ws.frontend_clients"] ?? 0}
        />
        <MetricCard
          label="Subscribed Assets"
          value={gauges["ws.subscribed_assets"] ?? 0}
        />
        <MetricCard
          label="WS Messages"
          value={counters["ws.messages_received"] ?? 0}
        />
        <MetricCard
          label="Orders Filled"
          value={
            (counters["orders.market_filled"] ?? 0) +
            (counters["orders.limit_filled"] ?? 0)
          }
        />
      </div>

      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <MetricCard
          label="API Calls"
          value={counters["proxy.api_calls"] ?? 0}
        />
        <MetricCard
          label="Market Orders"
          value={counters["orders.market_filled"] ?? 0}
        />
        <MetricCard
          label="Limit Orders"
          value={counters["orders.limit_filled"] ?? 0}
        />
        <MetricCard
          label="Log Buffer"
          value={`${metricsData?.log_buffer_size ?? 0} entries`}
        />
      </div>

      <Separator />

      {/* ── Log controls ───────────────────────────── */}
      <div className="flex flex-wrap items-center gap-3">
        <div className="flex items-center gap-2">
          <Switch checked={autoRefresh} onCheckedChange={setAutoRefresh} />
          <span className="text-sm">Auto-refresh (2s)</span>
        </div>

        <Select value={levelFilter} onValueChange={setLevelFilter}>
          <SelectTrigger className="w-32">
            <SelectValue placeholder="Level" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="ALL">All Levels</SelectItem>
            <SelectItem value="DEBUG">DEBUG</SelectItem>
            <SelectItem value="INFO">INFO</SelectItem>
            <SelectItem value="WARNING">WARNING</SelectItem>
            <SelectItem value="ERROR">ERROR</SelectItem>
          </SelectContent>
        </Select>

        <Select
          value={moduleFilter || "__all__"}
          onValueChange={(v) => setModuleFilter(v === "__all__" ? "" : v)}
        >
          <SelectTrigger className="w-48">
            <SelectValue placeholder="Module" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="__all__">All Modules</SelectItem>
            {modules.map((m) => (
              <SelectItem key={m} value={m}>
                {m}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>

        <div className="flex items-center gap-2">
          <Switch
            checked={autoScrollRef.current}
            onCheckedChange={(v) => { autoScrollRef.current = v }}
          />
          <span className="text-sm">Auto-scroll</span>
        </div>

        <span className="ml-auto text-xs text-muted-foreground">
          {filteredLogs.length} entries
        </span>
      </div>

      {/* ── Log entries ────────────────────────────── */}
      <Card>
        <CardContent className="p-0">
          <div
            ref={scrollRef}
            className="h-[60vh] overflow-y-auto font-mono text-xs"
          >
            <table className="w-full">
              <thead className="sticky top-0 bg-background">
                <tr className="border-b text-left text-muted-foreground">
                  <th className="w-44 px-3 py-2">Time</th>
                  <th className="w-20 px-2 py-2">Level</th>
                  <th className="w-52 px-2 py-2">Module</th>
                  <th className="px-2 py-2">Message</th>
                </tr>
              </thead>
              <tbody>
                {filteredLogs.map((log, i) => (
                  <tr
                    key={i}
                    className={cn(
                      "border-b border-border/50 hover:bg-muted/50",
                      log.level === "ERROR" && "bg-red-500/5",
                      log.level === "WARNING" && "bg-yellow-500/5",
                    )}
                  >
                    <td className="whitespace-nowrap px-3 py-1 text-muted-foreground">
                      {log.ts.slice(11, 23)}
                    </td>
                    <td className="px-2 py-1">
                      <span
                        className={cn(
                          "inline-block rounded px-1.5 py-0.5 text-[10px] font-medium",
                          LEVEL_BADGE[log.level] ?? "",
                        )}
                      >
                        {log.level}
                      </span>
                    </td>
                    <td className="truncate px-2 py-1 text-muted-foreground">
                      {log.module}
                    </td>
                    <td className={cn("px-2 py-1", LEVEL_COLORS[log.level])}>
                      {log.message}
                    </td>
                  </tr>
                ))}
                {filteredLogs.length === 0 && (
                  <tr>
                    <td colSpan={4} className="px-3 py-8 text-center text-muted-foreground">
                      No log entries
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}

function MetricCard({
  label,
  value,
}: {
  label: string
  value: React.ReactNode
}) {
  return (
    <Card>
      <CardContent className="flex flex-col gap-1 px-4 py-3">
        <span className="text-xs text-muted-foreground">{label}</span>
        <span className="text-lg font-semibold tabular-nums">{value}</span>
      </CardContent>
    </Card>
  )
}
