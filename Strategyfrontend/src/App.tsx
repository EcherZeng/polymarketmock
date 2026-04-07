import { Routes, Route, Link, useLocation } from "react-router-dom"
import { cn } from "@/lib/utils"
import { TooltipProvider } from "@/components/ui/tooltip"
import { Toaster } from "@/components/ui/sonner"
import { useConnectionStatus } from "@/hooks/useConnectionStatus"
import StrategyPage from "@/pages/StrategyPage"
import ResultsListPage from "@/pages/ResultsListPage"
import ResultDetailPage from "@/pages/ResultDetailPage"
import DashboardPage from "@/pages/DashboardPage"
import BatchDashboardPage from "@/pages/BatchDashboardPage"
import BatchDetailPage from "@/pages/BatchDetailPage"
import DataCleanupPage from "@/pages/DataCleanupPage"
import ResultsCleanupPage from "@/pages/ResultsCleanupPage"
import PortfoliosPage from "@/pages/PortfoliosPage"
import PortfolioDetailPage from "@/pages/PortfolioDetailPage"
import AiOptimizePage from "@/pages/AiOptimizePage"
import AiOptimizeDetailPage from "@/pages/AiOptimizeDetailPage"

const navItems = [
  { to: "/", label: "策略回测" },
  { to: "/batch", label: "批量回测" },
  { to: "/results", label: "回测结果" },
  { to: "/portfolios", label: "数据组合" },
  { to: "/ai-optimize", label: "AI 优化" },
  { to: "/dashboard", label: "仪表盘" },
  { to: "/cleanup", label: "数据清理" },
  { to: "/results-cleanup", label: "结果清理" },
]

export default function App() {
  const location = useLocation()
  useConnectionStatus()

  return (
    <TooltipProvider>
    <div className="flex min-h-screen flex-col bg-background text-foreground">
      <header className="border-b">
        <div className="mx-auto flex h-14 max-w-7xl items-center gap-6 px-4">
          <Link to="/" className="text-lg font-semibold tracking-tight">
            Strategy Engine
          </Link>
          <nav className="flex gap-4">
            {navItems.map((item) => (
              <Link
                key={item.to}
                to={item.to}
                className={cn(
                  "text-sm transition-colors hover:text-foreground",
                  location.pathname === item.to
                    || (item.to === "/batch" && location.pathname.startsWith("/batch"))
                    || (item.to === "/portfolios" && location.pathname.startsWith("/portfolios"))
                    || (item.to === "/ai-optimize" && location.pathname.startsWith("/ai-optimize"))
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
      <main className="mx-auto w-full max-w-7xl flex-1 px-4 py-4">
        <Routes>
          <Route path="/" element={<StrategyPage />} />
          <Route path="/batch" element={<BatchDashboardPage />} />
          <Route path="/batch/:batchId" element={<BatchDetailPage />} />
          <Route path="/results" element={<ResultsListPage />} />
          <Route path="/results/:sessionId" element={<ResultDetailPage />} />
          <Route path="/portfolios" element={<PortfoliosPage />} />
          <Route path="/portfolios/:portfolioId" element={<PortfolioDetailPage />} />
          <Route path="/ai-optimize" element={<AiOptimizePage />} />
          <Route path="/ai-optimize/:taskId" element={<AiOptimizeDetailPage />} />
          <Route path="/dashboard" element={<DashboardPage />} />
          <Route path="/cleanup" element={<DataCleanupPage />} />
          <Route path="/results-cleanup" element={<ResultsCleanupPage />} />
        </Routes>
      </main>
    </div>
    <Toaster richColors position="top-right" />
    </TooltipProvider>
  )
}
