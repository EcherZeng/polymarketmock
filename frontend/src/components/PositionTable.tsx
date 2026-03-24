import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { Separator } from "@/components/ui/separator"
import { Skeleton } from "@/components/ui/skeleton"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { fetchAccount, initAccount } from "@/api/client"
import { useState } from "react"
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"

export default function PositionTable() {
  const queryClient = useQueryClient()
  const [initBalance, setInitBalance] = useState("10000")
  const [dialogOpen, setDialogOpen] = useState(false)

  const { data: account, isLoading } = useQuery({
    queryKey: ["account"],
    queryFn: fetchAccount,
    refetchInterval: 10_000,
  })

  const initMutation = useMutation({
    mutationFn: () => initAccount(parseFloat(initBalance)),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["account"] })
      setDialogOpen(false)
    },
  })

  if (isLoading) {
    return (
      <Card>
        <CardHeader>
          <Skeleton className="h-5 w-1/3" />
        </CardHeader>
        <CardContent>
          <Skeleton className="h-32 w-full" />
        </CardContent>
      </Card>
    )
  }

  return (
    <Card>
      <CardHeader className="pb-2">
        <div className="flex items-center justify-between">
          <CardTitle className="text-sm">Account & Positions</CardTitle>
          <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
            <DialogTrigger asChild>
              <Button variant="outline" size="sm">
                Init Account
              </Button>
            </DialogTrigger>
            <DialogContent>
              <DialogHeader>
                <DialogTitle>Initialize Account</DialogTitle>
              </DialogHeader>
              <div className="flex flex-col gap-3">
                <div className="flex flex-col gap-1.5">
                  <label className="text-sm text-muted-foreground">
                    Initial USDC Balance
                  </label>
                  <Input
                    type="number"
                    value={initBalance}
                    onChange={(e) => setInitBalance(e.target.value)}
                    min={1}
                  />
                </div>
                <Button
                  onClick={() => initMutation.mutate()}
                  disabled={initMutation.isPending || parseFloat(initBalance) <= 0}
                >
                  {initMutation.isPending ? "Initializing..." : "Set Balance"}
                </Button>
              </div>
            </DialogContent>
          </Dialog>
        </div>
      </CardHeader>
      <CardContent>
        {account && (
          <>
            <div className="grid grid-cols-2 gap-2 text-xs">
              <div>
                <div className="text-muted-foreground">Balance</div>
                <div className="text-lg font-bold">
                  ${account.balance.toFixed(2)}
                </div>
              </div>
              <div>
                <div className="text-muted-foreground">Initial</div>
                <div className="text-lg font-bold">
                  ${account.initial_balance.toFixed(2)}
                </div>
              </div>
              <div>
                <div className="text-muted-foreground">Positions Value</div>
                <div className="font-medium">
                  ${account.total_positions_value.toFixed(2)}
                </div>
              </div>
              <div>
                <div className="text-muted-foreground">Total PnL</div>
                <div className={
                  account.total_pnl >= 0
                    ? "font-medium text-chart-2"
                    : "font-medium text-chart-1"
                }>
                  {account.total_pnl >= 0 ? "+" : ""}
                  ${account.total_pnl.toFixed(2)}
                </div>
              </div>
            </div>

            <Separator className="my-3" />

            {account.positions.length === 0 ? (
              <p className="text-center text-xs text-muted-foreground py-4">
                No open positions
              </p>
            ) : (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead className="text-xs">Token</TableHead>
                    <TableHead className="text-xs text-right">Shares</TableHead>
                    <TableHead className="text-xs text-right">Avg Cost</TableHead>
                    <TableHead className="text-xs text-right">Price</TableHead>
                    <TableHead className="text-xs text-right">PnL</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {account.positions.map((pos) => (
                    <TableRow key={pos.token_id}>
                      <TableCell className="text-xs font-mono max-w-24 truncate">
                        {pos.token_id.slice(0, 8)}…
                      </TableCell>
                      <TableCell className="text-xs text-right">
                        {pos.shares.toFixed(2)}
                      </TableCell>
                      <TableCell className="text-xs text-right">
                        {(pos.avg_cost * 100).toFixed(1)}¢
                      </TableCell>
                      <TableCell className="text-xs text-right">
                        {(pos.current_price * 100).toFixed(1)}¢
                      </TableCell>
                      <TableCell className="text-xs text-right">
                        <Badge
                          variant={pos.unrealized_pnl >= 0 ? "default" : "destructive"}
                        >
                          {pos.unrealized_pnl >= 0 ? "+" : ""}
                          ${pos.unrealized_pnl.toFixed(2)}
                        </Badge>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            )}
          </>
        )}
      </CardContent>
    </Card>
  )
}
