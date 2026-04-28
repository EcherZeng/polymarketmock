import { Routes, Route, Link, useLocation } from "react-router-dom"
import { cn } from "@/lib/utils"
import { TooltipProvider } from "@/components/ui/tooltip"
import { Toaster } from "@/components/ui/sonner"
import { Badge } from "@/components/ui/badge"
import { useConfigState } from "@/hooks/useTradeData"
import DashboardPage from "@/pages/DashboardPage"
import LiveSessionPage from "@/pages/LiveSessionPage"
import SessionsPage from "@/pages/SessionsPage"
import SessionDetailPage from "@/pages/SessionDetailPage"
import SettingsPage from "@/pages/SettingsPage"

const navItems = [
  { to: "/", label: "仪表盘" },
  { to: "/live", label: "实时场次" },
  { to: "/sessions", label: "Sessions" },
  { to: "/settings", label: "配置" },
]

function ExecutorModeBadge() {
  const { data: config } = useConfigState()
  const mode = config?.executor_mode
  if (!mode) return null
  const isReal = mode === "real"
  return (
    <Badge className={cn(
      "text-xs font-medium",
      isReal
        ? "bg-red-100 text-red-700 dark:bg-red-900 dark:text-red-300"
        : "bg-blue-100 text-blue-700 dark:bg-blue-900 dark:text-blue-300"
    )}>
      {isReal ? "真实交易" : "模拟交易"}
    </Badge>
  )
}

export default function App() {
  const location = useLocation()

  return (
    <TooltipProvider>
      <div className="flex min-h-screen flex-col bg-background text-foreground">
        <header className="border-b">
          <div className="mx-auto flex h-14 max-w-6xl items-center gap-6 px-4">
            <div className="flex items-center gap-2">
              <Link to="/" className="text-lg font-semibold tracking-tight">
                Live Trade
              </Link>
              <ExecutorModeBadge />
            </div>
            <nav className="flex gap-4">
              {navItems.map((item) => (
                <Link
                  key={item.to}
                  to={item.to}
                  className={cn(
                    "text-sm transition-colors hover:text-foreground",
                    location.pathname === item.to
                      || (item.to === "/sessions" && location.pathname.startsWith("/sessions"))
                      || (item.to === "/live" && location.pathname === "/live")
                      ? "text-foreground font-medium"
                      : "text-muted-foreground",
                  )}
                >
                  {item.label}
                </Link>
              ))}
            </nav>
          </div>
        </header>

        <main className="mx-auto w-full max-w-6xl flex-1 px-4 py-6">
          <Routes>
            <Route path="/" element={<DashboardPage />} />
            <Route path="/live" element={<LiveSessionPage />} />
            <Route path="/sessions" element={<SessionsPage />} />
            <Route path="/sessions/:slug" element={<SessionDetailPage />} />
            <Route path="/settings" element={<SettingsPage />} />
          </Routes>
        </main>
      </div>
      <Toaster />
    </TooltipProvider>
  )
}
