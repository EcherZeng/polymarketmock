import { useState } from "react"
import { useQuery } from "@tanstack/react-query"
import { Input } from "@/components/ui/input"
import { Badge } from "@/components/ui/badge"
import { Skeleton } from "@/components/ui/skeleton"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import EventCard from "@/components/EventCard"
import { fetchBtcMarkets, searchEvents } from "@/api/client"
import type { MarketEvent } from "@/types"

const DURATION_LABELS: Record<string, string> = {
  "5m": "5 分钟",
  "15m": "15 分钟",
}

const STATUS_ORDER: Record<string, number> = {
  live: 0,
  upcoming: 1,
  ended: 2,
  unknown: 3,
}

function sortByStatus(events: MarketEvent[]): MarketEvent[] {
  return [...events].sort(
    (a, b) =>
      (STATUS_ORDER[a._status ?? "unknown"] ?? 3) -
      (STATUS_ORDER[b._status ?? "unknown"] ?? 3),
  )
}

export default function EventListPage() {
  const [searchQuery, setSearchQuery] = useState("")

  const { data: btcMarkets, isLoading: loadingBtc } = useQuery({
    queryKey: ["btcMarkets"],
    queryFn: fetchBtcMarkets,
    refetchInterval: 20_000,
    staleTime: 10_000,
  })

  const { data: searchResults, isLoading: loadingSearch } = useQuery<MarketEvent[]>({
    queryKey: ["searchEvents", searchQuery],
    queryFn: () => searchEvents(searchQuery, false, 30),
    enabled: searchQuery.length >= 2,
    staleTime: 30_000,
  })

  const isSearching = searchQuery.length >= 2

  const tabs = ["5m", "15m"]
    .map((key) => ({
      key,
      label: DURATION_LABELS[key] ?? key,
      events: sortByStatus(btcMarkets?.[key] ?? []),
    }))
    .filter((t) => !btcMarkets || t.events.length > 0 || loadingBtc)

  const defaultTab =
    tabs.find((t) => t.events.some((e) => e._status === "live"))?.key ??
    tabs[0]?.key ??
    "5m"

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <h1 className="text-lg font-semibold">BTC 涨跌预测</h1>
        <span className="text-xs text-muted-foreground">每 20s 自动刷新</span>
      </div>

      <Input
        placeholder="Search events..."
        value={searchQuery}
        onChange={(e) => setSearchQuery(e.target.value)}
        className="max-w-md"
      />

      {/* Search results */}
      {isSearching &&
        (loadingSearch ? (
          <div className="grid grid-cols-1 gap-3 md:grid-cols-2 lg:grid-cols-3">
            {Array.from({ length: 3 }).map((_, i) => (
              <Skeleton key={i} className="h-28 rounded-lg" />
            ))}
          </div>
        ) : !searchResults || searchResults.length === 0 ? (
          <div className="flex items-center justify-center rounded-lg border border-dashed p-8 text-sm text-muted-foreground">
            No events match your search
          </div>
        ) : (
          <div className="grid grid-cols-1 gap-3 md:grid-cols-2 lg:grid-cols-3">
            {searchResults.map((evt) => (
              <EventCard key={evt.id} event={evt} />
            ))}
          </div>
        ))}

      {/* BTC market tabs */}
      {!isSearching &&
        (loadingBtc ? (
          <div className="grid grid-cols-1 gap-3 md:grid-cols-2 lg:grid-cols-3">
            {Array.from({ length: 6 }).map((_, i) => (
              <Skeleton key={i} className="h-28 rounded-lg" />
            ))}
          </div>
        ) : tabs.length === 0 ? (
          <div className="flex items-center justify-center rounded-lg border border-dashed p-12 text-muted-foreground">
            No BTC markets available
          </div>
        ) : (
          <Tabs defaultValue={defaultTab}>
            <TabsList>
              {tabs.map(({ key, label, events }) => {
                const liveCount = events.filter((e) => e._status === "live").length
                return (
                  <TabsTrigger key={key} value={key}>
                    {label}
                    {liveCount > 0 && (
                      <Badge
                        variant="destructive"
                        className="ml-1.5 px-1.5 py-0 text-[10px]"
                      >
                        {liveCount} LIVE
                      </Badge>
                    )}
                  </TabsTrigger>
                )
              })}
            </TabsList>

            {tabs.map(({ key, events }) => (
              <TabsContent key={key} value={key} className="mt-3">
                {events.length === 0 ? (
                  <div className="rounded-lg border border-dashed p-8 text-center text-sm text-muted-foreground">
                    No {DURATION_LABELS[key]} markets found
                  </div>
                ) : (
                  <div className="grid grid-cols-1 gap-3 md:grid-cols-2 lg:grid-cols-3">
                    {events.map((evt) => (
                      <EventCard key={evt.id} event={evt} />
                    ))}
                  </div>
                )}
              </TabsContent>
            ))}
          </Tabs>
        ))}
    </div>
  )
}
