import { useMemo, useState, useRef, useCallback } from "react"
import { InfoIcon, XIcon } from "lucide-react"
import type { ParamSchemaItem, ParamGroupDef } from "@/types"

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
}

export default function StrategyConfigForm({
  values,
  onChange,
  paramSchema,
  paramGroups,
  visibleKeys,
}: StrategyConfigFormProps) {
  // Group params by group, sorted by group order, filtered to visible keys
  const grouped = useMemo(() => {
    const map = new Map<string, GroupedParam[]>()

    for (const [key, schema] of Object.entries(paramSchema)) {
      if (!visibleKeys.has(key)) continue
      // If param depends on a toggle, check if toggle is off → skip
      if (schema.depends_on && !values[schema.depends_on]) continue

      const group = schema.group
      if (!map.has(group)) map.set(group, [])
      map.get(group)!.push({ key, schema })
    }

    // Sort groups by order
    const sorted = [...map.entries()].sort((a, b) => {
      const orderA = paramGroups[a[0]]?.order ?? 99
      const orderB = paramGroups[b[0]]?.order ?? 99
      return orderA - orderB
    })

    return sorted
  }, [paramSchema, paramGroups, visibleKeys, values])

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

  return (
    <div className="flex flex-col gap-5">
      {grouped.map(([groupKey, params]) => {
        const groupDef = paramGroups[groupKey]
        const groupLabel = groupDef ? t(groupDef) : groupKey

        return (
          <div key={groupKey}>
            <h3 className="mb-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
              {groupLabel}
            </h3>
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
              {params.map(({ key, schema }) => {
                const currentVal = values[key]
                const label = t(schema.label)

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
            </div>
          </div>
        )
      })}
    </div>
  )
}
