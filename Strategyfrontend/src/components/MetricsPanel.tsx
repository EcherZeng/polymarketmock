import type { EvaluationMetrics } from "@/types"
import { cn } from "@/lib/utils"

interface MetricsPanelProps {
  metrics: EvaluationMetrics
}

interface MetricCard {
  label: string
  value: string
  color?: "green" | "red" | "default"
}

export default function MetricsPanel({ metrics }: MetricsPanelProps) {
  const cards: MetricCard[] = [
    {
      label: "总收益",
      value: `$${metrics.total_pnl.toFixed(2)}`,
      color: metrics.total_pnl >= 0 ? "green" : "red",
    },
    {
      label: "收益率",
      value: `${metrics.total_return_pct >= 0 ? "+" : ""}${metrics.total_return_pct.toFixed(2)}%`,
      color: metrics.total_return_pct >= 0 ? "green" : "red",
    },
    {
      label: "Sharpe Ratio",
      value: metrics.sharpe_ratio.toFixed(4),
      color: metrics.sharpe_ratio > 0 ? "green" : "red",
    },
    {
      label: "Sortino Ratio",
      value: metrics.sortino_ratio.toFixed(4),
      color: metrics.sortino_ratio > 0 ? "green" : "red",
    },
    { label: "最大回撤", value: `${metrics.max_drawdown.toFixed(2)}%`, color: "red" },
    {
      label: "Calmar Ratio",
      value: metrics.calmar_ratio.toFixed(4),
    },
    {
      label: "胜率",
      value: `${metrics.win_rate.toFixed(1)}%`,
      color: metrics.win_rate >= 50 ? "green" : "red",
    },
    {
      label: "盈亏比",
      value: metrics.profit_factor === Infinity ? "∞" : metrics.profit_factor.toFixed(2),
      color: metrics.profit_factor > 1 ? "green" : "red",
    },
    { label: "总交易数", value: `${metrics.total_trades}` },
    {
      label: "买入/卖出",
      value: `${metrics.buy_count} / ${metrics.sell_count}`,
    },
    {
      label: "平均盈利",
      value: `$${metrics.avg_win.toFixed(4)}`,
      color: "green",
    },
    {
      label: "平均亏损",
      value: `$${metrics.avg_loss.toFixed(4)}`,
      color: "red",
    },
    {
      label: "最佳交易",
      value: `$${metrics.best_trade.toFixed(4)}`,
      color: "green",
    },
    {
      label: "最差交易",
      value: `$${metrics.worst_trade.toFixed(4)}`,
      color: "red",
    },
    {
      label: "平均滑点",
      value: `${metrics.avg_slippage.toFixed(4)}%`,
    },
    {
      label: "波动率",
      value: metrics.volatility.toFixed(6),
    },
  ]

  return (
    <div className="grid grid-cols-2 gap-3 sm:grid-cols-4 lg:grid-cols-8">
      {cards.map((card) => (
        <div key={card.label} className="rounded-lg border p-3">
          <div className="text-xs text-muted-foreground">{card.label}</div>
          <div
            className={cn(
              "mt-1 text-sm font-semibold",
              card.color === "green" && "text-emerald-600",
              card.color === "red" && "text-red-500",
            )}
          >
            {card.value}
          </div>
        </div>
      ))}
    </div>
  )
}
