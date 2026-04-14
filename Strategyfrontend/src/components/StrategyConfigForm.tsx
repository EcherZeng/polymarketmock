import { useMemo, useState, useRef, useCallback, useEffect } from "react"
import { InfoIcon, XIcon, PlusIcon, ChevronRightIcon } from "lucide-react"
import type { ParamSchemaItem, ParamGroupDef } from "@/types"
import { cn } from "@/lib/utils"
import { Badge } from "@/components/ui/badge"
import { ScrollArea } from "@/components/ui/scroll-area"
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip"

// ── helpers ─────────────────────────────────────────────────────────────────

const WEIGHT_CONFIG: Record<string, { icon: string; color: string; tip: string }> = {
  critical: { icon: "🔴", color: "text-red-500", tip: "本金安全 — 调整须极度谨慎" },
  high:     { icon: "🟠", color: "text-orange-500", tip: "显著影响收益 — 谨慎调整" },
  medium:   { icon: "🟡", color: "text-yellow-500", tip: "影响入场频率/质量" },
  low:      { icon: "🟢", color: "text-green-500", tip: "微调类参数" },
}

function WeightBadge({ weight }: { weight?: string }) {
  if (!weight) return null
  const cfg = WEIGHT_CONFIG[weight]
  if (!cfg) return null
  return (
    <TooltipProvider delayDuration={200}>
      <Tooltip>
        <TooltipTrigger asChild>
          <span className={cn("cursor-default text-xs leading-none", cfg.color)} aria-label={`权重: ${weight}`}>
            {cfg.icon}
          </span>
        </TooltipTrigger>
        <TooltipContent side="top" className="text-xs">
          <span className="font-medium">{weight}</span> — {cfg.tip}
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>
  )
}

function t(label: { zh: string; en: string } | string): string {
  if (typeof label === "string") return label
  return label.zh || label.en
}

// ── ParamInfoPopup ─────────────────────────────────────────────────────────

function ParamInfoPopup({ schema }: { schema: ParamSchemaItem }) {
  const [open, setOpen] = useState(false)
  const [pos, setPos] = useState({ x: 0, y: 0 })
  const dragging = useRef(false)
  const dragStart = useRef({ mx: 0, my: 0, px: 0, py: 0 })

  const onDragMouseDown = useCallback((e: React.MouseEvent) => {
    e.stopPropagation()
    dragging.current = true
    dragStart.current = { mx: e.clientX, my: e.clientY, px: pos.x, py: pos.y }

    function onMouseMove(ev: MouseEvent) {
      if (!dragging.current) return
      setPos({
        x: dragStart.current.px + (ev.clientX - dragStart.current.mx),
        y: dragStart.current.py + (ev.clientY - dragStart.current.my),
      })
    }
    function onMouseUp() {
      dragging.current = false
      document.removeEventListener("mousemove", onMouseMove)
      document.removeEventListener("mouseup", onMouseUp)
    }
    document.addEventListener("mousemove", onMouseMove)
    document.addEventListener("mouseup", onMouseUp)
  }, [pos])

  return (
    <div className="relative inline-flex">
      <button
        type="button"
        onClick={() => { setPos({ x: 0, y: 0 }); setOpen(true) }}
        className="flex items-center text-muted-foreground/50 hover:text-muted-foreground"
        aria-label="参数说明"
      >
        <InfoIcon className="size-3 shrink-0" />
      </button>

      {open && (
        <div
          className="fixed z-50 w-80 rounded-md border bg-popover text-popover-foreground shadow-lg"
          onClick={(e) => e.stopPropagation()}
          onMouseDown={(e) => e.stopPropagation()}
          style={{
            resize: "both",
            overflow: "auto",
            minWidth: "18rem",
            minHeight: "6rem",
            maxHeight: "24rem",
            top: "50%",
            left: "50%",
            transform: `translate(calc(-50% + ${pos.x}px), calc(-50% + ${pos.y}px))`,
          }}
        >
          <div
            onMouseDown={onDragMouseDown}
            onClick={(e) => e.stopPropagation()}
            className="flex cursor-grab items-center justify-between border-b px-3 py-1.5 active:cursor-grabbing"
          >
            <span className="text-xs font-medium text-muted-foreground select-none">参数说明</span>
            <button
              type="button"
              onClick={(e) => { e.stopPropagation(); setOpen(false) }}
              className="rounded p-0.5 text-muted-foreground hover:text-foreground"
              aria-label="关闭"
            >
              <XIcon className="size-3" />
            </button>
          </div>

          <div className="space-y-1.5 p-3">
            {schema.desc && (
              <p className="text-xs">{t(schema.desc)}</p>
            )}
            {schema.min !== undefined && schema.max !== undefined && (
              <p className="text-xs text-muted-foreground">
                范围：{schema.min} ~ {schema.max}
              </p>
            )}
            {schema.disable_value !== undefined && schema.disable_value !== null ? (
              <p className="text-xs text-muted-foreground">
                禁用值：<span className="font-mono text-foreground">{schema.disable_value}</span>
                {schema.disable_note && <span>（{t(schema.disable_note)}）</span>}
              </p>
            ) : schema.disable_note ? (
              <p className="text-xs text-muted-foreground">
                禁用：{t(schema.disable_note)}
              </p>
            ) : null}
          </div>
        </div>
      )}
    </div>
  )
}

