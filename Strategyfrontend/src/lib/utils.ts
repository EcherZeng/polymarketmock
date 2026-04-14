import { clsx, type ClassValue } from "clsx"
import { twMerge } from "tailwind-merge"

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

// ── UTC+8 (China Standard Time) formatting helpers ──────────────────────────
// All backend timestamps are stored as UTC. Display always uses UTC+8
// regardless of the browser/server local timezone.

const CST = "Asia/Shanghai"

/** ISO → "HH:mm:ss" in UTC+8 */
export function fmtTimeCst(iso: string): string {
  if (!iso) return ""
  try {
    return new Date(iso).toLocaleTimeString("zh-CN", {
      timeZone: CST,
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
      hour12: false,
    })
  } catch {
    return iso
  }
}

/** ISO → "HH:mm" in UTC+8 */
export function fmtTimeShortCst(iso: string): string {
  if (!iso) return ""
  try {
    return new Date(iso).toLocaleTimeString("zh-CN", {
      timeZone: CST,
      hour: "2-digit",
      minute: "2-digit",
      hour12: false,
    })
  } catch {
    return iso
  }
}

/** ISO → "MM/DD HH:mm:ss" in UTC+8 */
export function fmtDateTimeCst(iso: string): string {
  if (!iso) return "—"
  try {
    return new Date(iso).toLocaleString("zh-CN", {
      timeZone: CST,
      month: "2-digit",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
      hour12: false,
    })
  } catch {
    return iso
  }
}

/** ISO → full date+time string in UTC+8 */
export function fmtFullCst(iso: string): string {
  if (!iso) return "—"
  try {
    return new Date(iso).toLocaleString("zh-CN", { timeZone: CST, hour12: false })
  } catch {
    return iso
  }
}

/** Unix ms → "HH:mm" in UTC+8 */
export function fmtMsTimeCst(ms: number): string {
  const d = new Date(ms)
  return d.toLocaleTimeString("zh-CN", {
    timeZone: CST,
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  })
}

/** Unix ms → "M/D HH:mm" in UTC+8 */
export function fmtMsDateTimeCst(ms: number): string {
  const d = new Date(ms)
  return d.toLocaleString("zh-CN", {
    timeZone: CST,
    month: "numeric",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  })
}

/**
 * Format elapsed duration between two ISO timestamps (or from started_at to now).
 * Returns a compact string like "1分23秒" or "45秒".
 * If started_at is empty/undefined, returns "".
 */
export function fmtElapsed(startedAt: string | undefined, finishedAt?: string | undefined): string {
  if (!startedAt) return ""
  try {
    const start = new Date(startedAt).getTime()
    const end = finishedAt ? new Date(finishedAt).getTime() : Date.now()
    const totalSec = Math.max(0, Math.floor((end - start) / 1000))
    const h = Math.floor(totalSec / 3600)
    const m = Math.floor((totalSec % 3600) / 60)
    const s = totalSec % 60
    if (h > 0) return `${h}时${m}分${s}秒`
    if (m > 0) return `${m}分${s}秒`
    return `${s}秒`
  } catch {
    return ""
  }
}
