import { useQuery } from "@tanstack/react-query"
import { tradeApi } from "@/api/trade"

export function useStatus() {
  return useQuery({
    queryKey: ["trade", "status"],
    queryFn: tradeApi.status,
    refetchInterval: 3000,
  })
}

export function usePositions() {
  return useQuery({
    queryKey: ["trade", "positions"],
    queryFn: tradeApi.positions,
    refetchInterval: 5000,
  })
}

export function useBalance() {
  return useQuery({
    queryKey: ["trade", "balance"],
    queryFn: tradeApi.balance,
    refetchInterval: 5000,
  })
}

export function usePnl() {
  return useQuery({
    queryKey: ["trade", "pnl"],
    queryFn: tradeApi.pnl,
    refetchInterval: 10000,
  })
}

export function useSessions(limit = 50) {
  return useQuery({
    queryKey: ["trade", "sessions", limit],
    queryFn: () => tradeApi.sessions(limit),
    refetchInterval: 10000,
  })
}

export function useSessionDetail(slug: string) {
  return useQuery({
    queryKey: ["trade", "session", slug],
    queryFn: () => tradeApi.sessionDetail(slug),
    enabled: !!slug,
  })
}

export function useTrades(sessionSlug?: string, limit = 100) {
  return useQuery({
    queryKey: ["trade", "trades", sessionSlug, limit],
    queryFn: () => tradeApi.trades(sessionSlug, limit),
    refetchInterval: 10000,
  })
}

export function useConfig() {
  return useQuery({
    queryKey: ["trade", "config"],
    queryFn: tradeApi.config,
  })
}