// ── Dependency helpers (DAG: depends_on supports string | string[]) ─────────

/** Normalise depends_on to an array. */
function normaliseDeps(deps: string | string[] | undefined): string[] {
  if (!deps) return []
  return Array.isArray(deps) ? deps : [deps]
}

interface DepGraph {
  parentToChildren: Map<string, string[]>
  childToParents: Map<string, string[]>
}

function buildDepGraph(schema: Record<string, ParamSchemaItem>): DepGraph {
  const parentToChildren = new Map<string, string[]>()
  const childToParents = new Map<string, string[]>()
  for (const [key, s] of Object.entries(schema)) {
    const parents = normaliseDeps(s.depends_on).filter(p => p in schema)
    if (parents.length === 0) continue
    childToParents.set(key, parents)
    for (const parent of parents) {
      if (!parentToChildren.has(parent)) parentToChildren.set(parent, [])
      parentToChildren.get(parent)!.push(key)
    }
  }
  return { parentToChildren, childToParents }
}

function getDescendants(key: string, graph: DepGraph): string[] {
  const result: string[] = []
  const children = graph.parentToChildren.get(key) ?? []
  for (const child of children) {
    result.push(child)
    result.push(...getDescendants(child, graph))
  }
  return result
}

function getAncestors(key: string, graph: DepGraph): string[] {
  const result: string[] = []
  const visited = new Set<string>()
  const queue = [...(graph.childToParents.get(key) ?? [])]
  while (queue.length > 0) {
    const current = queue.shift()!
    if (visited.has(current)) continue
    visited.add(current)
    result.push(current)
    queue.push(...(graph.childToParents.get(current) ?? []))
  }
  return result
}

// ── NumericInput ─────────────────────────────────────────────────────────────
// Keeps a local string draft so intermediate states like "0.0" or "0.0" aren't
// collapsed to "0" on every keystroke. The numeric value is committed to the
// parent only on blur (or when the string represents a complete, valid number
// that doesn't end with "." / "-").
interface NumericInputProps {
  value: number | undefined
  onChange: (value: number) => void
  min?: number
  max?: number
  step?: number
  className?: string
}

function NumericInput({ value, onChange, min, max, className }: NumericInputProps) {
  const [draft, setDraft] = useState<string>(value !== undefined ? String(value) : "")
  const committedRef = useRef<number | undefined>(value)

  // Sync from parent when value changes externally (e.g. preset load)
  useEffect(() => {
    if (value !== committedRef.current) {
      committedRef.current = value
      setDraft(value !== undefined ? String(value) : "")
    }
  }, [value])

  function handleChange(e: React.ChangeEvent<HTMLInputElement>) {
    const raw = e.target.value
    setDraft(raw)
    // Only commit if the string is a complete valid number (not mid-typing like "0." or "-")
    if (raw !== "" && !raw.endsWith(".") && raw !== "-") {
      const num = Number(raw)
      if (!Number.isNaN(num)) {
        committedRef.current = num
        onChange(num)
      }
    }
  }

  function handleBlur() {
    const num = Number(draft)
    if (draft === "" || Number.isNaN(num)) {
      // Revert to last committed value
      const fallback = committedRef.current
      setDraft(fallback !== undefined ? String(fallback) : "")
      return
    }
    // Clamp to min/max
    const clamped = (min !== undefined && num < min) ? min
      : (max !== undefined && num > max) ? max
      : num
    committedRef.current = clamped
    setDraft(String(clamped))
    if (clamped !== value) onChange(clamped)
  }

  return (
    <input
      type="text"
      inputMode="decimal"
      value={draft}
      onChange={handleChange}
      onBlur={handleBlur}
      className={className}
    />
  )
}

// ── types ───────────────────────────────────────────────────────────────────

interface GroupedParam {
  key: string
  schema: ParamSchemaItem
}

// ── props ───────────────────────────────────────────────────────────────────

