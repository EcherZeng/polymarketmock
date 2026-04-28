import axios from "axios"
import type {
  HealthResponse,
  StatusResponse,
  PositionsResponse,
  BalanceResponse,
  PnlResponse,
  SessionRow,
  SessionDetailResponse,
  TradeRow,
  ConfigResponse,
} from "@/types"

const api = axios.create({ baseURL: "/trade-api" })

export const tradeApi = {
  health: () => api.get<HealthResponse>("/health").then((r) => r.data),

  status: () => api.get<StatusResponse>("/status").then((r) => r.data),

  positions: () =>
    api.get<PositionsResponse>("/positions").then((r) => r.data),

  balance: () => api.get<BalanceResponse>("/balance").then((r) => r.data),

  pnl: () => api.get<PnlResponse>("/pnl").then((r) => r.data),

  sessions: (limit = 50) =>
    api.get<SessionRow[]>("/sessions", { params: { limit } }).then((r) => r.data),

  sessionDetail: (slug: string) =>
    api.get<SessionDetailResponse>(`/sessions/${slug}`).then((r) => r.data),

  trades: (sessionSlug?: string, limit = 100) =>
    api
      .get<TradeRow[]>("/trades", {
        params: { session_slug: sessionSlug, limit },
      })
      .then((r) => r.data),

  config: () => api.get<ConfigResponse>("/config").then((r) => r.data),

  updateConfig: (config: Record<string, unknown>) =>
    api.put("/config", { config }).then((r) => r.data),

  loadPreset: (presetName: string) =>
    api.post<{
      ok: boolean
      preset_name: string
      applied: Record<string, number>
      skipped: string[]
      current_config: Record<string, unknown>
    }>("/config/load-preset", { preset_name: presetName }).then((r) => r.data),

  loadComposite: (compositeName: string) =>
    api.post<{
      ok: boolean
      composite_name: string
      branches: number
      btc_windows: { window_1: number; window_2: number }
      branch_details: Array<{
        label: string
        min_momentum: number
        preset_name: string
        config: Record<string, unknown>
      }>
    }>("/config/load-composite", { composite_name: compositeName }).then((r) => r.data),

  clearComposite: () =>
    api.delete<{ ok: boolean }>("/config/composite").then((r) => r.data),

  getExecutorMode: () =>
    api.get<{ executor_mode: string }>("/executor-mode").then((r) => r.data),

  setExecutorMode: (mode: string) =>
    api.put<{ executor_mode: string; changed: boolean }>("/executor-mode", { mode }).then((r) => r.data),

  pause: () => api.post("/pause").then((r) => r.data),

  resume: () => api.post("/resume").then((r) => r.data),
}
