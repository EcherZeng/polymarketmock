import type { DrawdownEvent } from "@/types"
import { cn } from "@/lib/utils"

interface DrawdownTableProps {
  events: DrawdownEvent[]
}

function formatTime(iso: string | null): string {
  if (!iso) return "—"
  return iso.slice(11, 19)
}

function formatDuration(seconds: number | null): string {
  if (seconds == null) return "—"
  if (seconds < 60) return `${seconds.toFixed(0)}s`
  const m = Math.floor(seconds / 60)
  const s = Math.round(seconds % 60)
  return `${m}m${s}s`
}

export default function DrawdownTable({ events }: DrawdownTableProps) {
  if (events.length === 0) {
    return <div className="text-sm text-muted-foreground">无回撤事件</div>
  }

  const maxDd = Math.max(...events.map((e) => e.drawdown_pct))

  return (
    <div className="max-h-64 overflow-auto rounded-md border">
      <table className="w-full text-xs">
        <thead className="sticky top-0 bg-muted/80">
          <tr className="border-b text-left text-muted-foreground">
            <th className="px-3 py-2">#</th>
            <th className="px-3 py-2">开始时间</th>
            <th className="px-3 py-2">最低点时间</th>
            <th className="px-3 py-2">恢复时间</th>
            <th className="px-3 py-2 text-right">峰值权益</th>
            <th className="px-3 py-2 text-right">谷值权益</th>
            <th className="px-3 py-2 text-right">回撤幅度</th>
            <th className="px-3 py-2 text-right">持续时间</th>
            <th className="px-3 py-2 text-right">恢复耗时</th>
          </tr>
        </thead>
        <tbody>
          {events.map((e, i) => (
            <tr
              key={i}
              className={cn(
                "border-b hover:bg-muted/30 transition-colors",
                e.drawdown_pct === maxDd && "bg-red-500/5",
              )}
            >
              <td className="px-3 py-2 text-muted-foreground">{i + 1}</td>
              <td className="px-3 py-2 font-mono">{formatTime(e.start_time)}</td>
              <td className="px-3 py-2 font-mono">{formatTime(e.trough_time)}</td>
              <td className="px-3 py-2 font-mono">
                {e.recovery_time ? formatTime(e.recovery_time) : (
                  <span className="text-red-500">未恢复</span>
                )}
              </td>
              <td className="px-3 py-2 text-right font-mono">
                ${e.peak_equity.toFixed(2)}
              </td>
              <td className="px-3 py-2 text-right font-mono">
                ${e.trough_equity.toFixed(2)}
              </td>
              <td className={cn(
                "px-3 py-2 text-right font-mono font-semibold",
                e.drawdown_pct === maxDd ? "text-red-600" : "text-red-500",
              )}>
                {(e.drawdown_pct * 100).toFixed(2)}%
              </td>
              <td className="px-3 py-2 text-right font-mono">
                {formatDuration(e.duration_seconds)}
              </td>
              <td className="px-3 py-2 text-right font-mono">
                {formatDuration(e.recovery_seconds)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
