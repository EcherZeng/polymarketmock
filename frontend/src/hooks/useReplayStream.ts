import { useCallback, useEffect, useRef, useState } from "react"
import type {
  ReplaySnapshot,
  ReplaySnapshotTrade,
  StreamSnapshotEvent,
} from "@/types"

interface UseReplayStreamOptions {
  slug: string | undefined
  startIndex: number
  speed: number
  playing: boolean
}

interface UseReplayStreamResult {
  /** Current snapshot (trades accumulated incrementally) */
  snapshot: ReplaySnapshot | null
  /** Current index in the timeline */
  streamIndex: number
  /** Whether the EventSource is connected */
  connected: boolean
}

export function useReplayStream({
  slug,
  startIndex,
  speed,
  playing,
}: UseReplayStreamOptions): UseReplayStreamResult {
  const [snapshot, setSnapshot] = useState<ReplaySnapshot | null>(null)
  const [streamIndex, setStreamIndex] = useState(startIndex)
  const [connected, setConnected] = useState(false)
  const tradesRef = useRef<ReplaySnapshotTrade[]>([])
  const eventSourceRef = useRef<EventSource | null>(null)

  const close = useCallback(() => {
    if (eventSourceRef.current) {
      eventSourceRef.current.close()
      eventSourceRef.current = null
    }
    setConnected(false)
  }, [])

  /** Reset accumulated trades (call on seek) */
  const resetTrades = useCallback(() => {
    tradesRef.current = []
  }, [])

  useEffect(() => {
    if (!playing || !slug) {
      close()
      return
    }

    // Reset trades for new stream connection
    resetTrades()

    const url = `/api/backtest/replay/${encodeURIComponent(slug)}/stream?start_index=${startIndex}&speed=${speed}`
    const es = new EventSource(url)
    eventSourceRef.current = es

    es.onopen = () => setConnected(true)

    es.onmessage = (e) => {
      try {
        const data: StreamSnapshotEvent = JSON.parse(e.data)

        // Accumulate new trades
        if (data.new_trades?.length) {
          tradesRef.current = [...tradesRef.current, ...data.new_trades]
        }

        // Build full ReplaySnapshot with per-token data
        const full: ReplaySnapshot = {
          timestamp: data.timestamp,
          token_ids: data.token_ids ?? [],
          tokens: data.tokens ?? {},
          trades: tradesRef.current,
        }
        setSnapshot(full)
        setStreamIndex(data.index)
      } catch {
        // ignore parse errors
      }
    }

    es.addEventListener("end", () => close())
    es.onerror = () => close()

    return () => {
      es.close()
      setConnected(false)
    }
  }, [slug, startIndex, speed, playing, close, resetTrades])

  return { snapshot, streamIndex, connected }
}
