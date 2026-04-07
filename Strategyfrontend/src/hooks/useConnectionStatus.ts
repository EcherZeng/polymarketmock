import { useEffect, useRef } from "react"
import { useQueryClient } from "@tanstack/react-query"
import { toast } from "sonner"

/**
 * Monitors react-query global error/success events to detect backend connectivity.
 * Shows a persistent toast when queries fail consecutively, and a recovery toast when
 * connectivity is restored.
 */
export function useConnectionStatus() {
  const queryClient = useQueryClient()
  const failCountRef = useRef(0)
  const disconnectedRef = useRef(false)
  const toastIdRef = useRef<string | number | undefined>(undefined)

  useEffect(() => {
    const cache = queryClient.getQueryCache()

    const unsubscribe = cache.subscribe((event) => {
      if (!event?.query) return

      // Only track polling queries (ones with refetchInterval, i.e. running tasks)
      const state = event.query.state

      if (event.type === "updated" && state.status === "error") {
        failCountRef.current += 1
        // After 2 consecutive failures (~4-6s of polling), show disconnect toast
        if (failCountRef.current >= 2 && !disconnectedRef.current) {
          disconnectedRef.current = true
          toastIdRef.current = toast.error("与服务器的连接已断开", {
            description: "正在尝试重新连接...",
            duration: Infinity,
            id: "connection-status",
          })
        }
      }

      if (event.type === "updated" && state.status === "success") {
        if (disconnectedRef.current) {
          disconnectedRef.current = false
          toast.success("连接已恢复", {
            id: "connection-status",
            duration: 3000,
          })
        }
        failCountRef.current = 0
      }
    })

    return () => unsubscribe()
  }, [queryClient])
}
