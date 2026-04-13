import { useState, useEffect } from "react"
import { useNavigate } from "react-router-dom"
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import { Input } from "@/components/ui/input"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Switch } from "@/components/ui/switch"
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { ScrollArea } from "@/components/ui/scroll-area"
import MarketInfo from "@/components/MarketInfo"
import OrderbookView from "@/components/OrderbookView"
import PriceChart from "@/components/PriceChart"
import TradingPanel from "@/components/TradingPanel"
import PositionTable from "@/components/PositionTable"
import TradeHistory from "@/components/TradeHistory"
import { fetchMarket, searchEvents, resolveSlug, fetchBtcMarkets, fetchAutoRecordConfig, updateAutoRecordConfig } from "@/api/client"
import type { Market, MarketEvent, AutoRecordConfig, AutoRecordState } from "@/types"
import { fmtTimeShortCst } from "@/lib/utils"

/** Parse clobTokenIds — handles both array and legacy JSON-string format. */
function parseTokenIds(raw: unknown): string[] {
  if (Array.isArray(raw)) return raw.filter(Boolean)
  if (typeof raw === "string") {
    try {
      const parsed = JSON.parse(raw)
      if (Array.isArray(parsed)) return parsed.filter(Boolean)
    } catch { /* not JSON, try comma-split */ }
    return raw.split(",").map((t) => t.trim()).filter(Boolean)
  }
  return []
}

