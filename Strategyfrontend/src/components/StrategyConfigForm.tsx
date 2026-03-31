import { InfoIcon } from "lucide-react"
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip"

/** Strategy parameter → { Chinese label, tooltip description } */
const PARAM_I18N: Record<string, { label: string; tip: string }> = {
  // ── solid_core ──
  min_price:            { label: "最低价格",     tip: "入场所需的最低市场价格，低于此不开仓" },
  time_remaining_ratio: { label: "剩余时间比",   tip: "进入窗口所需的剩余时间 / 总时长比值（如 0.333 = 最后 1/3 时间）" },
  momentum_window:      { label: "动量窗口",     tip: "计算价格动量的回看秒数" },
  momentum_min:         { label: "最小动量",     tip: "窗口内价格涨幅必须达到此比例才视为有上行动量" },
  volatility_window:    { label: "波动窗口",     tip: "计算振幅和标准差所用的回看秒数" },
  amplitude_min:        { label: "最小振幅",     tip: "窗口内价格振幅（最高-最低）的下限" },
  amplitude_max:        { label: "最大振幅",     tip: "窗口内价格振幅的上限，超出则波动过大" },
  max_std:              { label: "最大标准差",   tip: "窗口内价格标准差上限，控制噪声水平" },
  max_drawdown:         { label: "最大回撤",     tip: "窗口内允许的最大回撤比例" },
  position_min_pct:     { label: "最小仓位%",    tip: "单次买入占可用余额的最小比例" },
  position_max_pct:     { label: "最大仓位%",    tip: "单次买入占可用余额的最大比例" },
  reverse_tick_window:  { label: "反转检测窗口", tip: "检测最近 N 秒内是否出现大幅反向波动" },
  reverse_threshold:    { label: "反转阈值",     tip: "单次跌幅超过此值视为反向信号，阻止入场" },
  // ── mean_reversion ──
  window:               { label: "均线窗口",     tip: "移动平均线的回看 tick 数" },
  entry_std:            { label: "入场标准差",   tip: "价格偏离均线超过 N 个标准差时入场" },
  exit_std:             { label: "出场标准差",   tip: "价格回归到偏离均线 N 个标准差内时平仓" },
  // ── momentum ──
  lookback:             { label: "回看周期",     tip: "计算动量信号的回看 tick 数" },
  // ── common ──
  position_size:        { label: "仓位大小",     tip: "每笔交易的目标数量（股/份）" },
}

function getParamInfo(key: string) {
  return PARAM_I18N[key] ?? { label: key, tip: "" }
}

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
        const info = getParamInfo(key)

        return (
          <div key={key} className="flex flex-col gap-1">
            <label className="flex items-center gap-1 text-xs text-muted-foreground">
              <span>{info.label}</span>
              {info.tip && (
                <Tooltip>
                  <TooltipTrigger asChild>
                    <InfoIcon className="size-3 shrink-0 cursor-help text-muted-foreground/60" />
                  </TooltipTrigger>
                  <TooltipContent side="top">
                    <p>{info.tip}</p>
                  </TooltipContent>
                </Tooltip>
              )}
            </label>
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