interface StrategyConfigFormProps {
  values: Record<string, unknown>
  onChange: (values: Record<string, unknown>) => void
  paramSchema: Record<string, ParamSchemaItem>
  paramGroups: Record<string, ParamGroupDef>
  visibleKeys: Set<string>
  activeParams?: Set<string>
  onActiveParamsChange?: (params: Set<string>) => void
}

export default function StrategyConfigForm({
  values,
  onChange,
  paramSchema,
  paramGroups,
  visibleKeys,
  activeParams,
  onActiveParamsChange,
}: StrategyConfigFormProps) {
  const [expandedPoolGroup, setExpandedPoolGroup] = useState<string | null>(null)

  const depGraph = useMemo(() => buildDepGraph(paramSchema), [paramSchema])

  // ── Organize params into active form and pool ────────────────────────────
  const { activeGrouped, poolGrouped } = useMemo(() => {
    const activeMap = new Map<string, GroupedParam[]>()
    const poolMap = new Map<string, GroupedParam[]>()

    for (const [key, schema] of Object.entries(paramSchema)) {
      if (!visibleKeys.has(key)) continue
      const group = schema.group

      const isActive = activeParams?.has(key) ?? true
      if (isActive) {
        // Skip child params whose ALL parents are inactive
        const parents = normaliseDeps(schema.depends_on)
        if (parents.length > 0 && !parents.some(p => activeParams?.has(p))) continue
        if (!activeMap.has(group)) activeMap.set(group, [])
        activeMap.get(group)!.push({ key, schema })
      } else {
        // Hide pool_hidden params from the pool — they are auto-included with parent
        if (schema.pool_hidden) continue
        if (!poolMap.has(group)) poolMap.set(group, [])
        poolMap.get(group)!.push({ key, schema })
      }
    }

    const sortByOrder = (entries: [string, GroupedParam[]][]) =>
      entries.sort((a, b) => (paramGroups[a[0]]?.order ?? 99) - (paramGroups[b[0]]?.order ?? 99))

    return {
      activeGrouped: sortByOrder([...activeMap.entries()]),
      poolGrouped: sortByOrder([...poolMap.entries()]),
    }
  }, [paramSchema, paramGroups, visibleKeys, activeParams])

  const canManageParams = !!activeParams && !!onActiveParamsChange

  // ── Add with auto-dependency ──────────────────────────────────────────────
  function handleAddParam(key: string) {
    if (!activeParams || !onActiveParamsChange) return
    const next = new Set(activeParams)
    const updatedValues = { ...values }

    const ancestors = getAncestors(key, depGraph)
    for (const ak of ancestors) {
      if (!next.has(ak)) {
        next.add(ak)
        if (updatedValues[ak] === undefined) {
          const s = paramSchema[ak]
          if (s) updatedValues[ak] = s.type === "bool" ? false : (s.default ?? s.disable_value ?? s.min ?? 0)
        }
      }
    }

    next.add(key)
    if (updatedValues[key] === undefined) {
      const s = paramSchema[key]
      if (s) updatedValues[key] = s.type === "bool" ? false : (s.default ?? s.disable_value ?? s.min ?? 0)
    }

    // Auto-include pool_hidden descendants
    const descendants = getDescendants(key, depGraph)
    for (const dk of descendants) {
      const ds = paramSchema[dk]
      if (ds?.pool_hidden && !next.has(dk)) {
        next.add(dk)
        if (updatedValues[dk] === undefined) {
          updatedValues[dk] = ds.type === "bool" ? true : (ds.default ?? ds.min ?? 0)
        }
      }
    }

    onChange(updatedValues)
    onActiveParamsChange(next)
  }

  // ── Remove with cascading children + pool_hidden ancestor cleanup ────────
  function handleRemoveParam(key: string) {
    if (!activeParams || !onActiveParamsChange) return
    const next = new Set(activeParams)
    const updatedValues = { ...values }

    const descendants = getDescendants(key, depGraph)
    for (const dk of descendants) {
      next.delete(dk)
      delete updatedValues[dk]
    }

    next.delete(key)
    delete updatedValues[key]

    // Walk up ancestors: remove pool_hidden ones that have no remaining active children
    function cleanupPoolHiddenAncestors(removedKey: string) {
      const parents = depGraph.childToParents.get(removedKey) ?? []
      for (const parent of parents) {
        const parentSchema = paramSchema[parent]
        if (!parentSchema?.pool_hidden) continue
        const children = depGraph.parentToChildren.get(parent) ?? []
        if (children.some(c => next.has(c))) continue
        next.delete(parent)
        delete updatedValues[parent]
        cleanupPoolHiddenAncestors(parent)
      }
    }
    cleanupPoolHiddenAncestors(key)

    onChange(updatedValues)
    onActiveParamsChange(next)
  }

  function handleChange(key: string, raw: string | boolean, schema: ParamSchemaItem) {
    if (schema.type === "bool") {
      onChange({ ...values, [key]: raw as boolean })
    } else {
      const num = Number(raw)
      const updated = { ...values, [key]: num }

      // Cross-validation: btc_trend_window_2 must be > btc_trend_window_1
      if (key === "btc_trend_window_1" && "btc_trend_window_2" in updated) {
        if ((updated.btc_trend_window_2 as number) <= num) {
          updated.btc_trend_window_2 = Math.min(num + 1, 10)
        }
      }
      if (key === "btc_trend_window_2" && "btc_trend_window_1" in updated) {
        if (num <= (updated.btc_trend_window_1 as number)) {
          updated[key] = Math.min((updated.btc_trend_window_1 as number) + 1, 10)
        }
      }

      onChange(updated)
    }
  }

  // ── Param input renderer ──────────────────────────────────────────────────
  function renderParamInput(key: string, schema: ParamSchemaItem) {
    const currentVal = values[key]
    const isChild = !!schema.depends_on

    if (schema.type === "bool") {
      return (
        <div key={key} className={cn("col-span-1 flex items-center gap-2 rounded-md border px-3 py-2", isChild && "ml-4 border-dashed border-primary/30")}>
          <label className="flex flex-1 cursor-pointer items-center gap-2">
            <input
              type="checkbox"
              checked={!!currentVal}
              onChange={(e) => handleChange(key, e.target.checked, schema)}
              className="h-4 w-4 rounded accent-primary"
            />
            <WeightBadge weight={schema.weight} />
            <span className="text-sm">{t(schema.label)}</span>
          </label>
          {schema.desc && <ParamInfoPopup schema={schema} />}
          {canManageParams && !isChild && (
            <button type="button" onClick={() => handleRemoveParam(key)}
              className="ml-auto rounded p-0.5 text-muted-foreground/50 hover:text-destructive" aria-label="移除参数">
              <XIcon className="size-3" />
            </button>
          )}
        </div>
      )
    }

    return (
      <div key={key} className={cn("flex flex-col gap-1", isChild && "ml-4")}>
        <label className="flex items-center gap-1 text-xs text-muted-foreground">
          <WeightBadge weight={schema.weight} />
          <span>{t(schema.label)}</span>
          {schema.unit && <span className="text-muted-foreground/50">({schema.unit})</span>}
          <ParamInfoPopup schema={schema} />
          {canManageParams && !isChild && (
            <button type="button" onClick={() => handleRemoveParam(key)}
              className="ml-auto rounded p-0.5 text-muted-foreground/50 hover:text-destructive" aria-label="移除参数">
              <XIcon className="size-3" />
            </button>
          )}
        </label>
        <NumericInput
          value={currentVal !== undefined ? Number(currentVal) : undefined}
          onChange={(num) => handleChange(key, String(num), schema)}
          min={schema.min}
          max={schema.max}
          step={schema.step ?? (schema.type === "int" ? 1 : 0.0001)}
          className={cn("h-8 rounded-md border bg-background px-2 text-sm", isChild && "border-dashed border-primary/30")}
        />
      </div>
    )
  }

  const poolTotalCount = useMemo(
    () => poolGrouped.reduce((sum, [, items]) => sum + items.length, 0),
    [poolGrouped],
  )

  return (
    <div className="flex gap-4">
      {/* ══════════════ Main form: active params ══════════════ */}
      <div className="flex-1 flex flex-col gap-5 min-w-0">
        {activeGrouped.length === 0 && (
          <div className="flex flex-col items-center justify-center gap-2 rounded-md border border-dashed py-8 text-muted-foreground">
            <PlusIcon className="size-5" />
            <p className="text-sm">从右侧参数池中选择参数</p>
          </div>
        )}

        {activeGrouped.map(([groupKey, params]) => {
          const groupDef = paramGroups[groupKey]
          const groupLabel = groupDef ? t(groupDef) : groupKey

          const rootParams = params.filter(p => normaliseDeps(p.schema.depends_on).length === 0)
          const childParams = params.filter(p => normaliseDeps(p.schema.depends_on).length > 0)

          // ── Merge co-parent roots into render groups ──────────────────
          // Union-Find: roots that share a common child are rendered together
          const ufMap = new Map<string, string>()
          for (const rp of rootParams) ufMap.set(rp.key, rp.key)
          const ufFind = (k: string): string => {
            while (ufMap.get(k) !== k) { ufMap.set(k, ufMap.get(ufMap.get(k)!)!); k = ufMap.get(k)! }
            return k
          }
          for (const cp of childParams) {
            const rDeps = normaliseDeps(cp.schema.depends_on).filter(p => ufMap.has(p))
            for (let i = 1; i < rDeps.length; i++) {
              const fa = ufFind(rDeps[0]), fb = ufFind(rDeps[i])
              if (fa !== fb) ufMap.set(fa, fb)
            }
          }

          // Build { roots[], children[] } per leader
          const rgMap = new Map<string, { roots: GroupedParam[]; children: GroupedParam[] }>()
          for (const rp of rootParams) {
            const l = ufFind(rp.key)
            if (!rgMap.has(l)) rgMap.set(l, { roots: [], children: [] })
            rgMap.get(l)!.roots.push(rp)
          }
          for (const cp of childParams) {
            const rDeps = normaliseDeps(cp.schema.depends_on).filter(p => ufMap.has(p))
            if (rDeps.length > 0) {
              const l = ufFind(rDeps[0])
              rgMap.get(l)?.children.push(cp)
            }
          }

          // Stable iteration order: follow rootParams order
          const visited = new Set<string>()
          const orderedGroups: { roots: GroupedParam[]; children: GroupedParam[] }[] = []
          for (const rp of rootParams) {
            const l = ufFind(rp.key)
            if (visited.has(l)) continue
            visited.add(l)
            const g = rgMap.get(l)
            if (g) orderedGroups.push(g)
          }

          return (
            <div key={groupKey}>
              <h3 className="mb-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                {groupLabel}
              </h3>
              <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
                {orderedGroups.map(({ roots, children }) => {
                  if (children.length > 0) {
                    return (
                      <div key={roots[0].key} className="col-span-full flex flex-col gap-2 rounded-md border bg-muted/10 p-3">
                        <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
                          {roots.map(({ key: rk, schema: rs }) => renderParamInput(rk, rs))}
                        </div>
                        <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 border-t border-dashed pt-2">
                          {children.map(({ key: ck, schema: cs }) => renderParamInput(ck, cs))}
                        </div>
                      </div>
                    )
                  }
                  return roots.map(({ key, schema }) => renderParamInput(key, schema))
                })}
              </div>
            </div>
          )
        })}
      </div>

      {/* ══════════════ Side panel: parameter pool ══════════════ */}
      {canManageParams && poolTotalCount > 0 && (
        <div className="w-52 shrink-0 rounded-md border bg-muted/30">
          <div className="flex items-center gap-1.5 border-b px-3 py-2">
            <PlusIcon className="size-3.5 text-muted-foreground" />
            <span className="text-xs font-medium">参数池</span>
            <Badge variant="secondary" className="ml-auto text-[10px]">
              {poolTotalCount}
            </Badge>
          </div>
          <ScrollArea className="max-h-[60vh]">
            <div className="flex flex-col">
              {poolGrouped.map(([groupKey, items]) => {
                const groupDef = paramGroups[groupKey]
                const groupLabel = groupDef ? t(groupDef) : groupKey
                const isExpanded = expandedPoolGroup === groupKey

                return (
                  <div key={groupKey}>
                    <button
                      type="button"
                      onClick={() => setExpandedPoolGroup(isExpanded ? null : groupKey)}
                      className="flex w-full items-center gap-1.5 px-3 py-1.5 text-left text-xs font-medium text-muted-foreground hover:bg-muted/50 transition-colors"
                    >
                      <ChevronRightIcon className={cn("size-3 transition-transform", isExpanded && "rotate-90")} />
                      <span className="flex-1">{groupLabel}</span>
                      <Badge variant="outline" className="text-[10px] px-1.5">
                        {items.length}
                      </Badge>
                    </button>

                    {isExpanded && (
                      <div className="flex flex-col gap-0.5 px-1 pb-1">
                        {items.map(({ key, schema }) => (
                          <button
                            key={key}
                            type="button"
                            onClick={() => handleAddParam(key)}
                            className="flex items-center gap-1.5 rounded px-2 py-1 text-left text-xs hover:bg-primary/10 transition-colors"
                          >
                            <PlusIcon className="size-3 shrink-0 text-muted-foreground" />
                            <WeightBadge weight={schema.weight} />
                            <span className="flex-1 truncate">{t(schema.label)}</span>
                          </button>
                        ))}
                      </div>
                    )}
                  </div>
                )
              })}
            </div>
          </ScrollArea>
        </div>
      )}
    </div>
  )
}