/** Extract event slug from a Polymarket URL or return raw input. */
function extractSlugOrId(input: string): { type: "slug" | "marketId"; value: string } {
  // https://polymarket.com/event/btc-updown-5m-1774334100#xxx
  const eventMatch = input.match(/polymarket\.com\/event\/([^#?\s]+)/)
  if (eventMatch) return { type: "slug", value: eventMatch[1] }
  // plain numeric = market ID
  return { type: "marketId", value: input.trim() }
}

export default function TradingDashboard() {
  const navigate = useNavigate()
  const [marketIdInput, setMarketIdInput] = useState("")
  const [activeMarketId, setActiveMarketId] = useState("")
  const [activeTokenId, setActiveTokenId] = useState("")
  const [searchQuery, setSearchQuery] = useState("")
  const [loadingSlug, setLoadingSlug] = useState(false)

  const { data: market } = useQuery<Market>({
    queryKey: ["market", activeMarketId],
    queryFn: () => fetchMarket(activeMarketId),
    enabled: !!activeMarketId,
  })

  // BTC dynamic market discovery — auto-refresh every 30s
  const { data: btcMarkets } = useQuery<Record<string, MarketEvent[]>>({
    queryKey: ["btcMarkets"],
    queryFn: fetchBtcMarkets,
    refetchInterval: 30_000,
    staleTime: 15_000,
  })

  // Search for BTC up/down or other events
  const { data: searchResults } = useQuery<MarketEvent[]>({
    queryKey: ["searchEvents", searchQuery],
    queryFn: () => searchEvents(searchQuery, true, 10),
    enabled: searchQuery.length >= 2,
    staleTime: 30_000,
  })

  async function handleLoadMarket() {
    const raw = marketIdInput.trim()
    if (!raw) return
    const parsed = extractSlugOrId(raw)
    if (parsed.type === "slug") {
      setLoadingSlug(true)
      try {
        const event = await resolveSlug(parsed.value)
        if (event?.markets?.[0]) {
          setActiveMarketId(event.markets[0].id)
          setActiveTokenId("")
        }
      } finally {
        setLoadingSlug(false)
      }
    } else {
      setActiveMarketId(parsed.value)
      setActiveTokenId("")
    }
  }

  function handleSelectEventMarket(m: Market) {
    setActiveMarketId(m.id)
    setActiveTokenId("")
    setSearchQuery("")
  }

  // When market loads, extract the first token ID
  const tokenIds = parseTokenIds(market?.clobTokenIds)
  useEffect(() => {
    if (tokenIds.length > 0 && market) {
      setActiveTokenId(tokenIds[0])
    }
  }, [market?.id])

  return (
    <div className="flex flex-col gap-4">
      {/* Market ID / URL input */}
      <div className="flex items-center gap-2">
        <Input
          placeholder="Market ID, Polymarket URL, or search keyword..."
          value={marketIdInput}
          onChange={(e) => setMarketIdInput(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && handleLoadMarket()}
          className="flex-1"
        />
        <Button onClick={handleLoadMarket} disabled={loadingSlug}>
          {loadingSlug ? "Loading..." : "Load"}
        </Button>
        {tokenIds.length > 1 && (
          <div className="flex gap-1">
            {tokenIds.map((tid, i) => {
              const outcomes = Array.isArray(market?.outcomes)
                ? market.outcomes
                : []
              return (
                <Button
                  key={tid}
                  variant={activeTokenId === tid ? "default" : "outline"}
                  size="sm"
                  onClick={() => setActiveTokenId(tid)}
                >
                  {outcomes[i] ?? `Token ${i}`}
                </Button>
              )
            })}
          </div>
        )}
      </div>

      {/* Quick search for BTC / dynamic markets */}
      <div className="flex items-center gap-2">
        <Input
          placeholder="Search events (e.g. btc-updown, bitcoin)..."
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          className="max-w-xs"
        />
        {searchResults && searchResults.length > 0 && (
          <span className="text-xs text-muted-foreground">
            {searchResults.length} results
          </span>
        )}
      </div>

      {/* Search results dropdown */}
      {searchResults && searchResults.length > 0 && (
        <div className="rounded-lg border bg-card p-2">
          <div className="mb-1 text-xs font-medium text-muted-foreground">Active Events</div>
          <div className="flex flex-col gap-1 max-h-48 overflow-y-auto">
            {searchResults.map((evt) => (
              <div key={evt.id} className="rounded px-2 py-1 text-sm hover:bg-accent cursor-pointer"
                onClick={() => {
                  if (evt.slug) {
                    navigate(`/event/${evt.slug}`)
                  } else if (evt.markets?.[0]) {
                    handleSelectEventMarket(evt.markets[0])
                  }
                }}
              >
                <span className="font-medium">{evt.title}</span>
                <span className="ml-2 text-xs text-muted-foreground">
                  {evt.markets?.length ?? 0} market(s)
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      {!activeMarketId && !searchResults?.length && (
        <div className="flex items-center justify-center rounded-lg border border-dashed p-12 text-muted-foreground">
          Enter a Market ID / Polymarket URL above, or search for events
        </div>
      )}

      {/* BTC Quick Access Panel */}
      {!activeMarketId && btcMarkets && (
        <>
          <AutoRecordPanel />
          <BtcMarketPanel btcMarkets={btcMarkets} onSelect={handleSelectEventMarket} onNavigate={(slug) => navigate(`/event/${slug}`)} />
        </>
      )}

      {activeMarketId && activeTokenId && (
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-12">
          {/* Left column — Market info + Orderbook + Price chart */}
          <div className="flex flex-col gap-4 lg:col-span-4">
            <MarketInfo marketId={activeMarketId} />
            <OrderbookView tokens={[activeTokenId]} outcomes={["Token"]} />
            <PriceChart tokens={[activeTokenId]} outcomes={["Token"]} />
          </div>

          {/* Middle column — Trading panel */}
          <div className="flex flex-col gap-4 lg:col-span-4">
            <TradingPanel tokenId={activeTokenId} />
            <TradeHistory />
          </div>

          {/* Right column — Positions + Account */}
          <div className="flex flex-col gap-4 lg:col-span-4">
            <PositionTable />
          </div>
        </div>
      )}
    </div>
  )
}

// ── Auto-Record Control Panel ───────────────────────────────────────────────

const DURATION_OPTIONS = [
  { key: "5m", label: "5 分钟" },
  { key: "15m", label: "15 分钟" },
  { key: "30m", label: "30 分钟" },
] as const

const STATUS_LABEL: Record<string, { text: string; color: string }> = {
  searching: { text: "搜索中…", color: "text-blue-500" },
  waiting: { text: "等待开始", color: "text-blue-500" },
  recording: { text: "录制中", color: "text-destructive" },
  archiving: { text: "归档中", color: "text-amber-500" },
  completed: { text: "已完成", color: "text-emerald-500" },
}

function formatRemaining(secs: number | null | undefined): string {
  if (secs == null || secs <= 0) return ""
  const m = Math.floor(secs / 60)
  const s = Math.floor(secs % 60)
  return `${m}:${String(s).padStart(2, "0")}`
}

function AutoRecordPanel() {
  const queryClient = useQueryClient()

  const { data: config } = useQuery<AutoRecordConfig>({
    queryKey: ["autoRecordConfig"],
    queryFn: fetchAutoRecordConfig,
    refetchInterval: 5_000,
  })

  const mutation = useMutation({
    mutationFn: (durations: string[]) => updateAutoRecordConfig(durations),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["autoRecordConfig"] }),
  })

  const activeDurations = new Set(config?.durations ?? [])

  function handleToggle(dur: string, checked: boolean) {
    const next = checked
      ? [...activeDurations, dur]
      : [...activeDurations].filter((d) => d !== dur)
    mutation.mutate(next)
  }

  return (
    <Card>
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <CardTitle className="text-base">自动循环录制</CardTitle>
          {activeDurations.size > 0 && (
            <Badge variant="destructive" className="animate-pulse gap-1">
              <span className="inline-block size-2 rounded-full bg-white" />
              {activeDurations.size} 个时长运行中
            </Badge>
          )}
        </div>
      </CardHeader>
      <CardContent>
        <div className="flex flex-col gap-3">
          {DURATION_OPTIONS.map(({ key, label }) => {
            const active = activeDurations.has(key)
            const state = config?.states?.[key] as AutoRecordState | undefined
            const sl = state ? STATUS_LABEL[state.status] : null

            return (
              <div
                key={key}
                className={`flex items-center justify-between rounded-md border px-3 py-2 ${
                  active ? "border-destructive/30 bg-destructive/5" : ""
                }`}
              >
                <div className="flex items-center gap-3">
                  <Switch
                    checked={active}
                    onCheckedChange={(v) => handleToggle(key, v)}
                    disabled={mutation.isPending}
                  />
                  <span className="text-sm font-medium">{label}</span>
                </div>
                {active && state && (
                  <div className="flex items-center gap-2 text-xs">
                    {state.status === "recording" && (
                      <span className="inline-block size-2 animate-pulse rounded-full bg-destructive" />
                    )}
                    {sl && <span className={sl.color}>{sl.text}</span>}
                    {state.seconds_remaining != null && state.seconds_remaining > 0 && (
                      <Badge variant="outline" className="tabular-nums text-xs">
                        {formatRemaining(state.seconds_remaining)}
                      </Badge>
                    )}
                    {state.slug && (
                      <span className="max-w-40 truncate text-muted-foreground">{state.slug}</span>
                    )}
                  </div>
                )}
              </div>
            )
          })}
        </div>
      </CardContent>
    </Card>
  )
}

// ── BTC Market Discovery Panel ──────────────────────────────────────────────

const DURATION_LABELS: Record<string, string> = {
  "5m": "5 分钟",
  "15m": "15 分钟",
  "30m": "30 分钟",
}

const STATUS_CONFIG: Record<string, { label: string; variant: "default" | "secondary" | "destructive" | "outline" }> = {
  live: { label: "━ LIVE", variant: "destructive" },
  upcoming: { label: "即将开始", variant: "default" },
  ended: { label: "已结束", variant: "secondary" },
  unknown: { label: "?", variant: "outline" },
}

function parseOutcomes(raw: unknown): string[] {
  if (Array.isArray(raw)) return raw
  if (typeof raw === "string") {
    try { return JSON.parse(raw) } catch { return [] }
  }
  return []
}

function parsePrices(raw: unknown): string[] {
  if (Array.isArray(raw)) return raw
  if (typeof raw === "string") {
    try { return JSON.parse(raw) } catch { return [] }
  }
  return []
}

/** Format eventStartTime to short time string in UTC+8. */
function fmtTime(iso: string | undefined): string {
  if (!iso) return ""
  return fmtTimeShortCst(iso)
}

interface BtcMarketPanelProps {
  btcMarkets: Record<string, MarketEvent[]>
  onSelect: (m: Market) => void
  onNavigate: (slug: string) => void
}

function BtcMarketPanel({ btcMarkets, onSelect, onNavigate }: BtcMarketPanelProps) {
  const availableTabs = Object.entries(btcMarkets).filter(([, events]) => events.length > 0)
  if (availableTabs.length === 0) return null

  return (
    <Card>
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <CardTitle className="text-base">Bitcoin 涨跌预测 — 快速入口</CardTitle>
          <span className="text-xs text-muted-foreground">每 20s 自动刷新</span>
        </div>
      </CardHeader>
      <CardContent>
        <Tabs defaultValue={availableTabs[0][0]}>
          <TabsList>
            {availableTabs.map(([dur, events]) => {
              const liveCount = events.filter((e) => e._status === "live").length
              return (
                <TabsTrigger key={dur} value={dur}>
                  {DURATION_LABELS[dur] ?? dur}
                  {liveCount > 0 && (
                    <span className="ml-1 inline-flex h-4 min-w-4 items-center justify-center rounded-full bg-destructive px-1 text-[10px] font-bold text-destructive-foreground">
                      {liveCount}
                    </span>
                  )}
                </TabsTrigger>
              )
            })}
          </TabsList>

          {availableTabs.map(([dur, events]) => {
            // Sort: live first, then upcoming, then ended
            const sorted = [...events].sort((a, b) => {
              const order: Record<string, number> = { live: 0, upcoming: 1, ended: 2, unknown: 3 }
              return (order[a._status ?? "unknown"] ?? 3) - (order[b._status ?? "unknown"] ?? 3)
            })

            return (
              <TabsContent key={dur} value={dur} className="mt-2">
                <ScrollArea className="max-h-80">
                  <div className="flex flex-col gap-1.5">
                    {sorted.map((evt) => {
                      const m = evt.markets?.[0]
                      if (!m) return null
                      const outcomes = parseOutcomes(m.outcomes)
                      const prices = parsePrices(m.outcomePrices)
                      const tokens = parseTokenIds(m.clobTokenIds)
                      const status = evt._status ?? "unknown"
                      const sc = STATUS_CONFIG[status]
                      const isLive = status === "live"

                      return (
                        <div
                          key={evt.id}
                          className={`flex items-center justify-between gap-2 rounded-md border px-3 py-2 text-sm cursor-pointer transition-colors ${
                            isLive
                              ? "border-destructive/50 bg-destructive/5 hover:bg-destructive/10"
                              : status === "ended"
                                ? "opacity-60 hover:opacity-80 hover:bg-accent"
                                : "hover:bg-accent"
                          }`}
                          onClick={() => {
                            if (evt.slug) {
                              onNavigate(evt.slug)
                            } else {
                              onSelect(m)
                            }
                          }}
                        >
                          <div className="flex flex-col gap-0.5 min-w-0">
                            <div className="flex items-center gap-2">
                              <span className="font-medium truncate">{evt.title}</span>
                            </div>
                            <div className="flex items-center gap-2 text-xs text-muted-foreground">
                              <span>ID: {m.id}</span>
                              <span>·</span>
                              <span>{fmtTime(evt.startDate)} – {fmtTime(evt.endDate)}</span>
                            </div>
                            {tokens[0] && (
                              <span className="text-xs text-muted-foreground font-mono truncate">
                                Token: {tokens[0].slice(0, 24)}...
                              </span>
                            )}
                          </div>
                          <div className="flex items-center gap-2 shrink-0">
                            {outcomes[0] && prices[0] && (
                              <Badge variant="outline" className="text-chart-2 border-chart-2">
                                {outcomes[0]} {(parseFloat(prices[0]) * 100).toFixed(0)}¢
                              </Badge>
                            )}
                            {outcomes[1] && prices[1] && (
                              <Badge variant="outline" className="text-chart-1 border-chart-1">
                                {outcomes[1]} {(parseFloat(prices[1]) * 100).toFixed(0)}¢
                              </Badge>
                            )}
                            <Badge variant={sc.variant}>
                              {sc.label}
                            </Badge>
                          </div>
                        </div>
                      )
                    })}
                  </div>
                </ScrollArea>
              </TabsContent>
            )
          })}
        </Tabs>
      </CardContent>
    </Card>
  )
}
