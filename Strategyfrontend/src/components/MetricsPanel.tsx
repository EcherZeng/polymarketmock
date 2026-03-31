import { useState } from "react"
import { InfoIcon } from "lucide-react"
import type { EvaluationMetrics } from "@/types"
import { cn } from "@/lib/utils"
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip"

interface MetricsPanelProps {
  metrics: EvaluationMetrics
}

/** Metric label → tooltip description */
const METRIC_TIPS: Record<string, string> = {
  "总收益":       "回测期间的绝对盈亏金额",
  "收益率":       "总收益 / 初始资金 × 100%",
  "胜率":         "盈利交易占总交易数的百分比",
  "最大回撤":     "权益曲线从峰值到谷值的最大跌幅百分比",
  "Sharpe":       "夏普比率 = 超额收益 / 波动率, 衡量风险调整后收益",
  "盈亏比":       "总盈利 / 总亏损, >1 表示盈利能力强于亏损",
  "总交易数":     "回测期间执行的买入+卖出交易总数",
  "平均滑点":     "实际成交价与触发价之间的平均偏差百分比",
  "结算盈亏":     "持有到事件结算时的盈亏（二元市场按 $1/$0 结算）",
  "交易盈亏":     "交易过程中买卖差价产生的盈亏",
  "持有到期比例": "持有到结算的仓位占总交易仓位的比例",
  "平均入场价":   "所有买入交易的加权平均成交价格",
  "期望值/股":    "每股的预期收益 = (结算价 - 入场价) × 胜率",
  "Sortino":      "索提诺比率 = 超额收益 / 下行偏差, 只惩罚亏损波动",
  "Calmar":       "卡玛比率 = 年化收益 / 最大回撤, 衡量长期风险回报",
  "年化收益":     "将回测期收益换算为年度收益率",
  "波动率":       "收益率的标准差, 衡量收益的波动程度",
  "下行偏差":     "仅计算负收益的标准差, 衡量亏损的波动",
  "平均盈利":     "所有盈利交易的平均利润",
  "平均亏损":     "所有亏损交易的平均损失",
  "最佳交易":     "单笔最大盈利金额",
  "最差交易":     "单笔最大亏损金额",
  "买入/卖出":    "买入交易次数 / 卖出交易次数",
  "回撤持续":     "最大回撤从峰值到恢复所经历的 tick 数",
}

interface MetricCard {
  label: string
  value: string
  color?: "green" | "red" | "default"
}

function CardGrid({ cards, cols = "grid-cols-2 sm:grid-cols-4 lg:grid-cols-8" }: { cards: MetricCard[]; cols?: string }) {
  return (
    <div className={cn("grid gap-3", cols)}>
      {cards.map((card) => {
        const tip = METRIC_TIPS[card.label]
        return (
          <div key={card.label} className="rounded-lg border p-3">
            <div className="flex items-center gap-1 text-xs text-muted-foreground">
              <span>{card.label}</span>
              {tip && (
                <Tooltip>
                  <TooltipTrigger asChild>
                    <InfoIcon className="size-3 shrink-0 cursor-help text-muted-foreground/60" />
                  </TooltipTrigger>
                  <TooltipContent side="top">
                    <p>{tip}</p>
                  </TooltipContent>
                </Tooltip>
              )}
            </div>
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
        )
      })}
    </div>
  )
}

export default function MetricsPanel({ metrics }: MetricsPanelProps) {
  const [showDetail, setShowDetail] = useState(false)

  // ── Core metrics (always visible) ──
  const coreCards: MetricCard[] = [
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
      label: "胜率",
      value: `${metrics.win_rate.toFixed(1)}%`,
      color: metrics.win_rate >= 50 ? "green" : "red",
    },
    { label: "最大回撤", value: `${metrics.max_drawdown.toFixed(2)}%`, color: "red" },
    {
      label: "Sharpe",
      value: metrics.sharpe_ratio.toFixed(4),
      color: metrics.sharpe_ratio > 0 ? "green" : "red",
    },
    {
      label: "盈亏比",
      value: metrics.profit_factor === Infinity ? "∞" : metrics.profit_factor.toFixed(2),
      color: metrics.profit_factor > 1 ? "green" : "red",
    },
    { label: "总交易数", value: `${metrics.total_trades}` },
    {
      label: "平均滑点",
      value: `${metrics.avg_slippage.toFixed(4)}%`,
    },
  ]

  // ── BTC prediction market metrics ──
  const btcCards: MetricCard[] = [
    {
      label: "结算盈亏",
      value: `$${metrics.settlement_pnl.toFixed(2)}`,
      color: metrics.settlement_pnl >= 0 ? "green" : "red",
    },
    {
      label: "交易盈亏",
      value: `$${metrics.trade_pnl.toFixed(2)}`,
      color: metrics.trade_pnl >= 0 ? "green" : "red",
    },
    {
      label: "持有到期比例",
      value: `${metrics.hold_to_settlement_ratio.toFixed(1)}%`,
    },
    {
      label: "平均入场价",
      value: `$${metrics.avg_entry_price.toFixed(4)}`,
    },
    {
      label: "期望值/股",
      value: `$${metrics.expected_value >= 0 ? "+" : ""}${metrics.expected_value.toFixed(4)}`,
      color: metrics.expected_value >= 0 ? "green" : "red",
    },
  ]

  // ── Detailed metrics (collapsible) ──
  const detailCards: MetricCard[] = [
    {
      label: "Sortino",
      value: metrics.sortino_ratio.toFixed(4),
      color: metrics.sortino_ratio > 0 ? "green" : "red",
    },
    {
      label: "Calmar",
      value: metrics.calmar_ratio.toFixed(4),
    },
    {
      label: "年化收益",
      value: `${metrics.annualized_return.toFixed(2)}%`,
      color: metrics.annualized_return >= 0 ? "green" : "red",
    },
    {
      label: "波动率",
      value: metrics.volatility.toFixed(6),
    },
    {
      label: "下行偏差",
      value: metrics.downside_deviation.toFixed(6),
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
      label: "买入/卖出",
      value: `${metrics.buy_count} / ${metrics.sell_count}`,
    },
    {
      label: "回撤持续",
      value: `${metrics.max_drawdown_duration.toFixed(0)} ticks`,
    },
  ]

  return (
    <div className="flex flex-col gap-4">
      {/* Core metrics */}
      <CardGrid cards={coreCards} />

      {/* BTC prediction section */}
      <div>
        <div className="mb-2 text-xs font-medium text-muted-foreground">二元结算指标</div>
        <CardGrid cards={btcCards} cols="grid-cols-2 sm:grid-cols-3 lg:grid-cols-5" />
      </div>

      {/* Collapsible detailed section */}
      <div>
        <button
          onClick={() => setShowDetail(!showDetail)}
          className="mb-2 text-xs font-medium text-muted-foreground hover:text-foreground transition-colors"
        >
          {showDetail ? "▾ 收起详细指标" : "▸ 展开详细指标"}
        </button>
        {showDetail && <CardGrid cards={detailCards} />}
      </div>
    </div>
  )
}
