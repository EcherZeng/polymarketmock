import { useState } from "react"
import { useMutation, useQueryClient } from "@tanstack/react-query"
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
import { Spinner } from "@/components/ui/spinner"
import { estimateOrder, placeOrder } from "@/api/client"
import type { EstimateResult, OrderSide, OrderType } from "@/types"

interface TradingPanelProps {
  tokenId: string
}

export default function TradingPanel({ tokenId }: TradingPanelProps) {
  const queryClient = useQueryClient()
  const [side, setSide] = useState<OrderSide>("BUY")
  const [orderType, setOrderType] = useState<OrderType>("MARKET")
  const [amount, setAmount] = useState("")
  const [price, setPrice] = useState("")
  const [estimate, setEstimate] = useState<EstimateResult | null>(null)

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
      setAmount("")
      setPrice("")
      setEstimate(null)
    },
  })

  const canEstimate = parseFloat(amount) > 0 && (orderType === "MARKET" || parseFloat(price) > 0)
  const canOrder = canEstimate && !orderMutation.isPending

  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-sm">Trade</CardTitle>
      </CardHeader>
      <CardContent>
        <Tabs value={side} onValueChange={(v) => setSide(v as OrderSide)}>
          <TabsList className="w-full">
            <TabsTrigger value="BUY" className="flex-1">
              Buy
            </TabsTrigger>
            <TabsTrigger value="SELL" className="flex-1">
              Sell
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
                  Market
                </ToggleGroupItem>
                <ToggleGroupItem value="LIMIT" className="flex-1 text-xs">
                  Limit
                </ToggleGroupItem>
              </ToggleGroup>

              <div className="flex flex-col gap-1.5">
                <label className="text-xs text-muted-foreground">Shares</label>
                <Input
                  type="number"
                  placeholder="0.00"
                  min={0}
                  step={1}
                  value={amount}
                  onChange={(e) => {
                    setAmount(e.target.value)
                    setEstimate(null)
                  }}
                />
              </div>

              {orderType === "LIMIT" && (
                <div className="flex flex-col gap-1.5">
                  <label className="text-xs text-muted-foreground">
                    Price (0–1)
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
                Estimate
              </Button>

              {estimate && (
                <Alert>
                  <AlertDescription className="text-xs">
                    <div className="flex flex-col gap-1">
                      <div className="flex justify-between">
                        <span>Avg Price</span>
                        <span>{(estimate.estimated_avg_price * 100).toFixed(2)}¢</span>
                      </div>
                      <div className="flex justify-between">
                        <span>Total Cost</span>
                        <span>${estimate.estimated_total_cost.toFixed(4)}</span>
                      </div>
                      <div className="flex justify-between">
                        <span>Slippage</span>
                        <span>{estimate.estimated_slippage_pct.toFixed(3)}%</span>
                      </div>
                      <div className="flex justify-between">
                        <span>Depth Available</span>
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
                {side === "BUY" ? "Buy" : "Sell"}{" "}
                {orderType === "LIMIT" ? "(Limit)" : "(Market)"}
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
                    Order placed successfully
                  </AlertDescription>
                </Alert>
              )}
            </div>
          </TabsContent>
        </Tabs>
      </CardContent>
    </Card>
  )
}
