import { useState, useMemo } from "react"
import { Link } from "react-router-dom"
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Skeleton } from "@/components/ui/skeleton"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import {
  Card,
  CardContent,
} from "@/components/ui/card"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from "@/components/ui/alert-dialog"
import { Trash2 } from "lucide-react"
import { cn } from "@/lib/utils"
import { fetchArchives, deleteArchive } from "@/api/client"
import type { ArchivedEvent } from "@/types"

type SortField = "time" | "type" | "data"
type SortDir = "asc" | "desc"
type SessionType = "all" | "5m" | "15m"

function parseSessionType(slug: string): "5m" | "15m" | "other" {
  if (slug.includes("-5m-")) return "5m"
  if (slug.includes("-15m-")) return "15m"
  return "other"
}

function fmtDateTime(iso: string): string {
  if (!iso) return "—"
  try {
    return new Date(iso).toLocaleString("zh-CN", {
      month: "2-digit",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
      hour12: false,
    })
  } catch {
    return iso
  }
}

function fmtDuration(start: string, end: string): string {
  if (!start || !end) return "—"
  try {
    const ms = new Date(end).getTime() - new Date(start).getTime()
    const mins = Math.round(ms / 60000)
    if (mins < 60) return `${mins}分钟`
    return `${Math.floor(mins / 60)}小时${mins % 60}分钟`
  } catch {
    return "—"
  }
}

function hasAnyData(a: ArchivedEvent): boolean {
  return (a.prices_count ?? 0) + (a.orderbooks_count ?? 0) + (a.live_trades_count ?? 0) > 0
}

function dataTotal(a: ArchivedEvent): number {
  return (a.prices_count ?? 0) + (a.orderbooks_count ?? 0) + (a.live_trades_count ?? 0)
}

