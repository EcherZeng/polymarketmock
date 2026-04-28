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

  getExecutorMode: () =>
    api.get<{ executor_mode: string }>("/executor-mode").then((r) => r.data),

  setExecutorMode: (mode: string) =>
    api.put<{ executor_mode: string; changed: boolean }>("/executor-mode", { mode }).then((r) => r.data),

  pause: () => api.post("/pause").then((r) => r.data),

  resume: () => api.post("/resume").then((r) => r.data),
}
