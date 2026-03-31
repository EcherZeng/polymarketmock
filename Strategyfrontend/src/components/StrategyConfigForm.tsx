import { useMemo } from "react"
import { InfoIcon } from "lucide-react"
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip"
import type { ParamSchemaItem, ParamGroupDef } from "@/types"

// ── helpers ─────────────────────────────────────────────────────────────────

/** Get localised text — always zh for now, fallback to en */
function t(label: { zh: string; en: string } | string): string {
  if (typeof label === "string") return label
  return label.zh || label.en
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
      onChange({ ...values, [key]: raw as boolean })
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
                    <label
                      key={key}
                      className="col-span-1 flex items-center gap-2 rounded-md border px-3 py-2"
                    >
                      <input
                        type="checkbox"
                        checked={!!currentVal}
                        onChange={(e) => handleChange(key, e.target.checked, schema)}
                        className="h-4 w-4 rounded accent-primary"
                      />
                      <span className="text-sm">{label}</span>
                    </label>
                  )
                }

                return (
                  <div key={key} className="flex flex-col gap-1">
                    <label className="flex items-center gap-1 text-xs text-muted-foreground">
                      <span>{label}</span>
                      {schema.unit && (
                        <span className="text-muted-foreground/50">({schema.unit})</span>
                      )}
                      <Tooltip>
                        <TooltipTrigger asChild>
                          <InfoIcon className="size-3 shrink-0 cursor-help text-muted-foreground/50" />
                        </TooltipTrigger>
                        <TooltipContent side="top" className="max-w-xs">
                          <p className="text-xs">
                            {schema.min !== undefined && schema.max !== undefined
                              ? `范围: ${schema.min} ~ ${schema.max}`
                              : key}
                          </p>
                        </TooltipContent>
                      </Tooltip>
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