export default function SessionHistoryPage() {
  const queryClient = useQueryClient()
  const [search, setSearch] = useState("")
  const [typeFilter, setTypeFilter] = useState<SessionType>("all")
  const [sortField, setSortField] = useState<SortField>("time")
  const [sortDir, setSortDir] = useState<SortDir>("desc")

  const { data: archives, isLoading } = useQuery<ArchivedEvent[]>({
    queryKey: ["archives"],
    queryFn: fetchArchives,
  })

  const filtered = useMemo(() => {
    if (!archives) return []

    // Filter out archives with no data at all
    let list = archives.filter(hasAnyData)

    // Search filter
    if (search.trim()) {
      const q = search.trim().toLowerCase()
      list = list.filter(
        (a) =>
          a.slug.toLowerCase().includes(q) ||
          a.title.toLowerCase().includes(q) ||
          a.market_id.toLowerCase().includes(q),
      )
    }

    // Type filter
    if (typeFilter !== "all") {
      list = list.filter((a) => parseSessionType(a.slug) === typeFilter)
    }

    // Sort
    list.sort((a, b) => {
      let cmp = 0
      switch (sortField) {
        case "time":
          cmp =
            new Date(a.archived_at || a.end_time).getTime() -
            new Date(b.archived_at || b.end_time).getTime()
          break
        case "type": {
          const ta = parseSessionType(a.slug)
          const tb = parseSessionType(b.slug)
          cmp = ta.localeCompare(tb)
          break
        }
        case "data":
          cmp = dataTotal(a) - dataTotal(b)
          break
      }
      return sortDir === "desc" ? -cmp : cmp
    })

    return list
  }, [archives, search, typeFilter, sortField, sortDir])

  const deleteMutation = useMutation({
    mutationFn: (slug: string) => deleteArchive(slug),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["archives"] }),
  })

  const toggleSort = (field: SortField) => {
    if (sortField === field) {
      setSortDir((d) => (d === "asc" ? "desc" : "asc"))
    } else {
      setSortField(field)
      setSortDir("desc")
    }
  }

  const sortIcon = (field: SortField) => {
    if (sortField !== field) return "↕"
    return sortDir === "desc" ? "↓" : "↑"
  }

  if (isLoading) {
    return (
      <div className="flex flex-col gap-4">
        <Skeleton className="h-8 w-48" />
        <Skeleton className="h-10 w-full" />
        <Skeleton className="h-64 w-full rounded-lg" />
      </div>
    )
  }

  return (
    <div className="flex flex-col gap-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h1 className="text-lg font-semibold">场次历史</h1>
        <Badge variant="secondary" className="font-mono">
          共 {filtered.length} 个场次{archives && filtered.length < archives.length ? ` (已过滤 ${archives.length - filtered.length} 个无数据)` : ""}
        </Badge>
      </div>

      {/* Filters bar */}
      <Card>
        <CardContent className="flex flex-wrap items-center gap-3 p-3">
          <Input
            placeholder="搜索场次名称或 ID..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="h-8 w-64"
          />

          <Select
            value={typeFilter}
            onValueChange={(v) => setTypeFilter(v as SessionType)}
          >
            <SelectTrigger size="sm">
              <SelectValue placeholder="场次类型" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">全部类型</SelectItem>
              <SelectItem value="5m">5 分钟</SelectItem>
              <SelectItem value="15m">15 分钟</SelectItem>
            </SelectContent>
          </Select>

          <Select
            value={`${sortField}-${sortDir}`}
            onValueChange={(v) => {
              const [f, d] = v.split("-") as [SortField, SortDir]
              setSortField(f)
              setSortDir(d)
            }}
          >
            <SelectTrigger size="sm">
              <SelectValue placeholder="排序" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="time-desc">时间 (最新优先)</SelectItem>
              <SelectItem value="time-asc">时间 (最早优先)</SelectItem>
              <SelectItem value="type-asc">类型 (5m → 15m)</SelectItem>
              <SelectItem value="type-desc">类型 (15m → 5m)</SelectItem>
              <SelectItem value="data-desc">数据量 (多 → 少)</SelectItem>
              <SelectItem value="data-asc">数据量 (少 → 多)</SelectItem>
            </SelectContent>
          </Select>

          {(search || typeFilter !== "all") && (
            <Button
              variant="ghost"
              size="sm"
              onClick={() => {
                setSearch("")
                setTypeFilter("all")
              }}
            >
              清除筛选
            </Button>
          )}
        </CardContent>
      </Card>

      {/* Results */}
      {filtered.length === 0 ? (
        <div className="flex flex-col items-center gap-2 py-12 text-sm text-muted-foreground">
          <p>没有匹配的场次</p>
          {search && (
            <Button variant="ghost" size="sm" onClick={() => setSearch("")}>
              清除搜索
            </Button>
          )}
        </div>
      ) : (
        <Card>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead
                  className="cursor-pointer select-none"
                  onClick={() => toggleSort("time")}
                >
                  时间 {sortIcon("time")}
                </TableHead>
                <TableHead>名称</TableHead>
                <TableHead
                  className="cursor-pointer select-none text-center"
                  onClick={() => toggleSort("type")}
                >
                  类型 {sortIcon("type")}
                </TableHead>
                <TableHead
                  className="cursor-pointer select-none text-right"
                  onClick={() => toggleSort("data")}
                >
                  数据量 {sortIcon("data")}
                </TableHead>
                <TableHead className="text-center">场次时长</TableHead>
                <TableHead className="text-center">数据时长</TableHead>
                <TableHead className="text-right">操作</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {filtered.map((archive) => {
                const sessionType = parseSessionType(archive.slug)
                return (
                  <TableRow key={archive.slug}>
                    <TableCell className="font-mono text-xs whitespace-nowrap">
                      {fmtDateTime(archive.start_time || archive.archived_at)}
                    </TableCell>
                    <TableCell>
                      <div className="flex flex-col gap-0.5">
                        <span className="text-sm font-medium line-clamp-1">
                          {archive.title}
                        </span>
                        <span className="text-xs text-muted-foreground font-mono">
                          {archive.slug}
                        </span>
                      </div>
                    </TableCell>
                    <TableCell className="text-center">
                      <Badge
                        variant="outline"
                        className={cn(
                          "text-xs",
                          sessionType === "5m"
                            ? "border-blue-300 bg-blue-50 text-blue-700"
                            : sessionType === "15m"
                              ? "border-amber-300 bg-amber-50 text-amber-700"
                              : "",
                        )}
                      >
                        {sessionType === "5m"
                          ? "5 分钟"
                          : sessionType === "15m"
                            ? "15 分钟"
                            : "其他"}
                      </Badge>
                    </TableCell>
                    <TableCell className="text-right">
                      <div className="flex flex-col gap-0.5 text-xs text-muted-foreground tabular-nums">
                        <span>{archive.prices_count} 价格</span>
                        <span>{archive.orderbooks_count} 盘口</span>
                        <span>{archive.live_trades_count ?? 0} 成交</span>
                      </div>
                    </TableCell>
                    <TableCell className="text-center text-xs text-muted-foreground font-mono">
                      {fmtDuration(archive.start_time, archive.end_time)}
                    </TableCell>
                    <TableCell className="text-center text-xs text-muted-foreground font-mono">
                      {fmtDuration(archive.data_start, archive.data_end)}
                    </TableCell>
                    <TableCell className="text-right">
                      <div className="flex items-center justify-end gap-1">
                        <Button variant="outline" size="sm" asChild>
                          <Link to={`/replay/${archive.slug}`}>回放</Link>
                        </Button>
                        <AlertDialog>
                          <AlertDialogTrigger asChild>
                            <Button variant="ghost" size="sm" className="text-destructive hover:text-destructive hover:bg-destructive/10 px-2">
                              <Trash2 />
                            </Button>
                          </AlertDialogTrigger>
                          <AlertDialogContent>
                            <AlertDialogHeader>
                              <AlertDialogTitle>确认删除场次</AlertDialogTitle>
                              <AlertDialogDescription>
                                将永久删除 <span className="font-mono font-medium">{archive.slug}</span> 的所有归档数据（Parquet + 元数据），此操作不可撤销。
                              </AlertDialogDescription>
                            </AlertDialogHeader>
                            <AlertDialogFooter>
                              <AlertDialogCancel>取消</AlertDialogCancel>
                              <AlertDialogAction
                                className="bg-destructive text-white hover:bg-destructive/90"
                                onClick={() => deleteMutation.mutate(archive.slug)}
                              >
                                删除
                              </AlertDialogAction>
                            </AlertDialogFooter>
                          </AlertDialogContent>
                        </AlertDialog>
                      </div>
                    </TableCell>
                  </TableRow>
                )
              })}
            </TableBody>
          </Table>
        </Card>
      )}
    </div>
  )
}
