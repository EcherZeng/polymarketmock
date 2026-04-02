import axios from "axios"
import type {
  StrategyInfo,
  ArchiveInfo,
  BacktestResult,
  BacktestResultSummary,
  EquityPoint,
  DrawdownPoint,
  DrawdownEvent,
  TradeRecord,
  PositionPoint,
  RunRequest,
  BatchRequest,
  BatchTask,
  BatchTaskDetail,
  PresetsResponse,
} from "@/types"

const api = axios.create({ baseURL: "/strategy" })

// ── Strategies ──────────────────────────────────────────────────────────────

export async function fetchStrategies(): Promise<StrategyInfo[]> {
  const { data } = await api.get<StrategyInfo[]>("/strategies")
  return data
}

export async function fetchStrategy(name: string): Promise<StrategyInfo> {
  const { data } = await api.get<StrategyInfo>(`/strategies/${name}`)
  return data
}

// ── Presets ──────────────────────────────────────────────────────────────────

export async function fetchPresets(): Promise<PresetsResponse> {
  const { data } = await api.get<PresetsResponse>("/presets")
  return data
}

export async function savePreset(
  name: string,
  body: { description?: string; params: Record<string, unknown> },
): Promise<{ name: string; config: Record<string, unknown> }> {
  const { data } = await api.put(`/presets/${name}`, body)
  return data
}

export async function deletePreset(name: string): Promise<void> {
  await api.delete(`/presets/${name}`)
}

// ── Data Archives ───────────────────────────────────────────────────────────

export async function fetchArchives(): Promise<ArchiveInfo[]> {
  const { data } = await api.get<ArchiveInfo[]>("/data/archives")
  return data
}

export async function fetchArchiveDetail(slug: string): Promise<ArchiveInfo> {
  const { data } = await api.get<ArchiveInfo>(`/data/archives/${slug}`)
  return data
}

// ── Backtest Execution ──────────────────────────────────────────────────────

export async function runBacktest(req: RunRequest): Promise<BacktestResult> {
  const { data } = await api.post<BacktestResult>("/run", req)
  return data
}

// ── Batch Execution ─────────────────────────────────────────────────────────

export async function submitBatch(
  req: BatchRequest,
): Promise<{ batch_id: string; total: number }> {
  const { data } = await api.post<{ batch_id: string; total: number }>("/batch", req)
  return data
}

export async function fetchBatchTasks(): Promise<BatchTask[]> {
  const { data } = await api.get<BatchTask[]>("/tasks")
  return data
}

export async function fetchBatchTask(batchId: string): Promise<BatchTaskDetail> {
  const { data } = await api.get<BatchTaskDetail>(`/tasks/${batchId}`)
  return data
}

export async function cancelBatch(batchId: string): Promise<void> {
  await api.post(`/tasks/${batchId}/cancel`)
}

// ── Results ─────────────────────────────────────────────────────────────────

export async function fetchResults(): Promise<BacktestResultSummary[]> {
  const { data } = await api.get<BacktestResultSummary[]>("/results")
  return data
}

export async function fetchResult(sessionId: string): Promise<BacktestResult> {
  const { data } = await api.get<BacktestResult>(`/results/${sessionId}`)
  return data
}

export async function fetchEquityCurve(sessionId: string): Promise<EquityPoint[]> {
  const { data } = await api.get<EquityPoint[]>(`/results/${sessionId}/equity`)
  return data
}

export async function fetchDrawdownCurve(sessionId: string): Promise<DrawdownPoint[]> {
  const { data } = await api.get<DrawdownPoint[]>(`/results/${sessionId}/drawdown`)
  return data
}

export async function fetchDrawdownEvents(sessionId: string): Promise<DrawdownEvent[]> {
  const { data } = await api.get<DrawdownEvent[]>(`/results/${sessionId}/drawdown-events`)
  return data
}

export async function fetchTrades(sessionId: string): Promise<TradeRecord[]> {
  const { data } = await api.get<TradeRecord[]>(`/results/${sessionId}/trades`)
  return data
}

export async function fetchPositions(sessionId: string): Promise<PositionPoint[]> {
  const { data } = await api.get<PositionPoint[]>(`/results/${sessionId}/positions`)
  return data
}

export async function deleteResult(sessionId: string): Promise<void> {
  await api.delete(`/results/${sessionId}`)
}

export async function clearResults(): Promise<void> {
  await api.delete("/results")
}

// ── Data Cleanup ────────────────────────────────────────────────────────────

export interface IncompleteItem {
  slug: string
  source: "archive" | "live"
  duration_min: number
  prices_count: number
  orderbooks_count: number
  live_trades_count: number
  size_mb: number
  time_range: { start: string; end: string }
  threshold: number
}

export interface IncompleteResponse {
  total_archives: number
  incomplete_count: number
  thresholds: Record<number, number>
  items: IncompleteItem[]
}

export interface CleanupResponse {
  deleted: string[]
  not_found: string[]
  deleted_count: number
}

export async function fetchIncomplete(
  min5m?: number,
  min15m?: number,
): Promise<IncompleteResponse> {
  const params: Record<string, number> = {}
  if (min5m !== undefined) params.min_prices_5m = min5m
  if (min15m !== undefined) params.min_prices_15m = min15m
  const { data } = await api.get<IncompleteResponse>("/data/incomplete", { params })
  return data
}

export async function cleanupSlugs(slugs: string[]): Promise<CleanupResponse> {
  const { data } = await api.post<CleanupResponse>("/data/cleanup", { slugs })
  return data
}

export async function deleteArchive(slug: string): Promise<void> {
  await api.delete(`/data/archives/${slug}`)
}
