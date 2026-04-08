import { useMemo, useState, useRef, useCallback } from "react"
import { InfoIcon, XIcon, PlusIcon, CheckIcon } from "lucide-react"
import type { ParamSchemaItem, ParamGroupDef } from "@/types"
import { Popover, PopoverTrigger, PopoverContent } from "@/components/ui/popover"
import { Badge } from "@/components/ui/badge"
import { ScrollArea } from "@/components/ui/scroll-area"
import { Checkbox } from "@/components/ui/checkbox"

// ── helpers ─────────────────────────────────────────────────────────────────

/** Get localised text — always zh for now, fallback to en */
function t(label: { zh: string; en: string } | string): string {
  if (typeof label === "string") return label
  return label.zh || label.en
}

// ── ParamInfoPopup ─────────────────────────────────────────────────────────

interface ParamInfoPopupProps {
  schema: ParamSchemaItem
}

function ParamInfoPopup({ schema }: ParamInfoPopupProps) {
  const [open, setOpen] = useState(false)
  // position relative to viewport center offset
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
          {/* Drag handle */}
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
  /** Keys that exist in the current strategy default_config (to filter relevant params) */
  visibleKeys: Set<string>
  /** Currently active param keys (core always included; advanced toggled by user) */
  activeParams?: Set<string>
  /** Called when user adds/removes advanced params */
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
  // Group params by group, sorted by group order, filtered to visible keys
  const { grouped, inactiveByGroup } = useMemo(() => {
    const map = new Map<string, GroupedParam[]>()
    const inactive = new Map<string, GroupedParam[]>()

    for (const [key, schema] of Object.entries(paramSchema)) {
      if (!visibleKeys.has(key)) continue
      // If param depends on a toggle, check if toggle is off → skip
      if (schema.depends_on && !values[schema.depends_on]) continue

      const group = schema.group

      // When activeParams is provided, advanced params not in activeParams go to inactive list
      if (activeParams && onActiveParamsChange && schema.visibility === "advanced" && !activeParams.has(key)) {
        if (!inactive.has(group)) inactive.set(group, [])
        inactive.get(group)!.push({ key, schema })
        continue
      }

      if (!map.has(group)) map.set(group, [])
      map.get(group)!.push({ key, schema })
    }

    // Also collect inactive params whose toggle is off but the toggle itself is inactive
    // (these are already excluded above, which is correct)

    // Sort groups by order
    const sorted = [...map.entries()].sort((a, b) => {
      const orderA = paramGroups[a[0]]?.order ?? 99
      const orderB = paramGroups[b[0]]?.order ?? 99
      return orderA - orderB
    })

    return { grouped: sorted, inactiveByGroup: inactive }
  }, [paramSchema, paramGroups, visibleKeys, values, activeParams, onActiveParamsChange])

  if (grouped.length === 0) {
    return <p className="text-sm text-muted-foreground">该策略无可配置参数</p>
  }

  function handleChange(key: string, raw: string | boolean, schema: ParamSchemaItem) {
    if (schema.type === "bool") {
      const updated = { ...values, [key]: raw as boolean }
      // When a toggle is turned OFF, reset dependent params to disable_value
      if (!(raw as boolean)) {
        for (const [depKey, depSchema] of Object.entries(paramSchema)) {
          if (depSchema.depends_on === key && depSchema.disable_value != null) {
            updated[depKey] = depSchema.disable_value
          }
        }
      }
      onChange(updated)
    } else {
      onChange({ ...values, [key]: Number(raw) })
    }
  }

  function handleAddParams(keys: string[]) {
    if (!activeParams || !onActiveParamsChange) return
    const next = new Set(activeParams)
    const updatedValues = { ...values }
    for (const key of keys) {
      next.add(key)
      // Initialise with schema default (min or disable_value) if not already set
      if (updatedValues[key] === undefined) {
        const schema = paramSchema[key]
        if (schema) {
          if (schema.type === "bool") {
            updatedValues[key] = false
          } else {
            updatedValues[key] = schema.disable_value ?? schema.min ?? 0
          }
        }
      }
    }
    onChange(updatedValues)
    onActiveParamsChange(next)
  }

  function handleRemoveParam(key: string) {
    if (!activeParams || !onActiveParamsChange) return
    const next = new Set(activeParams)
    next.delete(key)
    // Also remove dependent params whose toggle is this key
    for (const [depKey, depSchema] of Object.entries(paramSchema)) {
      if (depSchema.depends_on === key) next.delete(depKey)
    }
    // Remove values for removed keys
    const updatedValues = { ...values }
    delete updatedValues[key]
    for (const [depKey, depSchema] of Object.entries(paramSchema)) {
      if (depSchema.depends_on === key) delete updatedValues[depKey]
    }
    onChange(updatedValues)
    onActiveParamsChange(next)
  }

  const canManageParams = !!activeParams && !!onActiveParamsChange

  return (
    <div className="flex flex-col gap-5">
      {grouped.map(([groupKey, params]) => {
        const groupDef = paramGroups[groupKey]
        const groupLabel = groupDef ? t(groupDef) : groupKey
        const inactiveParams = inactiveByGroup.get(groupKey) ?? []

        return (
          <div key={groupKey}>
            <h3 className="mb-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
              {groupLabel}
            </h3>
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
              {params.map(({ key, schema }) => {
                const currentVal = values[key]
                const label = t(schema.label)
                const isAdvanced = canManageParams && schema.visibility === "advanced"

                if (schema.type === "bool") {
                  return (
                    <div
                      key={key}
                      className="col-span-1 flex items-center gap-2 rounded-md border px-3 py-2"
                    >
                      <label className="flex flex-1 cursor-pointer items-center gap-2">
                        <input
                          type="checkbox"
                          checked={!!currentVal}
                          onChange={(e) => handleChange(key, e.target.checked, schema)}
                          className="h-4 w-4 rounded accent-primary"
                        />
                        <span className="text-sm">{label}</span>
                      </label>
                      {schema.desc && (
                        <ParamInfoPopup schema={schema} />
                      )}
                      {isAdvanced && (
                        <button
                          type="button"
                          onClick={() => handleRemoveParam(key)}
                          className="ml-auto rounded p-0.5 text-muted-foreground/50 hover:text-destructive"
                          aria-label="移除参数"
                        >
                          <XIcon className="size-3" />
                        </button>
                      )}
                    </div>
                  )
                }

                return (
                  <div key={key} className="flex flex-col gap-1">
                    <label className="flex items-center gap-1 text-xs text-muted-foreground">
                      <span>{label}</span>
                      {schema.unit && (
                        <span className="text-muted-foreground/50">({schema.unit})</span>
                      )}
                      <ParamInfoPopup schema={schema} />
                      {isAdvanced && (
                        <button
                          type="button"
                          onClick={() => handleRemoveParam(key)}
                          className="ml-auto rounded p-0.5 text-muted-foreground/50 hover:text-destructive"
                          aria-label="移除参数"
                        >
                          <XIcon className="size-3" />
                        </button>
                      )}
                    </label>
                    <input
                      type="number"
                      value={currentVal !== undefined ? String(currentVal) : ""}
                      onChange={(e) => handleChange(key, e.target.value, schema)}
                      min={schema.min}
                      max={schema.max}
                      step={schema.step ?? (schema.type === "int" ? 1 : 0.01)}
                      className="h-8 rounded-md border bg-background px-2 text-sm"
                    />
                  </div>
                )
              })}

              {/* Add advanced param button */}
              {canManageParams && inactiveParams.length > 0 && (
                <AddParamPopover
                  inactiveParams={inactiveParams}
                  onAdd={handleAddParams}
                />
              )}
            </div>
          </div>
        )
      })}

      {/* Show groups that have ONLY inactive params (all advanced, none active) */}
      {canManageParams && (() => {
        const activeGroupKeys = new Set(grouped.map(([k]) => k))
        const hiddenGroups = [...inactiveByGroup.entries()]
          .filter(([gk, items]) => !activeGroupKeys.has(gk) && items.length > 0)
          .sort((a, b) => (paramGroups[a[0]]?.order ?? 99) - (paramGroups[b[0]]?.order ?? 99))
        if (hiddenGroups.length === 0) return null
        return hiddenGroups.map(([groupKey, inactiveParams]) => {
          const groupDef = paramGroups[groupKey]
          const groupLabel = groupDef ? t(groupDef) : groupKey
          return (
            <div key={groupKey}>
              <h3 className="mb-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                {groupLabel}
              </h3>
              <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
                <AddParamPopover
                  inactiveParams={inactiveParams}
                  onAdd={handleAddParams}
                />
              </div>
            </div>
          )
        })
      })()}
    </div>
  )
}

