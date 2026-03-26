import { useState } from "react"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { Button } from "@/components/ui/button"
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { Separator } from "@/components/ui/separator"
import { Spinner } from "@/components/ui/spinner"
import { estimateOrder, fetchMidpoint, placeOrder } from "@/api/client"
import type { EstimateResult, OrderSide, OrderType, WsBestBidAskEvent } from "@/types"

interface TradingPanelProps {
  tokenId: string
  outcomes?: string[]
  tokenIds?: string[]
  onSwitchToken?: (tokenId: string) => void
  /** WS best_bid_ask event (if provided, HTTP polling is reduced) */
  wsBestBidAsk?: WsBestBidAskEvent | null
  wsConnected?: boolean
}

export default function TradingPanel({
  tokenId,
  outcomes = [],
  tokenIds = [],
  onSwitchToken,
  wsBestBidAsk,
  wsConnected,
}: TradingPanelProps) {
  const queryClient = useQueryClient()
  const [side, setSide] = useState<OrderSide>("BUY")
  const [orderType, setOrderType] = useState<OrderType>("MARKET")
  const [amount, setAmount] = useState("")
  const [price, setPrice] = useState("")
  const [estimate, setEstimate] = useState<EstimateResult | null>(null)

  // Real-time midpoint — prefer WS, fallback to HTTP polling
  const hasWsBBA = !!(wsConnected && wsBestBidAsk)
  const { data: midData } = useQuery({
    queryKey: ["midpoint", tokenId],
    queryFn: () => fetchMidpoint(tokenId),
    enabled: !!tokenId && !hasWsBBA,
    refetchInterval: hasWsBBA ? false : 3_000,
  })

  // Derive midPrice: WS best_bid_ask → HTTP midpoint → 0
  const wsMid = wsBestBidAsk
    ? (parseFloat(wsBestBidAsk.best_bid) + parseFloat(wsBestBidAsk.best_ask)) / 2
    : null
  const midPrice = wsMid ?? midData?.mid ?? 0
  const compPrice = midPrice > 0 ? 1 - midPrice : 0

  // Determine current outcome index
  const currentIdx = tokenIds.indexOf(tokenId)

  // Map prices to correct outcome positions (midPrice is for the selected token)
  const price0 = currentIdx === 1 ? compPrice : midPrice
  const price1 = currentIdx === 1 ? midPrice : compPrice
  const currentOutcome = currentIdx >= 0 && currentIdx < outcomes.length ? outcomes[currentIdx] : "Yes"
  const compIdx = currentIdx === 0 ? 1 : 0
  const compOutcome = compIdx < outcomes.length ? outcomes[compIdx] : "No"
  const compTokenId = compIdx < tokenIds.length ? tokenIds[compIdx] : ""

  const estimateMutation = useMutation({
    mutationFn: () =>
      estimateOrder({
        token_id: tokenId,
        side,
        type: orderType,
        amount: parseFloat(amount),
        price: orderType === "LIMIT" ? parseFloat(price) : undefined,
      }),
    onSuccess: (data) => setEstimate(data),
  })

  const orderMutation = useMutation({
    mutationFn: () =>
      placeOrder({
        token_id: tokenId,
        side,
        type: orderType,
        amount: parseFloat(amount),
        price: orderType === "LIMIT" ? parseFloat(price) : undefined,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["account"] })
      queryClient.invalidateQueries({ queryKey: ["positions"] })
      queryClient.invalidateQueries({ queryKey: ["orders"] })
      queryClient.invalidateQueries({ queryKey: ["activityFeed"] })
      setAmount("")
      setPrice("")
      setEstimate(null)
    },
  })

  const canEstimate =
    parseFloat(amount) > 0 && (orderType === "MARKET" || parseFloat(price) > 0)
  const canOrder = canEstimate && !orderMutation.isPending

  const shares = parseFloat(amount) || 0

  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-sm">交易</CardTitle>
      </CardHeader>
      <CardContent>
        {/* ── Probability overview ── */}
        {midPrice > 0 && outcomes.length >= 2 && (
          <>
            <div className="mb-3 grid grid-cols-2 gap-2 text-center">
              <div
                className={`rounded-md px-2 py-1.5 ${
                  currentIdx === 0
                    ? "bg-emerald-500/10 ring-1 ring-emerald-500/30"
                    : "bg-muted"
                }`}
              >
                <div className="text-xs text-muted-foreground">{outcomes[0]}</div>
                <div className="text-lg font-bold tabular-nums">
                  {(price0 * 100).toFixed(1)}¢
                </div>
              </div>
              <div
                className={`rounded-md px-2 py-1.5 ${
                  currentIdx === 1
                    ? "bg-rose-500/10 ring-1 ring-rose-500/30"
                    : "bg-muted"
                }`}
              >
                <div className="text-xs text-muted-foreground">{outcomes[1]}</div>
                <div className="text-lg font-bold tabular-nums">
                  {(price1 * 100).toFixed(1)}¢
                </div>
              </div>
            </div>
            <Separator className="mb-3" />
          </>
        )}

        <Tabs value={side} onValueChange={(v) => setSide(v as OrderSide)}>
          <TabsList className="w-full">
            <TabsTrigger value="BUY" className="flex-1">
              买入
            </TabsTrigger>
            <TabsTrigger value="SELL" className="flex-1">
              卖出
            </TabsTrigger>
          </TabsList>

          <TabsContent value={side} className="mt-3">
            <div className="flex flex-col gap-3">
              <ToggleGroup
                type="single"
                value={orderType}
                onValueChange={(v) => v && setOrderType(v as OrderType)}
                className="w-full"
              >
                <ToggleGroupItem value="MARKET" className="flex-1 text-xs">
                  市价单
                </ToggleGroupItem>
                <ToggleGroupItem value="LIMIT" className="flex-1 text-xs">
                  限价单
                </ToggleGroupItem>
              </ToggleGroup>

              <div className="flex flex-col gap-1.5">
                <label className="text-xs text-muted-foreground">
                  份数（每份赢 = $1）
                </label>
                <Input
                  type="number"
                  placeholder="0"
                  min={0}
                  step={1}
                  value={amount}
                  onChange={(e) => {
                    setAmount(e.target.value)
                    setEstimate(null)
                  }}
                />
                {shares > 0 && midPrice > 0 && (
                  <span className="text-xs text-muted-foreground">
                    ≈ ${(shares * midPrice).toFixed(2)} 成本估算
                  </span>
                )}
              </div>

              {orderType === "LIMIT" && (
                <div className="flex flex-col gap-1.5">
                  <label className="text-xs text-muted-foreground">
                    限价 (0–1)
                  </label>
                  <Input
                    type="number"
                    placeholder="0.50"
                    min={0}
                    max={1}
                    step={0.01}
                    value={price}
                    onChange={(e) => {
                      setPrice(e.target.value)
                      setEstimate(null)
                    }}
                  />
                </div>
              )}

              <Button
                variant="outline"
                size="sm"
                disabled={!canEstimate || estimateMutation.isPending}
                onClick={() => estimateMutation.mutate()}
              >
                {estimateMutation.isPending && <Spinner data-icon="inline-start" />}
                估算
              </Button>

              {estimate && (
                <Alert>
                  <AlertDescription className="text-xs">
                    <div className="flex flex-col gap-1.5">
                      <div className="flex justify-between">
                        <span>每份成本</span>
                        <span className="font-mono">
                          {(estimate.probability_price * 100).toFixed(2)}¢
                        </span>
                      </div>
                      <div className="flex justify-between">
                        <span>总成本</span>
                        <span className="font-mono">
                          ${estimate.estimated_total_cost.toFixed(4)}
                        </span>
                      </div>
                      <Separator />
                      <div className="flex justify-between text-emerald-600">
                        <span>如果赢 (每份)</span>
                        <span className="font-mono">
                          +${estimate.potential_profit_per_share.toFixed(4)}
                        </span>
                      </div>
                      <div className="flex justify-between text-emerald-600">
                        <span>如果赢 (总计)</span>
                        <span className="font-mono">
                          +$
                          {(
                            estimate.potential_profit_per_share *
                            estimate.orderbook_depth_available
                          ).toFixed(4)}
                        </span>
                      </div>
                      <div className="flex justify-between text-rose-600">
                        <span>如果输 (每份)</span>
                        <span className="font-mono">
                          -${estimate.potential_loss_per_share.toFixed(4)}
                        </span>
                      </div>
                      <div className="flex justify-between text-rose-600">
                        <span>如果输 (总计)</span>
                        <span className="font-mono">
                          -${estimate.estimated_total_cost.toFixed(4)}
                        </span>
                      </div>
                      <Separator />
                      <div className="flex justify-between">
                        <span>滑点</span>
                        <span>{estimate.estimated_slippage_pct.toFixed(3)}%</span>
                      </div>
                      <div className="flex justify-between">
                        <span>可用深度</span>
                        <span>{estimate.orderbook_depth_available.toFixed(2)}</span>
                      </div>
                    </div>
                  </AlertDescription>
                </Alert>
              )}

              <Button
                className="w-full"
                disabled={!canOrder}
                onClick={() => orderMutation.mutate()}
              >
                {orderMutation.isPending && <Spinner data-icon="inline-start" />}
                {side === "BUY" ? "买入" : "卖出"} {currentOutcome}{" "}
                {orderType === "LIMIT" ? "(限价)" : "(市价)"}
              </Button>

              {orderMutation.isError && (
                <Alert variant="destructive">
                  <AlertDescription className="text-xs">
                    {(orderMutation.error as Error).message}
                  </AlertDescription>
                </Alert>
              )}

              {orderMutation.isSuccess && (
                <Alert>
                  <AlertDescription className="text-xs">
                    ✓ 订单已执行
                  </AlertDescription>
                </Alert>
              )}

              {/* Complementary result suggestion */}
              {compTokenId && compOutcome && onSwitchToken && (
                <>
                  <Separator />
                  <button
                    type="button"
                    className="text-left text-xs text-muted-foreground hover:text-foreground transition-colors"
                    onClick={() => onSwitchToken(compTokenId)}
                  >
                    或者: 买入 <span className="font-medium">{compOutcome}</span>{" "}
                    @ {(compPrice * 100).toFixed(1)}¢, 赢利{" "}
                    <span className="text-emerald-600">
                      +${(1 - compPrice).toFixed(2)}/份
                    </span>{" "}
                    →
                  </button>
                </>
              )}
            </div>
          </TabsContent>
        </Tabs>
      </CardContent>
    </Card>
  )
}
