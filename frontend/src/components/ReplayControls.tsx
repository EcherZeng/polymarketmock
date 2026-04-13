import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Slider } from "@/components/ui/slider"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import type { ReplayTimeline } from "@/types"

interface ReplayControlsProps {
  timeline: ReplayTimeline
  currentIndex: number
  playing: boolean
  speed: string
  connected: boolean
  onSeek: (index: number) => void
  onPlayingChange: (playing: boolean) => void
  onSpeedChange: (speed: string) => void
}

import { fmtTimeCst } from "@/lib/utils"

function fmtTs(iso: string): string {
  return fmtTimeCst(iso)
}

export default function ReplayControls({
  timeline,
  currentIndex,
  playing,
  speed,
  connected,
  onSeek,
  onPlayingChange,
  onSpeedChange,
}: ReplayControlsProps) {
  const total = timeline.timestamps.length
  const pct = total > 0 ? ((currentIndex + 1) / total) * 100 : 0
  const currentTs = timeline.timestamps[currentIndex] ?? ""

  return (
    <div className="flex flex-col gap-3 rounded-lg border bg-card p-4">
      {/* Header row */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Badge variant="outline" className="font-mono text-xs">
            {fmtTs(timeline.start_time)}
          </Badge>
          <span className="text-xs text-muted-foreground">→</span>
          <Badge variant="outline" className="font-mono text-xs">
            {fmtTs(timeline.end_time)}
          </Badge>
        </div>
        <div className="flex items-center gap-2">
          {playing && (
            <Badge
              variant={connected ? "default" : "secondary"}
              className="text-xs"
            >
              {connected ? "● 流式" : "○ 连接中…"}
            </Badge>
          )}
          <Badge variant="secondary" className="font-mono text-xs tabular-nums">
            {currentIndex + 1} / {total}
          </Badge>
          <Badge className="font-mono text-xs tabular-nums">
            {pct.toFixed(0)}%
          </Badge>
        </div>
      </div>

      {/* Current timestamp */}
      <div className="text-center font-mono text-sm font-medium tabular-nums">
        {fmtTs(currentTs)}
      </div>

      {/* Slider */}
      <Slider
        min={0}
        max={Math.max(total - 1, 0)}
        step={1}
        value={[currentIndex]}
        onValueChange={([v]) => {
          onPlayingChange(false)
          onSeek(v)
        }}
      />

      {/* Controls row */}
      <div className="flex items-center justify-center gap-3">
        <Button
          variant="outline"
          size="sm"
          disabled={currentIndex <= 0}
          onClick={() => {
            onPlayingChange(false)
            onSeek(Math.max(0, currentIndex - 1))
          }}
        >
          ⏮
        </Button>

        {playing ? (
          <Button size="sm" onClick={() => onPlayingChange(false)}>
            ⏸ 暂停
          </Button>
        ) : (
          <Button
            size="sm"
            disabled={currentIndex >= total - 1}
            onClick={() => onPlayingChange(true)}
          >
            ▶ 播放
          </Button>
        )}

        <Button
          variant="outline"
          size="sm"
          disabled={currentIndex >= total - 1}
          onClick={() => {
            onPlayingChange(false)
            onSeek(Math.min(total - 1, currentIndex + 1))
          }}
        >
          ⏭
        </Button>

        <Select value={speed} onValueChange={onSpeedChange}>
          <SelectTrigger className="w-20">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="0.5">0.5x</SelectItem>
            <SelectItem value="1">1x</SelectItem>
            <SelectItem value="2">2x</SelectItem>
            <SelectItem value="5">5x</SelectItem>
            <SelectItem value="10">10x</SelectItem>
          </SelectContent>
        </Select>
      </div>
    </div>
  )
}
