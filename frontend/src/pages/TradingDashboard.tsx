import { useState } from "react"
import { useQuery } from "@tanstack/react-query"
import { Input } from "@/components/ui/input"
import { Button } from "@/components/ui/button"
import MarketInfo from "@/components/MarketInfo"
import OrderbookView from "@/components/OrderbookView"
import PriceChart from "@/components/PriceChart"
import TradingPanel from "@/components/TradingPanel"
import PositionTable from "@/components/PositionTable"
import TradeHistory from "@/components/TradeHistory"
import { fetchMarket } from "@/api/client"
import type { Market } from "@/types"

export default function TradingDashboard() {
  const [marketIdInput, setMarketIdInput] = useState("")
  const [activeMarketId, setActiveMarketId] = useState("")
  const [activeTokenId, setActiveTokenId] = useState("")

  const { data: market } = useQuery<Market>({
    queryKey: ["market", activeMarketId],
    queryFn: () => fetchMarket(activeMarketId),
    enabled: !!activeMarketId,
  })

  function handleLoadMarket() {
    const id = marketIdInput.trim()
    if (!id) return
    setActiveMarketId(id)
    // token ID will be set once market data loads
  }

  // When market loads, extract the first token ID
  const tokenIds = market?.clobTokenIds?.split(",").map((t) => t.trim()).filter(Boolean) ?? []
  if (tokenIds.length > 0 && !activeTokenId && market) {
    setActiveTokenId(tokenIds[0])
  }

  return (
    <div className="flex flex-col gap-4">
      {/* Market ID input */}
      <div className="flex items-center gap-2">
        <Input
          placeholder="Enter Market ID (conditionId) or paste from Polymarket..."
          value={marketIdInput}
          onChange={(e) => setMarketIdInput(e.target.value)}
          className="flex-1"
        />
        <Button onClick={handleLoadMarket}>Load Market</Button>
        {tokenIds.length > 1 && (
          <div className="flex gap-1">
            {tokenIds.map((tid, i) => (
              <Button
                key={tid}
                variant={activeTokenId === tid ? "default" : "outline"}
                size="sm"
                onClick={() => setActiveTokenId(tid)}
              >
                {market?.outcomes?.[i] ?? `Token ${i}`}
              </Button>
            ))}
          </div>
        )}
      </div>

      {!activeMarketId && (
        <div className="flex items-center justify-center rounded-lg border border-dashed p-12 text-muted-foreground">
          Enter a Polymarket market ID above to get started
        </div>
      )}

      {activeMarketId && activeTokenId && (
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-12">
          {/* Left column — Market info + Orderbook + Price chart */}
          <div className="flex flex-col gap-4 lg:col-span-4">
            <MarketInfo marketId={activeMarketId} />
            <OrderbookView tokenId={activeTokenId} />
            <PriceChart tokenId={activeTokenId} />
          </div>

          {/* Middle column — Trading panel */}
          <div className="flex flex-col gap-4 lg:col-span-4">
            <TradingPanel tokenId={activeTokenId} />
            <TradeHistory />
          </div>

          {/* Right column — Positions + Account */}
          <div className="flex flex-col gap-4 lg:col-span-4">
            <PositionTable />
          </div>
        </div>
      )}
    </div>
  )
}
