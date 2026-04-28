import { clsx, type ClassValue } from "clsx"
import { twMerge } from "tailwind-merge"

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

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

/** ISO → "MM-DD HH:mm" in UTC+8 */
export function fmtDateTimeCst(iso: string): string {
  if (!iso) return ""
  try {
    const d = new Date(iso)
    const month = String(d.toLocaleString("en-US", { timeZone: CST, month: "numeric" })).padStart(2, "0")
    const day = String(d.toLocaleString("en-US", { timeZone: CST, day: "numeric" })).padStart(2, "0")
    const time = d.toLocaleTimeString("zh-CN", {
      timeZone: CST,
      hour: "2-digit",
      minute: "2-digit",
      hour12: false,
    })
    return `${month}-${day} ${time}`
  } catch {
    return iso
  }
}

/** epoch → ISO string */
export function epochToIso(epoch: number): string {
  return new Date(epoch * 1000).toISOString()
}

/** Format number as USD */
export function fmtUsd(value: number, decimals = 2): string {
  return `$${value.toFixed(decimals)}`
}

/** Colour for PnL values */
export function pnlColor(value: number): string {
  if (value > 0) return "text-green-600 dark:text-green-400"
  if (value < 0) return "text-red-600 dark:text-red-400"
  return "text-muted-foreground"
}
