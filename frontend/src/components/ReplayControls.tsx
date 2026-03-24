import { useCallback, useEffect, useRef, useState } from "react"
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
  onSeek: (index: number) => void
}

function fmtTs(iso: string): string {
  try {
    return new Date(iso).toLocaleTimeString("zh-CN", {
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
      hour12: false,
    })
  } catch {
    return iso
  }
}

export default function ReplayControls({
  timeline,
  currentIndex,
  onSeek,
}: ReplayControlsProps) {
  const [playing, setPlaying] = useState(false)
  const [speed, setSpeed] = useState("1")
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null)
  const indexRef = useRef(currentIndex)

  indexRef.current = currentIndex

  const startPlay = useCallback(() => {
    if (timerRef.current) return
    setPlaying(true)
    const interval = 1000 / parseFloat(speed)
    timerRef.current = setInterval(() => {
      const next = indexRef.current + 1
      if (next >= timeline.timestamps.length) {
        if (timerRef.current) clearInterval(timerRef.current)
        timerRef.current = null
        setPlaying(false)
        return
      }
      onSeek(next)
    }, interval)
  }, [speed, timeline.timestamps.length, onSeek])

  const stopPlay = useCallback(() => {
    if (timerRef.current) {
      clearInterval(timerRef.current)
      timerRef.current = null
    }
    setPlaying(false)
  }, [])

  // Restart timer when speed changes
  useEffect(() => {
    if (playing) {
      stopPlay()
      startPlay()
    }
  }, [speed])

  // Cleanup
  useEffect(() => {
    return () => {
      if (timerRef.current) clearInterval(timerRef.current)
    }
  }, [])

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
          stopPlay()
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
            stopPlay()
            onSeek(Math.max(0, currentIndex - 1))
          }}
        >
          ⏮
        </Button>

        {playing ? (
          <Button size="sm" onClick={stopPlay}>
            ⏸ 暂停
          </Button>
        ) : (
          <Button
            size="sm"
            disabled={currentIndex >= total - 1}
            onClick={startPlay}
          >
            ▶ 播放
          </Button>
        )}

        <Button
          variant="outline"
          size="sm"
          disabled={currentIndex >= total - 1}
          onClick={() => {
            stopPlay()
            onSeek(Math.min(total - 1, currentIndex + 1))
          }}
        >
          ⏭
        </Button>

        <Select value={speed} onValueChange={setSpeed}>
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
