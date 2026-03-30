import { Routes, Route, Link, useLocation } from "react-router-dom"
import { cn } from "@/lib/utils"
import ErrorBoundary from "@/components/ErrorBoundary"
import EventListPage from "@/pages/EventListPage"
import EventDetailPage from "@/pages/EventDetailPage"
import TradingDashboard from "@/pages/TradingDashboard"
import HistoryPage from "@/pages/HistoryPage"
import ReplayPage from "@/pages/ReplayPage"
import SessionHistoryPage from "@/pages/SessionHistoryPage"
import MonitorPage from "@/pages/MonitorPage"

const navItems = [
  { to: "/", label: "Events" },
  { to: "/sessions", label: "Sessions" },
  { to: "/trading", label: "Trading" },
  { to: "/history", label: "History" },
  { to: "/monitor", label: "Monitor" },
]

export default function App() {
  const location = useLocation()

  return (
    <div className="flex min-h-screen flex-col bg-background text-foreground">
      <header className="border-b">
        <div className="mx-auto flex h-14 max-w-7xl items-center gap-6 px-4">
          <Link to="/" className="text-lg font-semibold tracking-tight">
            Polymarket Mock
          </Link>
          <nav className="flex gap-4">
            {navItems.map((item) => {
              const active =
                item.to === "/"
                  ? location.pathname === "/"
                  : item.to === "/sessions"
                    ? location.pathname === "/sessions" ||
                      location.pathname.startsWith("/replay/")
                    : location.pathname.startsWith(item.to)
              return (
                <Link
                  key={item.to}
                  to={item.to}
                  className={cn(
                    "text-sm font-medium transition-colors hover:text-primary",
                    active ? "text-primary" : "text-muted-foreground",
                  )}
                >
                  {item.label}
                </Link>
              )
            })}
          </nav>
        </div>
      </header>
      <main className="mx-auto w-full max-w-7xl flex-1 px-4 py-4">
        <ErrorBoundary>
          <Routes>
            <Route path="/" element={<EventListPage />} />
            <Route path="/event/:slug" element={<EventDetailPage />} />
            <Route path="/sessions" element={<SessionHistoryPage />} />
            <Route path="/replay/:slug" element={<ReplayPage />} />
            <Route path="/trading" element={<TradingDashboard />} />
            <Route path="/history" element={<HistoryPage />} />
            <Route path="/monitor" element={<MonitorPage />} />
          </Routes>
        </ErrorBoundary>
      </main>
    </div>
  )
}
