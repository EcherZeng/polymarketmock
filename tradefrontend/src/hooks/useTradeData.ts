import { useQuery } from "@tanstack/react-query"
import { tradeApi } from "@/api/trade"

/** Historical sessions list — for SessionsPage. Polling only when needed. */
export function useSessions(limit = 50) {
  return useQuery({
    queryKey: ["trade", "sessions", limit],
    queryFn: () => tradeApi.sessions(limit),
    refetchInterval: 30_000,
  })
}

export function useSessionDetail(slug: string) {
  return useQuery({
    queryKey: ["trade", "session", slug],
    queryFn: () => tradeApi.sessionDetail(slug),
    enabled: !!slug,
  })
}

/** Strategy catalog — available strategies & composites. Fetched once on mount. */
export function useCatalog() {
  return useQuery({
    queryKey: ["trade", "catalog"],
    queryFn: tradeApi.catalog,
    staleTime: 5 * 60 * 1000,
  })
}

/** Current strategy state — active preset, config, composite. Instant (no external calls). */
export function useConfigState() {
  return useQuery({
    queryKey: ["trade", "config-state"],
    queryFn: tradeApi.config,
  })
}
