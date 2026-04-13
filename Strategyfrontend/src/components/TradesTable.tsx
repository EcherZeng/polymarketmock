import { cn, fmtTimeCst } from "@/lib/utils"
import type { TradeRecord } from "@/types"

interface TradesTableProps {
  trades: TradeRecord[]
}

export default function TradesTable({ trades }: TradesTableProps) {
  return (
    <div className="max-h-96 overflow-auto">
      <table className="w-full text-sm">
        <thead className="sticky top-0 bg-background">
          <tr className="border-b">
            <th className="px-2 py-1.5 text-left text-xs font-medium text-muted-foreground">#</th>
            <th className="px-2 py-1.5 text-left text-xs font-medium text-muted-foreground">时间</th>
            <th className="px-2 py-1.5 text-left text-xs font-medium text-muted-foreground">方向</th>
            <th className="px-2 py-1.5 text-right text-xs font-medium text-muted-foreground">数量</th>
            <th className="px-2 py-1.5 text-right text-xs font-medium text-muted-foreground">均价</th>
            <th className="px-2 py-1.5 text-right text-xs font-medium text-muted-foreground">总额</th>
            <th className="px-2 py-1.5 text-right text-xs font-medium text-muted-foreground">滑点</th>
            <th className="px-2 py-1.5 text-right text-xs font-medium text-muted-foreground">余额</th>
            <th className="px-2 py-1.5 text-right text-xs font-medium text-muted-foreground">持仓</th>
          </tr>
        </thead>
        <tbody>
          {trades.map((t, i) => (
            <tr key={i} className="border-b hover:bg-muted/30">
              <td className="px-2 py-1.5 text-xs text-muted-foreground">{i + 1}</td>
              <td className="px-2 py-1.5 text-xs">{fmtTimeCst(t.timestamp)}</td>
              <td className="px-2 py-1.5">
                <span
                  className={cn(
                    "rounded px-1.5 py-0.5 text-xs font-medium",
                    t.side === "BUY"
                      ? "bg-emerald-100 text-emerald-700"
                      : "bg-red-100 text-red-700",
                  )}
                >
                  {t.side}
                </span>
              </td>
              <td className="px-2 py-1.5 text-right font-mono text-xs">{t.filled_amount.toFixed(2)}</td>
              <td className="px-2 py-1.5 text-right font-mono text-xs">${t.avg_price.toFixed(4)}</td>
              <td className="px-2 py-1.5 text-right font-mono text-xs">${t.total_cost.toFixed(2)}</td>
              <td className="px-2 py-1.5 text-right font-mono text-xs">
                {t.slippage_pct.toFixed(2)}%
              </td>
              <td className="px-2 py-1.5 text-right font-mono text-xs">${t.balance_after.toFixed(2)}</td>
              <td className="px-2 py-1.5 text-right font-mono text-xs">{t.position_after.toFixed(2)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
