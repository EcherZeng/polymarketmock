import axios from "axios"
import type {
  StrategyInfo,
  ArchiveInfo,
  BacktestResult,
  BacktestResultSummary,
  EquityPoint,
  DrawdownPoint,
  TradeRecord,
  PositionPoint,
  RunRequest,
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