// ── AddParamPopover ─────────────────────────────────────────────────────────

interface AddParamPopoverProps {
  inactiveParams: GroupedParam[]
  onAdd: (keys: string[]) => void
}

function AddParamPopover({ inactiveParams, onAdd }: AddParamPopoverProps) {
  const [open, setOpen] = useState(false)
  const [selected, setSelected] = useState<Set<string>>(new Set())

  function toggle(key: string) {
    setSelected((prev) => {
      const next = new Set(prev)
      if (next.has(key)) next.delete(key)
      else next.add(key)
      return next
    })
  }

  function handleConfirm() {
    if (selected.size > 0) {
      onAdd([...selected])
      setSelected(new Set())
    }
    setOpen(false)
  }

  return (
    <Popover open={open} onOpenChange={(v) => { setOpen(v); if (!v) setSelected(new Set()) }}>
      <PopoverTrigger asChild>
        <button
          type="button"
          className="flex h-8 items-center gap-1 rounded-md border border-dashed border-muted-foreground/30 px-3 text-xs text-muted-foreground hover:border-primary/50 hover:text-foreground transition-colors"
        >
          <PlusIcon className="size-3" />
          添加参数
          <Badge variant="secondary" className="ml-1 text-[10px]">
            {inactiveParams.length}
          </Badge>
        </button>
      </PopoverTrigger>
      <PopoverContent className="w-72 p-0" align="start">
        <div className="border-b px-3 py-2">
          <p className="text-xs font-medium">选择要添加的高级参数</p>
        </div>
        <ScrollArea className="max-h-60">
          <div className="flex flex-col gap-0.5 p-2">
            {inactiveParams.map(({ key, schema }) => (
              <button
                key={key}
                type="button"
                onClick={() => toggle(key)}
                className="flex items-center gap-2 rounded-md px-2 py-1.5 text-left text-sm hover:bg-muted transition-colors"
              >
                <Checkbox
                  checked={selected.has(key)}
                  onCheckedChange={() => toggle(key)}
                  aria-label={t(schema.label)}
                />
                <span className="flex-1 truncate">{t(schema.label)}</span>
              </button>
            ))}
          </div>
        </ScrollArea>
        <div className="flex items-center justify-end gap-2 border-t px-3 py-2">
          <button
            type="button"
            onClick={() => { setOpen(false); setSelected(new Set()) }}
            className="h-7 rounded-md px-3 text-xs hover:bg-muted"
          >
            取消
          </button>
          <button
            type="button"
            disabled={selected.size === 0}
            onClick={handleConfirm}
            className="h-7 rounded-md bg-primary px-3 text-xs text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
          >
            添加 {selected.size > 0 && `(${selected.size})`}
          </button>
        </div>
      </PopoverContent>
    </Popover>
  )
}
