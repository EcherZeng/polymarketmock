interface StrategyConfigFormProps {
  defaultConfig: Record<string, number | string | boolean>
  values: Record<string, unknown>
  onChange: (values: Record<string, unknown>) => void
}

export default function StrategyConfigForm({ defaultConfig, values, onChange }: StrategyConfigFormProps) {
  const entries = Object.entries(defaultConfig)

  if (entries.length === 0) {
    return <p className="text-sm text-muted-foreground">该策略无可配置参数</p>
  }

  function handleChange(key: string, raw: string, type: string) {
    const val = type === "number" ? Number(raw) : raw
    onChange({ ...values, [key]: val })
  }

  return (
    <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4">
      {entries.map(([key, defaultVal]) => {
        const type = typeof defaultVal
        const currentVal = values[key] ?? defaultVal

        return (
          <div key={key} className="flex flex-col gap-1">
            <label className="text-xs text-muted-foreground">{key}</label>
            <input
              type={type === "number" ? "number" : "text"}
              value={String(currentVal)}
              onChange={(e) => handleChange(key, e.target.value, type)}
              step={type === "number" && Number(defaultVal) < 1 ? "0.1" : "1"}
              className="h-8 rounded-md border bg-background px-2 text-sm"
            />
          </div>
        )
      })}
    </div>
  )
}
