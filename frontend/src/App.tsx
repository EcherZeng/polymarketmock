import { Routes, Route, Link, useLocation } from "react-router-dom"
import { cn } from "@/lib/utils"
import EventListPage from "@/pages/EventListPage"
import EventDetailPage from "@/pages/EventDetailPage"
import TradingDashboard from "@/pages/TradingDashboard"
import HistoryPage from "@/pages/HistoryPage"

const navItems = [
  { to: "/", label: "Events" },
  { to: "/trading", label: "Trading" },
  { to: "/history", label: "History" },
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
            {navItems.map((item) => (
              <Link
                key={item.to}
                to={item.to}
                className={cn(
                  "text-sm font-medium transition-colors hover:text-primary",
                  location.pathname === item.to
                    ? "text-primary"
                    : "text-muted-foreground",
                )}
              >
                {item.label}
              </Link>
            ))}
          </nav>
        </div>
      </header>
      <main className="mx-auto w-full max-w-7xl flex-1 px-4 py-4">
        <Routes>
          <Route path="/" element={<EventListPage />} />
          <Route path="/event/:slug" element={<EventDetailPage />} />
          <Route path="/trading" element={<TradingDashboard />} />
          <Route path="/history" element={<HistoryPage />} />
        </Routes>
      </main>
    </div>
  )
}
