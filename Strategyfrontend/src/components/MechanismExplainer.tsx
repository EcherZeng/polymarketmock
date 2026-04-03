import { useState } from "react"
import { Card, CardContent } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Separator } from "@/components/ui/separator"

/**
 * Top-of-page explainer: VWAP execution, orderbook walk-through,
 * tiered anchor price, and strategy parameters.
 */
export default function MechanismExplainer() {
  const [expanded, setExpanded] = useState(false)

  return (
    <Card className="border-dashed">
      <CardContent className="pt-4 pb-3">
        {/* Header row — always visible */}
        <div className="flex items-center justify-between">
          <div className="flex flex-wrap items-center gap-2 text-sm">
            <Badge variant="outline" className="border-blue-400 text-blue-500">执行 = VWAP</Badge>
            <Badge variant="outline" className="border-purple-400 text-purple-500">决策 = 锚点价格</Badge>
            <Badge variant="outline" className="border-amber-400 text-amber-600">参数 = 分层阈值</Badge>
            <span className="text-xs text-muted-foreground">
              买入吃 Ask 各档、卖出吃 Bid 各档，逐级成交取加权均价
            </span>
          </div>
          <button
            onClick={() => setExpanded(!expanded)}
            className="shrink-0 text-xs text-muted-foreground underline decoration-dotted hover:text-foreground"
          >
            {expanded ? "收起" : "展开详情"}
          </button>
        </div>

        {/* Collapsible detail */}
        {expanded && (
          <div className="mt-4 flex flex-col gap-5 text-xs leading-relaxed text-muted-foreground">
            {/* ─── Section 1: VWAP ─── */}
            <section>
              <h3 className="mb-1.5 text-sm font-semibold text-foreground">
                1. VWAP 是什么？（Volume-Weighted Average Price）
              </h3>
              <p>
                VWAP = <strong>成交量加权平均价</strong>。在 Polymarket CLOB 中，订单簿有多个价格档位，
                每档有不同的挂单量。当你要买入 100 份 shares 时，不可能只在一个价格成交——
                系统从最优价格开始，逐档吃掉挂单量，直到填满你需要的数量，最终成交价就是各档的加权平均。
              </p>
              <div className="mt-2 rounded-md bg-muted px-3 py-2 font-mono text-[11px]">
                VWAP = Σ(price_i × filled_i) / Σ(filled_i)
              </div>
              <p className="mt-1.5">
                举例：你需要 BUY 100 shares，ask 侧有：
              </p>
              <div className="mt-1 overflow-x-auto rounded-md border">
                <table className="w-full text-center text-[11px]">
                  <thead>
                    <tr className="border-b bg-muted/50">
                      <th className="px-3 py-1">档位</th>
                      <th className="px-3 py-1">Ask Price</th>
                      <th className="px-3 py-1">Size（可用量）</th>
                      <th className="px-3 py-1">本次吃入</th>
                      <th className="px-3 py-1">本档成本</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr className="border-b">
                      <td className="px-3 py-1">1（最优）</td>
                      <td className="px-3 py-1 text-red-500">$0.52</td>
                      <td className="px-3 py-1">60</td>
                      <td className="px-3 py-1 font-medium">60</td>
                      <td className="px-3 py-1">60 × 0.52 = $31.20</td>
                    </tr>
                    <tr className="border-b">
                      <td className="px-3 py-1">2</td>
                      <td className="px-3 py-1 text-red-500">$0.53</td>
                      <td className="px-3 py-1">80</td>
                      <td className="px-3 py-1 font-medium">40（剩余）</td>
                      <td className="px-3 py-1">40 × 0.53 = $21.20</td>
                    </tr>
                    <tr>
                      <td className="px-3 py-1" colSpan={3}></td>
                      <td className="px-3 py-1 font-medium">合计 100</td>
                      <td className="px-3 py-1 font-medium">$52.40</td>
                    </tr>
                  </tbody>
                </table>
              </div>
              <p className="mt-1.5">
                VWAP = $52.40 / 100 = <strong>$0.5240</strong>，
                比最优 ask $0.52 贵了一点——这就是<strong>滑点（Slippage）</strong>。
                数量越大、深度越浅，滑点越大。
              </p>
            </section>

            <Separator />

            {/* ─── Section 2: Orderbook Walk-Through ─── */}
            <section>
              <h3 className="mb-1.5 text-sm font-semibold text-foreground">
                2. 逐级吃单规则（Orderbook Walk-Through）
              </h3>
              <div className="flex flex-col gap-1.5">
                <p>
                  <strong className="text-green-500">BUY</strong> →
                  从 <code>ask_levels</code> 最低价开始向上吃（你在买，对手挂卖）
                </p>
                <p>
                  <strong className="text-red-500">SELL</strong> →
                  从 <code>bid_levels</code> 最高价开始向下吃（你在卖，对手挂买）
                </p>
              </div>
              <div className="mt-2 rounded-md bg-muted px-3 py-2 font-mono text-[11px]">
                <pre className="whitespace-pre-wrap">{`for (price, size) in levels:        # 按最优价排序
    fill_qty = min(remaining, size)  # 本档能吃多少
    cost     += fill_qty × price     # 累计成本
    filled   += fill_qty             # 累计成交
    remaining -= fill_qty            # 剩余需求
    if remaining ≤ 0: break          # 填满则停止`}</pre>
              </div>
              <p className="mt-1.5">额外约束：</p>
              <ul className="mt-1 flex flex-col gap-0.5 pl-4">
                <li>• <strong>预算上限</strong>（max_cost）：BUY 时余额不够就提前停止</li>
                <li>• <strong>价格底线</strong>（min_price）：SELL 时跳过低于门槛的 bid 档位</li>
                <li>• 所有运算用 <code>Decimal</code> 精确计算，避免浮点误差</li>
              </ul>
            </section>

            <Separator />

            {/* ─── Section 3: Anchor Price ─── */}
            <section>
              <h3 className="mb-1.5 text-sm font-semibold text-foreground">
                3. 锚点价格是什么？（Anchor Price）
              </h3>
              <p>
                锚点价格 = <strong>策略做决策时参考的价格</strong>。入场信号、止盈/止损触发都基于它。
                它不等于执行价（执行价由 VWAP 决定），而是一个尽可能准确的"当前市场公允价"。
              </p>
              <p className="mt-1.5">
                问题：简单的 <code>mid = (best_bid + best_ask) / 2</code> 在宽 spread 时不可靠。
                所以我们用<strong>三层分级</strong>：
              </p>
              <div className="mt-2 flex flex-col gap-2">
                <div className="flex items-start gap-2 rounded-md border p-2">
                  <Badge variant="outline" className="mt-0.5 shrink-0 border-blue-400 text-blue-500">Tier 1</Badge>
                  <div>
                    <p><strong>Mid Price</strong> — 当 <code>spread &lt; 0.05</code></p>
                    <div className="mt-1 rounded bg-muted px-2 py-0.5 font-mono">anchor = (best_bid + best_ask) / 2</div>
                    <p className="mt-0.5 text-[11px]">订单簿紧密，Mid 就是最好的参考。</p>
                  </div>
                </div>
                <div className="flex items-start gap-2 rounded-md border p-2">
                  <Badge variant="outline" className="mt-0.5 shrink-0 border-purple-400 text-purple-500">Tier 2</Badge>
                  <div>
                    <p><strong>Micro-price（前 3 档深度加权）</strong> — 当 <code>0.05 ≤ spread &lt; 0.15</code></p>
                    <div className="mt-1 rounded bg-muted px-2 py-0.5 font-mono text-[11px]">
                      anchor = (Σ bid_i × ΣV_ask + Σ ask_i × ΣV_bid) / (N_bid × ΣV_ask + N_ask × ΣV_bid)
                    </div>
                    <p className="mt-0.5 text-[11px]">
                      取买卖各前 3 档，用对侧总量交叉加权。买方量大 → 价格靠 ask（买压推升），
                      卖方量大 → 价格靠 bid。多档纳入避免单档噪声。
                    </p>
                  </div>
                </div>
                <div className="flex items-start gap-2 rounded-md border p-2">
                  <Badge variant="outline" className="mt-0.5 shrink-0 border-amber-400 text-amber-600">Tier 3</Badge>
                  <div>
                    <p><strong>Last Trade Price</strong> — 当 <code>spread ≥ 0.15</code>（且有成交记录）</p>
                    <div className="mt-1 rounded bg-muted px-2 py-0.5 font-mono">anchor = last_trade_price</div>
                    <p className="mt-0.5 text-[11px]">
                      Spread 过大，Mid 不可信（Polymarket 官方也在 spread &gt; 0.10 时切换到 last trade price 展示）。
                    </p>
                  </div>
                </div>
              </div>
            </section>

            <Separator />

            {/* ─── Section 4: Strategy Parameters ─── */}
            <section>
              <h3 className="mb-1.5 text-sm font-semibold text-foreground">
                4. 策略参数基于什么？
              </h3>
              <p>所有策略参数最终都围绕<strong>锚点价格</strong>和<strong>订单簿状态</strong>做判断：</p>
              <div className="mt-2 overflow-x-auto rounded-md border">
                <table className="w-full text-[11px]">
                  <thead>
                    <tr className="border-b bg-muted/50">
                      <th className="px-3 py-1.5 text-left">参数</th>
                      <th className="px-3 py-1.5 text-left">含义</th>
                      <th className="px-3 py-1.5 text-left">基于</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr className="border-b">
                      <td className="px-3 py-1"><code>entry_threshold</code></td>
                      <td className="px-3 py-1">价格低于此阈值时才考虑买入</td>
                      <td className="px-3 py-1">锚点价格 vs 阈值</td>
                    </tr>
                    <tr className="border-b">
                      <td className="px-3 py-1"><code>take_profit</code></td>
                      <td className="px-3 py-1">锚点涨到买入价 + TP 时触发卖出</td>
                      <td className="px-3 py-1">锚点价格 vs 买入均价</td>
                    </tr>
                    <tr className="border-b">
                      <td className="px-3 py-1"><code>stop_loss</code></td>
                      <td className="px-3 py-1">锚点跌到买入价 - SL 时触发止损</td>
                      <td className="px-3 py-1">锚点价格 vs 买入均价</td>
                    </tr>
                    <tr className="border-b">
                      <td className="px-3 py-1"><code>max_spread</code></td>
                      <td className="px-3 py-1">Spread 超过此值时拒绝入场</td>
                      <td className="px-3 py-1">订单簿 Spread</td>
                    </tr>
                    <tr className="border-b">
                      <td className="px-3 py-1"><code>max_ask_deviation</code></td>
                      <td className="px-3 py-1">Ask 偏离锚点过远时拒绝入场</td>
                      <td className="px-3 py-1">(best_ask - anchor) / anchor</td>
                    </tr>
                    <tr>
                      <td className="px-3 py-1"><code>min_profit_room</code></td>
                      <td className="px-3 py-1">ask 到 1.0 的空间太小时不入场</td>
                      <td className="px-3 py-1">1.0 - best_ask</td>
                    </tr>
                  </tbody>
                </table>
              </div>
              <p className="mt-2">
                <strong>核心原则</strong>：策略用锚点价格做"看不见的参考价"来判断要不要交易；
                而实际交易时，系统通过 VWAP 逐级吃 orderbook，成交价可能和锚点有偏差——这个偏差就是滑点。
              </p>
            </section>

            <Separator />

            {/* ─── Quick summary diagram ─── */}
            <section>
              <h3 className="mb-1.5 text-sm font-semibold text-foreground">总结流程</h3>
              <div className="rounded-md bg-muted px-3 py-2 font-mono text-[11px]">
                <pre className="whitespace-pre-wrap">{`Orderbook Tick
  │
  ├─ 计算 spread = best_ask - best_bid
  │
  ├─ 分层选定锚点 ──┐
  │   Tier1: Mid     │  spread < 0.05
  │   Tier2: Micro   │  0.05 ≤ spread < 0.15（前3档加权）
  │   Tier3: Last    │  spread ≥ 0.15
  │                  │
  │  ┌───────────────┘
  │  │
  │  ▼  策略决策
  │  ├─ anchor < entry_threshold?  → 产生 BUY 信号
  │  ├─ anchor > buy_avg + TP?     → 产生 SELL 信号（止盈）
  │  └─ anchor < buy_avg - SL?     → 产生 SELL 信号（止损）
  │
  ▼  执行（VWAP）
  BUY  → 逐级吃 ask_levels（从最低价向上）
  SELL → 逐级吃 bid_levels（从最高价向下）
  成交价 = Σ(price × qty) / Σ(qty)`}</pre>
              </div>
            </section>
          </div>
        )}
      </CardContent>
    </Card>
  )
}
