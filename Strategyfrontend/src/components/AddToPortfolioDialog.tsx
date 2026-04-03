import { useState } from "react"
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import { cn } from "@/lib/utils"
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from "@/components/ui/dialog"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { ScrollArea } from "@/components/ui/scroll-area"
import {
  fetchPortfolios,
  createPortfolio,
  addPortfolioItems,
} from "@/api/client"
import type { Portfolio, PortfolioItem } from "@/types"

interface AddToPortfolioDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  items: PortfolioItem[]
}

export default function AddToPortfolioDialog({
  open,
  onOpenChange,
  items,
}: AddToPortfolioDialogProps) {
  const queryClient = useQueryClient()
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [showCreate, setShowCreate] = useState(false)
  const [newName, setNewName] = useState("")

  const { data: portfolios = [] } = useQuery<Portfolio[]>({
    queryKey: ["portfolios"],
    queryFn: fetchPortfolios,
    enabled: open,
  })

  const addMutation = useMutation({
    mutationFn: (portfolioId: string) => addPortfolioItems(portfolioId, items),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["portfolios"] })
      handleClose()
    },
  })

  const createMutation = useMutation({
    mutationFn: (name: string) => createPortfolio({ name, items }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["portfolios"] })
      handleClose()
    },
  })

  function handleClose() {
    setSelectedId(null)
    setShowCreate(false)
    setNewName("")
    onOpenChange(false)
  }

  function handleConfirm() {
    if (showCreate && newName.trim()) {
      createMutation.mutate(newName.trim())
    } else if (selectedId) {
      addMutation.mutate(selectedId)
    }
  }

  const isPending = addMutation.isPending || createMutation.isPending
  const canConfirm = showCreate ? newName.trim().length > 0 : selectedId !== null

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>加入数据组合</DialogTitle>
          <DialogDescription>
            已选 {items.length} 条结果，选择目标组合或创建新组合
          </DialogDescription>
        </DialogHeader>

        {!showCreate && (
          <>
            {portfolios.length > 0 ? (
              <ScrollArea className="max-h-64">
                <div className="flex flex-col gap-1 pr-3">
                  {portfolios.map((p) => (
                    <button
                      key={p.portfolio_id}
                      onClick={() => setSelectedId(p.portfolio_id)}
                      className={cn(
                        "flex items-center justify-between rounded-md border px-3 py-2 text-left text-sm transition-colors",
                        selectedId === p.portfolio_id
                          ? "border-primary bg-primary/5 text-foreground"
                          : "border-transparent hover:bg-muted",
                      )}
                    >
                      <div>
                        <div className="font-medium">{p.name}</div>
                        <div className="text-xs text-muted-foreground">
                          {p.items.length} 条数据源
                        </div>
                      </div>
                      <div className="text-xs text-muted-foreground">
                        {p.created_at.replace("T", " ").slice(0, 10)}
                      </div>
                    </button>
                  ))}
                </div>
              </ScrollArea>
            ) : (
              <div className="py-6 text-center text-sm text-muted-foreground">
                暂无组合，请创建新组合
              </div>
            )}
          </>
        )}

        {showCreate && (
          <div className="flex flex-col gap-2">
            <label className="text-sm font-medium">组合名称</label>
            <Input
              value={newName}
              onChange={(e) => setNewName(e.target.value)}
              placeholder="输入组合名称..."
              autoFocus
              maxLength={100}
            />
          </div>
        )}

        <div className="flex items-center justify-between gap-2 pt-2">
          <Button
            variant="outline"
            size="sm"
            onClick={() => {
              if (showCreate) {
                setShowCreate(false)
                setNewName("")
              } else {
                setShowCreate(true)
                setSelectedId(null)
              }
            }}
          >
            {showCreate ? "选择已有组合" : "创建新组合"}
          </Button>

          <div className="flex gap-2">
            <Button variant="outline" size="sm" onClick={handleClose}>
              取消
            </Button>
            <Button
              size="sm"
              disabled={!canConfirm || isPending}
              onClick={handleConfirm}
            >
              {isPending ? "添加中..." : "确认"}
            </Button>
          </div>
        </div>

        {(addMutation.isError || createMutation.isError) && (
          <div className="text-xs text-red-500">
            操作失败，请重试
          </div>
        )}
      </DialogContent>
    </Dialog>
  )
}
