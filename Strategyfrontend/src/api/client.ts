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
  BtcKlineResponse,
  BtcHdAnalysis,
  ExitAnalysisResponse,
  Portfolio,
  PortfolioItem,
  RerunRequest,
  CompositePreset,
  CompositeBatchRequest,
} from "@/types"

const api = axios.create({ baseURL: "/strategy", timeout: 300_000 })

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

export async function renamePreset(
  name: string,
  newName: string,
): Promise<{ old_name: string; new_name: string }> {
  const { data } = await api.patch(`/presets/${name}/rename`, { new_name: newName })
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

export async function rerunBacktest(req: RerunRequest): Promise<BacktestResult> {
  const { data } = await api.post<BacktestResult>("/rerun", req)
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

// ── Composite Presets ───────────────────────────────────────────────────────

export async function fetchCompositePresets(): Promise<
  Array<{ name: string } & CompositePreset>
> {
  const { data } = await api.get("/composite-presets")
  return data
}

export async function fetchCompositePreset(
  name: string,
): Promise<{ name: string } & CompositePreset> {
  const { data } = await api.get(`/composite-presets/${name}`)
  return data
}

export async function saveCompositePreset(
  name: string,
  body: {
    description?: string
    btc_windows: { btc_trend_window_1: number; btc_trend_window_2: number }
    branches: Array<{ label: string; min_momentum: number; preset_name: string }>
  },
): Promise<{ name: string } & CompositePreset> {
  const { data } = await api.put(`/composite-presets/${name}`, body)
  return data
}

export async function deleteCompositePreset(name: string): Promise<void> {
  await api.delete(`/composite-presets/${name}`)
}

export async function renameCompositePreset(
  name: string,
  newName: string,
): Promise<{ old_name: string; new_name: string }> {
  const { data } = await api.patch(`/composite-presets/${name}/rename`, {
    new_name: newName,
  })
  return data
}

// ── Composite Batch ─────────────────────────────────────────────────────────

export async function submitCompositeBatch(
  req: CompositeBatchRequest,
): Promise<{ batch_id: string; total: number }> {
  const { data } = await api.post<{ batch_id: string; total: number }>(
    "/composite-batch",
    req,
  )
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

export interface FirstTradeSummaryItem {
  pnl: number
  return_pct: number
  cost: number
  token_id: string
}

export async function fetchFirstTradeSummary(
  sessionIds: string[],
): Promise<Record<string, FirstTradeSummaryItem | null>> {
  const { data } = await api.post<Record<string, FirstTradeSummaryItem | null>>(
    "/results/first-trade-summary",
    { session_ids: sessionIds },
  )
  return data
}

export async function fetchBtcKlines(sessionId: string): Promise<BtcKlineResponse> {
  const { data } = await api.get<BtcKlineResponse>(`/results/${sessionId}/btc-klines`)
  return data
}

export async function analyzeBtcHd(sessionId: string): Promise<BtcHdAnalysis> {
  const { data } = await api.post<BtcHdAnalysis>(`/results/${sessionId}/btc-analyze`)
  return data
}

export async function analyzeExitFactors(sessionId: string): Promise<ExitAnalysisResponse> {
  const { data } = await api.post<ExitAnalysisResponse>(`/results/${sessionId}/exit-analysis`)
  return data
}

export async function clearResults(): Promise<void> {
  await api.delete("/results")
}

// ── Results Cleanup ─────────────────────────────────────────────────────────

export interface ResultStatItem {
  session_id: string
  strategy: string
  slug: string
  created_at: string
  final_equity: number
  total_return_pct: number
  total_trades: number
  size_kb: number
  batch_id: string | null
}

export interface BatchStatItem {
  batch_id: string
  strategy: string
  status: string
  total: number
  completed: number
  created_at: string
  slugs_count: number
  results_count: number
  size_kb: number
}

export interface ResultsStatsResponse {
  results_count: number
  results_total_size_mb: number
  results: ResultStatItem[]
  batches_count: number
  batches_total_size_mb: number
  batches: BatchStatItem[]
  runner_tasks_in_memory: number
  runner_tasks_running: number
}

export async function fetchResultsStats(): Promise<ResultsStatsResponse> {
  const { data } = await api.get<ResultsStatsResponse>("/results-stats")
  return data
}

export async function cleanupResultsBulk(
  sessionIds: string[],
): Promise<CleanupResponse> {
  const { data } = await api.post<CleanupResponse>("/results-cleanup", {
    session_ids: sessionIds,
  })
  return data
}

export async function cleanupByBatch(
  batchId: string,
): Promise<{ batch_id: string; results_deleted_count: number }> {
  const { data } = await api.post(`/results-cleanup/by-batch/${batchId}`)
  return data
}

export async function cleanupBatchesBulk(
  batchIds: string[],
): Promise<{ deleted_batches_count: number; deleted_results_count: number }> {
  const { data } = await api.post("/results-cleanup/batches", {
    batch_ids: batchIds,
  })
  return data
}

export async function purgeRunnerMemory(): Promise<{ purged: number }> {
  const { data } = await api.post<{ purged: number }>(
    "/results-cleanup/purge-memory",
  )
  return data
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
  errors?: string[]
  error_detail?: string
}

export async function fetchIncomplete(
  min5m?: number,
  min15m?: number,
): Promise<IncompleteResponse> {
  const params: Record<string, number> = {}
  if (min5m !== undefined) params.min_trades_5m = min5m
  if (min15m !== undefined) params.min_trades_15m = min15m
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

// ── Track data source for git commit ────────────────────────────────────────

export async function trackArchive(
  slug: string,
): Promise<{ slug: string; status: string }> {
  const { data } = await api.post<{ slug: string; status: string }>(
    `/data/archives/${slug}/track`,
  )
  return data
}

export async function fetchTracked(): Promise<string[]> {
  const { data } = await api.get<string[]>("/data/tracked")
  return data
}

// ── Portfolios ──────────────────────────────────────────────────────────────

export async function fetchPortfolios(): Promise<Portfolio[]> {
  const { data } = await api.get<Portfolio[]>("/portfolios")
  return data
}

export async function fetchStrategyGroups(): Promise<Portfolio[]> {
  const { data } = await api.get<Portfolio[]>("/portfolios/strategy-groups")
  return data
}

export async function fetchPortfolio(portfolioId: string): Promise<Portfolio> {
  const { data } = await api.get<Portfolio>(`/portfolios/${portfolioId}`)
  return data
}

export async function createPortfolio(body: {
  name: string
  items: PortfolioItem[]
}): Promise<Portfolio> {
  const { data } = await api.post<Portfolio>("/portfolios", body)
  return data
}

export async function createContainer(body: {
  name: string
  children?: string[]
}): Promise<Portfolio> {
  const { data } = await api.post<Portfolio>("/portfolios/container", body)
  return data
}

export async function renamePortfolio(
  portfolioId: string,
  name: string,
): Promise<Portfolio> {
  const { data } = await api.put<Portfolio>(`/portfolios/${portfolioId}`, { name })
  return data
}

export async function addPortfolioItems(
  portfolioId: string,
  items: PortfolioItem[],
): Promise<Portfolio> {
  const { data } = await api.put<Portfolio>(`/portfolios/${portfolioId}/items`, {
    items,
  })
  return data
}

export async function removePortfolioItems(
  portfolioId: string,
  sessionIds: string[],
): Promise<Portfolio> {
  const { data } = await api.delete<Portfolio>(`/portfolios/${portfolioId}/items`, {
    data: { session_ids: sessionIds },
  })
  return data
}

export async function addChildren(
  portfolioId: string,
  children: string[],
): Promise<Portfolio> {
  const { data } = await api.put<Portfolio>(`/portfolios/${portfolioId}/children`, {
    children,
  })
  return data
}

export async function removeChildren(
  portfolioId: string,
  children: string[],
): Promise<Portfolio> {
  const { data } = await api.delete<Portfolio>(
    `/portfolios/${portfolioId}/children`,
    { data: { children } },
  )
  return data
}

export async function deletePortfolio(portfolioId: string): Promise<void> {
  await api.delete(`/portfolios/${portfolioId}`)
}

// ── AI Optimize ─────────────────────────────────────────────────────────────

export async function fetchAiModels(): Promise<import("@/types").AiModelsResponse> {
  const { data } = await api.get("/ai-optimize/models")
  return data
}

export async function submitAiOptimize(
  req: import("@/types").AiOptimizeRequest,
): Promise<{ task_id: string; max_rounds: number; runs_per_round: number; total_slugs: number; estimated_total_runs: number }> {
  const { data } = await api.post("/ai-optimize", req)
  return data
}

export async function fetchAiOptimizeTasks(): Promise<import("@/types").AiOptimizeTask[]> {
  const { data } = await api.get("/ai-optimize")
  return data
}

export async function fetchAiOptimizeTaskProgress(
  taskId: string,
): Promise<import("@/types").AiOptimizeTaskProgress> {
  const { data } = await api.get(`/ai-optimize/${taskId}/progress`)
  return data
}

export async function fetchAiOptimizeTask(
  taskId: string,
): Promise<import("@/types").AiOptimizeTaskDetail> {
  const { data } = await api.get(`/ai-optimize/${taskId}`)
  return data
}

export async function stopAiOptimize(taskId: string): Promise<void> {
  await api.post(`/ai-optimize/${taskId}/stop`)
}
