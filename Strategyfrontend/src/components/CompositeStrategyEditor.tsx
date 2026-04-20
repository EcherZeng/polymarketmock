import { useState, useMemo } from "react"
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import { PlusIcon, Trash2Icon, SaveIcon, PencilIcon, XIcon } from "lucide-react"
import { cn } from "@/lib/utils"
import {
  fetchStrategies,
  fetchCompositePresets,
  saveCompositePreset,
  deleteCompositePreset,
  renameCompositePreset,
} from "@/api/client"
import type { StrategyInfo, CompositeBranch, CompositePreset } from "@/types"

interface CompositeStrategyEditorProps {
  /** Currently selected composite preset name (for batch run) */
  selectedComposite: string
  onSelectComposite: (name: string) => void
}

interface EditingBranch {
  label: string
  min_momentum: string
  preset_name: string
}

export default function CompositeStrategyEditor({
  selectedComposite,
  onSelectComposite,
}: CompositeStrategyEditorProps) {
  const queryClient = useQueryClient()

  // ── Data ────────────────────────────────────────────────────────────
  const { data: composites = [] } = useQuery({
    queryKey: ["composite-presets"],
    queryFn: fetchCompositePresets,
  })

  const { data: strategies = [] } = useQuery<StrategyInfo[]>({
    queryKey: ["strategies"],
    queryFn: fetchStrategies,
  })

  // ── Editing state ─────────────────────────────────────────────────
  const [editing, setEditing] = useState(false)
  const [editName, setEditName] = useState("")
  const [editDesc, setEditDesc] = useState("")
  const [editW1, setEditW1] = useState(5)
  const [editW2, setEditW2] = useState(10)
  const [editBranches, setEditBranches] = useState<EditingBranch[]>([])
  const [isNew, setIsNew] = useState(false)
  const [renameTarget, setRenameTarget] = useState<string | null>(null)
  const [renameValue, setRenameValue] = useState("")

  // Sort branches by min_momentum descending for display
  const sortedBranches = useMemo(
    () =>
      [...editBranches].sort(
        (a, b) => parseFloat(b.min_momentum || "0") - parseFloat(a.min_momentum || "0"),
      ),
    [editBranches],
  )

  // ── Mutations ─────────────────────────────────────────────────────
  const saveMutation = useMutation({
    mutationFn: () =>
      saveCompositePreset(editName, {
        description: editDesc,
        btc_windows: { btc_trend_window_1: editW1, btc_trend_window_2: editW2 },
        branches: editBranches.map((b) => ({
          label: b.label,
          min_momentum: parseFloat(b.min_momentum) || 0,
          preset_name: b.preset_name,
        })),
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["composite-presets"] })
      setEditing(false)
      onSelectComposite(editName)
    },
  })

  const deleteMutation = useMutation({
    mutationFn: deleteCompositePreset,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["composite-presets"] })
      if (selectedComposite === editName) onSelectComposite("")
    },
  })

  const renameMutation = useMutation({
    mutationFn: ({ old, new: n }: { old: string; new: string }) =>
      renameCompositePreset(old, n),
    onSuccess: (_, { new: n }) => {
      queryClient.invalidateQueries({ queryKey: ["composite-presets"] })
      if (selectedComposite === renameTarget) onSelectComposite(n)
      setRenameTarget(null)
    },
  })

  // ── Helpers ────────────────────────────────────────────────────────

  /** Look up btc_min_momentum from a strategy's default_config */
  function getStrategyThreshold(presetName: string): string {
    const s = strategies.find((st) => st.name === presetName)
    const val = s?.default_config?.btc_min_momentum
    if (val == null) return "0"
    return String(val)
  }

  // ── Handlers ──────────────────────────────────────────────────────

  function startNew() {
    const firstPreset = strategies[0]?.name ?? ""
    setEditName("")
    setEditDesc("")
    setEditW1(5)
    setEditW2(10)
    setEditBranches([{ label: "分支1", min_momentum: getStrategyThreshold(firstPreset), preset_name: firstPreset }])
    setIsNew(true)
    setEditing(true)
  }

  function startEdit(name: string, data: CompositePreset) {
    setEditName(name)
    setEditDesc(data.description || "")
    setEditW1(data.btc_windows?.btc_trend_window_1 ?? 5)
    setEditW2(data.btc_windows?.btc_trend_window_2 ?? 10)
    setEditBranches(
      data.branches.map((b) => ({
        label: b.label,
        min_momentum: String(b.min_momentum),
        preset_name: b.preset_name,
      })),
    )
    setIsNew(false)
    setEditing(true)
  }

  function addBranch() {
    const firstPreset = strategies[0]?.name ?? ""
    setEditBranches((prev) => [
      ...prev,
      {
        label: `分支${prev.length + 1}`,
        min_momentum: getStrategyThreshold(firstPreset),
        preset_name: firstPreset,
      },
    ])
  }

  function removeBranch(idx: number) {
    setEditBranches((prev) => prev.filter((_, i) => i !== idx))
  }

  function updateBranch(idx: number, field: keyof EditingBranch, value: string) {
    setEditBranches((prev) => prev.map((b, i) => {
      if (i !== idx) return b
      const updated = { ...b, [field]: value }
      // Auto-fill threshold when changing strategy preset
      if (field === "preset_name") {
        updated.min_momentum = getStrategyThreshold(value)
      }
      return updated
    }))
  }

  // ── Render ────────────────────────────────────────────────────────

  if (editing) {
    return (
      <div className="flex flex-col gap-4">
        <div className="flex items-center justify-between">
          <h3 className="text-sm font-medium">{isNew ? "创建复合策略" : `编辑: ${editName}`}</h3>
          <button
            onClick={() => setEditing(false)}
            className="text-muted-foreground hover:text-foreground"
          >
            <XIcon className="size-4" />
          </button>
        </div>

        {/* Name + Description */}
        <div className="flex flex-col gap-2">
          {isNew && (
            <input
              value={editName}
              onChange={(e) => setEditName(e.target.value)}
              placeholder="复合策略名称"
              className="h-9 rounded-md border bg-background px-3 text-sm"
            />
          )}
          <input
            value={editDesc}
            onChange={(e) => setEditDesc(e.target.value)}
            placeholder="描述 (可选)"
            className="h-9 rounded-md border bg-background px-3 text-sm"
          />
        </div>

        {/* BTC Windows */}
        <div className="flex items-center gap-3">
          <span className="text-xs text-muted-foreground whitespace-nowrap">BTC 窗口</span>
          <label className="flex items-center gap-1 text-xs">
            <span>W1</span>
            <input
              type="number"
              min={1}
              max={10}
              value={editW1}
              onChange={(e) => setEditW1(Number(e.target.value))}
              className="h-7 w-14 rounded border bg-background px-2 text-xs"
            />
            <span>min</span>
          </label>
          <label className="flex items-center gap-1 text-xs">
            <span>W2</span>
            <input
              type="number"
              min={1}
              max={30}
              value={editW2}
              onChange={(e) => setEditW2(Number(e.target.value))}
              className="h-7 w-14 rounded border bg-background px-2 text-xs"
            />
            <span>min</span>
          </label>
        </div>

        {/* Branches */}
        <div className="flex flex-col gap-2">
          <div className="flex items-center justify-between">
            <span className="text-xs font-medium text-muted-foreground">
              分支条件（按阈值从高到低匹配）
            </span>
            <button
              onClick={addBranch}
              className="flex items-center gap-1 text-xs text-primary hover:underline"
            >
              <PlusIcon className="size-3" /> 添加分支
            </button>
          </div>

          {sortedBranches.map((branch, displayIdx) => {
            // Find original index for editing
            const origIdx = editBranches.indexOf(branch)
            return (
              <div
                key={origIdx}
                className="flex items-center gap-2 rounded-md border p-2"
              >
                <input
                  value={branch.label}
                  onChange={(e) => updateBranch(origIdx, "label", e.target.value)}
                  placeholder="标签"
                  className="h-7 w-20 rounded border bg-background px-2 text-xs"
                />
                <span className="text-xs text-muted-foreground">≥</span>
                <input
                  type="number"
                  step="0.0001"
                  min={0}
                  value={branch.min_momentum}
                  onChange={(e) => updateBranch(origIdx, "min_momentum", e.target.value)}
                  className="h-7 w-24 rounded border bg-background px-2 text-xs"
                />
                <select
                  value={branch.preset_name}
                  onChange={(e) => updateBranch(origIdx, "preset_name", e.target.value)}
                  className="h-7 flex-1 rounded border bg-background px-2 text-xs"
                >
                  {strategies.map((s) => (
                    <option key={s.name} value={s.name}>
                      {s.name}
                    </option>
                  ))}
                </select>
                <button
                  onClick={() => removeBranch(origIdx)}
                  disabled={editBranches.length <= 1}
                  className="text-muted-foreground hover:text-destructive disabled:opacity-30"
                >
                  <Trash2Icon className="size-3.5" />
                </button>
              </div>
            )
          })}
        </div>

        {/* Save */}
        <div className="flex gap-2">
          <button
            onClick={() => saveMutation.mutate()}
            disabled={!editName.trim() || editBranches.length === 0 || saveMutation.isPending}
            className={cn(
              "flex items-center gap-1 h-9 flex-1 rounded-md text-sm font-medium transition-colors",
              "bg-primary text-primary-foreground hover:bg-primary/90",
              "disabled:pointer-events-none disabled:opacity-50",
            )}
          >
            <SaveIcon className="size-3.5" />
            {saveMutation.isPending ? "保存中..." : "保存"}
          </button>
          <button
            onClick={() => setEditing(false)}
            className="h-9 rounded-md border px-4 text-sm text-muted-foreground hover:text-foreground"
          >
            取消
          </button>
        </div>

        {saveMutation.isError && (
          <p className="text-sm text-destructive">
            保存失败: {(saveMutation.error as Error).message}
          </p>
        )}
      </div>
    )
  }

  // ── List view ─────────────────────────────────────────────────────
  return (
    <div className="flex flex-col gap-3">
      {composites.length === 0 && (
        <p className="text-sm text-muted-foreground">暂无复合策略，点击下方按钮创建</p>
      )}

      {composites.map((c) => {
        const name = c.name
        const isSelected = selectedComposite === name
        const isRenaming = renameTarget === name

        return (
          <div
            key={name}
            onClick={() => onSelectComposite(isSelected ? "" : name)}
            className={cn(
              "rounded-lg border p-3 cursor-pointer transition-colors",
              isSelected ? "border-primary bg-primary/5" : "border-border hover:border-primary/50",
            )}
          >
            <div className="flex items-center justify-between">
              {isRenaming ? (
                <div className="flex items-center gap-1" onClick={(e) => e.stopPropagation()}>
                  <input
                    value={renameValue}
                    onChange={(e) => setRenameValue(e.target.value)}
                    className="h-6 w-32 rounded border bg-background px-2 text-xs"
                    autoFocus
                    onKeyDown={(e) => {
                      if (e.key === "Enter" && renameValue.trim()) {
                        renameMutation.mutate({ old: name, new: renameValue.trim() })
                      }
                      if (e.key === "Escape") setRenameTarget(null)
                    }}
                  />
                  <button
                    onClick={(e) => {
                      e.stopPropagation()
                      if (renameValue.trim()) renameMutation.mutate({ old: name, new: renameValue.trim() })
                    }}
                    className="text-xs text-primary hover:underline"
                  >
                    确认
                  </button>
                </div>
              ) : (
                <span className="font-medium text-sm">{name}</span>
              )}
              <div className="flex items-center gap-1" onClick={(e) => e.stopPropagation()}>
                <button
                  onClick={() => { setRenameTarget(name); setRenameValue(name) }}
                  className="text-muted-foreground hover:text-foreground"
                  title="重命名"
                >
                  <PencilIcon className="size-3" />
                </button>
                <button
                  onClick={() => startEdit(name, c)}
                  className="text-muted-foreground hover:text-foreground"
                  title="编辑"
                >
                  <PencilIcon className="size-3" />
                </button>
                <button
                  onClick={() => {
                    if (confirm(`确定删除复合策略 "${name}"？`)) deleteMutation.mutate(name)
                  }}
                  className="text-muted-foreground hover:text-destructive"
                  title="删除"
                >
                  <Trash2Icon className="size-3" />
                </button>
              </div>
            </div>
            {c.description && (
              <p className="mt-1 text-xs text-muted-foreground">{c.description}</p>
            )}
            <div className="mt-2 flex flex-col gap-1">
              {c.branches.map((b, i) => (
                <div key={i} className="flex items-center gap-2 text-xs">
                  <span className="rounded bg-muted px-1.5 py-0.5 font-mono">
                    ≥{b.min_momentum}
                  </span>
                  <span className="text-muted-foreground">→</span>
                  <span className="font-medium">{b.preset_name}</span>
                  <span className="text-muted-foreground">({b.label})</span>
                </div>
              ))}
            </div>
          </div>
        )
      })}

      <button
        onClick={startNew}
        className="rounded-lg border border-dashed border-muted-foreground/30 p-3 text-center text-sm text-muted-foreground hover:border-primary/50 hover:text-foreground transition-colors"
      >
        <PlusIcon className="inline size-4 mr-1" /> 创建复合策略
      </button>
    </div>
  )
}
