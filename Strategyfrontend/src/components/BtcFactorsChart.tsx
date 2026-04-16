import { useMemo } from "react"
import {
  ResponsiveContainer,
  ComposedChart,
  Line,
  Bar,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ReferenceLine,
} from "recharts"
import type { BtcFactors, BtcPrediction } from "@/types"
import { fmtMsTimeCst, fmtMsDateTimeCst } from "@/lib/utils"

interface BtcFactorsChartProps {
  factors: BtcFactors
}

/** Factor meta for the summary cards */
const FACTOR_META: {
  key: keyof Omit<BtcFactors, "factor_series">
  label: string
  desc: string
  fmt: (v: number) => string
  color: (v: number) => string
}[] = [
  {
    key: "f1_momentum",
    label: "方向动量 f₁",
    desc: "a₁+a₂ — 两段窗口累计涨跌幅，>0 看涨，<0 看跌",
    fmt: (v) => `${v >= 0 ? "+" : ""}${(v * 100).toFixed(4)}%`,
    color: (v) => (v >= 0 ? "text-emerald-600" : "text-red-500"),
  },
  {
    key: "f2_acceleration",
    label: "动量加速度 f₂",
    desc: "|a₂|−|a₁| — >0 表示第二段加速，<0 减速",
    fmt: (v) => `${v >= 0 ? "+" : ""}${(v * 100).toFixed(4)}%`,
    color: (v) => (v > 0 ? "text-emerald-600" : v < 0 ? "text-amber-500" : "text-muted-foreground"),
  },
  {
    key: "f2_consistent",
    label: "方向连续 f₂ˢ",
    desc: "窗口末尾连续同方向K线数 — 越大趋势越一致",
    fmt: (v) => `${v} 根`,
    color: (v) => (v >= 3 ? "text-emerald-600" : v >= 1 ? "text-amber-500" : "text-muted-foreground"),
  },
  {
    key: "f3_vol_norm",
    label: "波动归一化 f₃",
    desc: "动量÷ATR比率 — 消除不同波动环境下的阈值偏移",
    fmt: (v) => v.toFixed(3),
    color: (v) => (Math.abs(v) > 1 ? "text-emerald-600" : "text-muted-foreground"),
  },
  {
    key: "f3_atr_ratio",
    label: "ATR 比率",
    desc: "ATR₂₀÷价格 — 当前波动状态度量",
    fmt: (v) => `${(v * 100).toFixed(4)}%`,
    color: () => "text-muted-foreground",
  },
  {
    key: "f4_volume_z",
    label: "VWAP偏离 f₄",
    desc: "(收盘−VWAP)÷VWAP — >0 价格高于量价中枢(看涨), <0 低于(看跌)",
    fmt: (v) => `${v >= 0 ? "+" : ""}${(v * 10000).toFixed(2)}bp`,
    color: (v) => (v > 0.0002 ? "text-emerald-600" : v < -0.0002 ? "text-red-500" : "text-muted-foreground"),
  },
  {
    key: "f4_volume_dir",
    label: "量比 f₄ᵛ",
    desc: "w2总量÷w1总量 — >1 放量，<1 缩量",
    fmt: (v) => `${v.toFixed(3)}x`,
    color: (v) => (v > 1.2 ? "text-emerald-600" : v < 0.8 ? "text-red-500" : "text-muted-foreground"),
  },
  {
    key: "f5_body_ratio",
    label: "实体比 f₅",
    desc: "窗口内K线|收−开|÷(高−低)均值 — 越接近1越坚决",
    fmt: (v) => `${(v * 100).toFixed(1)}%`,
    color: (v) => (v > 0.6 ? "text-emerald-600" : v < 0.3 ? "text-amber-500" : "text-muted-foreground"),
  },
  {
    key: "f5_wick_imbalance",
    label: "影线失衡 f₅ʷ",
    desc: "窗口内(上影−下影)÷振幅均值 — >0 上方压力大，<0 下方支撑强",
    fmt: (v) => `${v >= 0 ? "+" : ""}${v.toFixed(3)}`,
    color: (v) => (v > 0.3 ? "text-red-500" : v < -0.3 ? "text-emerald-600" : "text-muted-foreground"),
  },
]

/** Chinese labels for prediction component breakdown */
const COMPONENT_LABELS: Record<string, string> = {
  delta_w2: "位移 Δ_W2",
  sigma_1: "1分钟波动率 σ₁",
  sigma_remain: "剩余σ",
  alpha: "因子调节系数 α",
  z_base: "基础z分数",
  z_adjusted: "调节后z分数",
  adj_accel: "加速度调节",
  adj_consistent: "连续streak调节",
  adj_vol: "VWAP量价调节",
  adj_wick: "影线压力调节",
  adj_body: "实体比调节",
}

export default function BtcFactorsChart({ factors }: BtcFactorsChartProps) {
  const series = useMemo(() => {
    return (factors.factor_series ?? []).map((pt) => ({
      ...pt,
      time: fmtMsTimeCst(pt.time_ms),
      fullTime: fmtMsDateTimeCst(pt.time_ms),
      momentum_pct: pt.momentum * 100,
      atr_pct: pt.atr_ratio * 100,
    }))
  }, [factors])

  const hasSeries = series.length > 0
  const pred = factors.prediction as BtcPrediction | null | undefined

  return (
    <div className="flex flex-col gap-5">
      {/* ── Composite Prediction Panel ─────────────────────────── */}
      {pred && (
        <div className="rounded-lg border-2 border-dashed p-4"
          style={{ borderColor: pred.signal === "bullish" ? "hsl(142, 71%, 45%)" : pred.signal === "bearish" ? "hsl(0, 84%, 60%)" : "hsl(var(--border))" }}
        >
          <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:gap-6">
            {/* Left: Probability gauge */}
            <div className="flex flex-col items-center gap-1 sm:min-w-[160px]">
              <div className="text-xs font-medium text-muted-foreground">场次结束看涨概率</div>
              <div className={`text-3xl font-black ${
                pred.signal === "bullish" ? "text-emerald-600" : pred.signal === "bearish" ? "text-red-500" : "text-muted-foreground"
              }`}>
                {(pred.prob_up * 100).toFixed(1)}%
              </div>
              <div className="text-xs text-muted-foreground">
                P(P_end &gt; P_0)
              </div>
              {/* Mini probability bar */}
              <div className="mt-1 flex h-3 w-36 overflow-hidden rounded-full bg-muted">
                <div
                  className="h-full rounded-l-full transition-all"
                  style={{
                    width: `${pred.prob_up * 100}%`,
                    backgroundColor: "hsl(142, 71%, 45%)",
                  }}
                />
                <div
                  className="h-full rounded-r-full transition-all"
                  style={{
                    width: `${pred.prob_down * 100}%`,
                    backgroundColor: "hsl(0, 84%, 60%)",
                  }}
                />
              </div>
              <div className="flex w-36 justify-between text-[10px] text-muted-foreground">
                <span>涨 {(pred.prob_up * 100).toFixed(1)}%</span>
                <span>跌 {(pred.prob_down * 100).toFixed(1)}%</span>
              </div>
            </div>

            {/* Middle: Signal + confidence */}
            <div className="flex flex-col gap-2">
              <div className="flex items-center gap-2">
                <span className={`rounded-md px-2 py-0.5 text-sm font-bold ${
                  pred.signal === "bullish"
                    ? "bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-400"
                    : pred.signal === "bearish"
                    ? "bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400"
                    : "bg-muted text-muted-foreground"
                }`}>
                  {pred.signal === "bullish" ? "看涨" : pred.signal === "bearish" ? "看跌" : "中性"}
                </span>
                <span className={`rounded-md px-2 py-0.5 text-xs ${
                  pred.confidence === "high"
                    ? "bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400"
                    : pred.confidence === "medium"
                    ? "bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400"
                    : "bg-muted text-muted-foreground"
                }`}>
                  置信度: {pred.confidence === "high" ? "高" : pred.confidence === "medium" ? "中" : "低"}
                </span>
                <span className="text-xs text-muted-foreground">
                  z = {pred.raw_score >= 0 ? "+" : ""}{pred.raw_score.toFixed(4)}σ
                </span>
              </div>

              {/* Component breakdown */}
              {pred.components && Object.keys(pred.components).length > 0 && (
                <div className="flex flex-wrap gap-x-3 gap-y-1">
                  {Object.entries(pred.components).map(([name, val]) => {
                    const isAdjustment = name.startsWith("adj_")
                    return (
                      <span key={name} className="text-[10px]">
                        <span className="text-muted-foreground">{COMPONENT_LABELS[name] ?? name}: </span>
                        <span className={isAdjustment ? (val < 0 ? "text-emerald-600" : val > 0 ? "text-red-500" : "text-muted-foreground") : "text-foreground"}>
                          {typeof val === "number" ? (val >= 0 && isAdjustment ? "+" : "") : ""}{typeof val === "number" ? val.toFixed(6) : val}
                        </span>
                      </span>
                    )
                  })}
                </div>
              )}
            </div>
          </div>

          {/* Formula */}
          <div className="mt-3 rounded-md bg-muted/50 px-3 py-2">
            <div className="text-[10px] font-medium text-muted-foreground mb-1">计算公式</div>
            <code className="block whitespace-pre-wrap text-[10px] leading-relaxed text-foreground/80 font-mono">
              {pred.formula}
            </code>
          </div>

          <div className="mt-2 text-[10px] leading-tight text-muted-foreground/60">
            P(P_end &gt; P_0) = F_t(z_adj; df=4) — 基于位移÷波动率的Student-t(df=4)厚尾 CDF模型。
            到第二窗口结束时，BTC已相对P₀位移了Δ_W2，要翻转需在剩余时间内回撤整个位移。
            z_base = Δ_W2 / (σ₁·√剩余分钟) 衡量位移相对剩余波动空间的大小。
            Student-t(4)比正态分布有更厚的尾部，更好地反映BTC实际回报分布。
            因子调节α：连续 streak(β=0.15)·加速度(0.10)·VWAP量价(0.10)缩小σ（趋势更粘），影线压力(0.10)放大σ（反转风险）。
            |P-0.5|≥0.25 为高置信, ≥0.10 中置信, &lt;0.10 低置信。
          </div>
        </div>
      )}

      {/* ── Factor Summary Cards ───────────────────────────────── */}
      <div className="grid gap-3 sm:grid-cols-3 lg:grid-cols-5">
        {FACTOR_META.map((meta) => {
          const val = factors[meta.key] as number
          return (
            <div key={meta.key} className="rounded-md border p-3">
              <div className="text-xs text-muted-foreground">{meta.label}</div>
              <div className={`mt-1 text-sm font-bold ${meta.color(val)}`}>
                {meta.fmt(val)}
              </div>
              <div className="mt-1 text-[10px] leading-tight text-muted-foreground/70">
                {meta.desc}
              </div>
            </div>
          )
        })}
      </div>

      {hasSeries && (
        <>
          {/* ── Chart 1: Momentum + ATR overlay ──────────────────── */}
          <div>
            <h3 className="mb-1 text-xs font-medium text-muted-foreground">
              累计动量 vs 波动率（ATR比率）
              <span className="ml-2 text-[10px] text-muted-foreground/60">
                蓝线=价格累计动量%, 橙色区域=ATR/价格% — 动量应显著超过波动噪声才有效
              </span>
            </h3>
            <div className="h-52">
              <ResponsiveContainer width="100%" height="100%">
                <ComposedChart data={series}>
                  <CartesianGrid strokeDasharray="3 3" opacity={0.3} />
                  <XAxis dataKey="time" tick={{ fontSize: 10 }} interval="preserveStartEnd" />
                  <YAxis
                    yAxisId="left"
                    tickFormatter={(v: number) => `${v.toFixed(2)}%`}
                    tick={{ fontSize: 10 }}
                    width={55}
                  />
                  <YAxis
                    yAxisId="right"
                    orientation="right"
                    tickFormatter={(v: number) => `${v.toFixed(3)}%`}
                    tick={{ fontSize: 10 }}
                    width={55}
                  />
                  <Tooltip
                    labelFormatter={(_v, payload) => {
                      const item = payload?.[0]?.payload
                      return item?.fullTime ?? _v
                    }}
                    formatter={(value, name) => {
                      const n = Number(value)
                      if (name === "累计动量") return [`${n.toFixed(4)}%`, name]
                      if (name === "ATR比率") return [`${n.toFixed(4)}%`, name]
                      return [n.toFixed(4), String(name)]
                    }}
                  />
                  <ReferenceLine yAxisId="left" y={0} stroke="#888" strokeDasharray="3 3" />
                  <Area
                    yAxisId="right"
                    type="monotone"
                    dataKey="atr_pct"
                    stroke="hsl(30, 90%, 55%)"
                    fill="hsl(30, 90%, 55%)"
                    fillOpacity={0.15}
                    strokeWidth={1}
                    dot={false}
                    name="ATR比率"
                  />
                  <Line
                    yAxisId="left"
                    type="monotone"
                    dataKey="momentum_pct"
                    stroke="hsl(217, 91%, 60%)"
                    strokeWidth={2}
                    dot={false}
                    name="累计动量"
                  />
                  <Legend />
                </ComposedChart>
              </ResponsiveContainer>
            </div>
          </div>

          {/* ── Chart 2: VWAP deviation chart ─────────────────── */}
          <div>
            <h3 className="mb-1 text-xs font-medium text-muted-foreground">
              VWAP 偏离
              <span className="ml-2 text-[10px] text-muted-foreground/60">
                绿色=价格高于VWAP(看涨), 红色=低于VWAP(看跌) — 偷离量价中枢越远趋势越强
              </span>
            </h3>
            <div className="h-40">
              <ResponsiveContainer width="100%" height="100%">
                <ComposedChart data={series}>
                  <CartesianGrid strokeDasharray="3 3" opacity={0.3} />
                  <XAxis dataKey="time" tick={{ fontSize: 10 }} interval="preserveStartEnd" />
                  <YAxis
                    tickFormatter={(v: number) => `${(v * 10000).toFixed(1)}bp`}
                    tick={{ fontSize: 10 }}
                    width={55}
                  />
                  <Tooltip
                    labelFormatter={(_v, payload) => {
                      const item = payload?.[0]?.payload
                      return item?.fullTime ?? _v
                    }}
                    formatter={(value) => [`${(Number(value) * 10000).toFixed(2)}bp`, "VWAP偏离"]}
                  />
                  <ReferenceLine y={0} stroke="#888" strokeDasharray="3 3" />
                  <Bar
                    dataKey="vol_z"
                    name="VWAP偏离"
                    fill="hsl(217, 91%, 60%)"
                    opacity={0.8}
                    // Color per bar handled via cell render
                  />
                  <Legend />
                </ComposedChart>
              </ResponsiveContainer>
            </div>
          </div>

          {/* ── Chart 3: Candle structure (body ratio + wick imbalance) ── */}
          <div>
            <h3 className="mb-1 text-xs font-medium text-muted-foreground">
              K线结构质量
              <span className="ml-2 text-[10px] text-muted-foreground/60">
                紫线=实体比(越高越坚决,窗口均值), 橙线=影线失衡(&gt;0上方压力,&lt;0下方支撑,窗口均值)
              </span>
            </h3>
            <div className="h-40">
              <ResponsiveContainer width="100%" height="100%">
                <ComposedChart data={series}>
                  <CartesianGrid strokeDasharray="3 3" opacity={0.3} />
                  <XAxis dataKey="time" tick={{ fontSize: 10 }} interval="preserveStartEnd" />
                  <YAxis
                    domain={[-1, 1]}
                    tickFormatter={(v: number) => v.toFixed(1)}
                    tick={{ fontSize: 10 }}
                    width={35}
                  />
                  <Tooltip
                    labelFormatter={(_v, payload) => {
                      const item = payload?.[0]?.payload
                      return item?.fullTime ?? _v
                    }}
                    formatter={(value, name) => [Number(value).toFixed(3), String(name)]}
                  />
                  <ReferenceLine y={0} stroke="#888" strokeDasharray="3 3" />
                  <Line
                    type="monotone"
                    dataKey="body_ratio"
                    stroke="hsl(270, 70%, 60%)"
                    strokeWidth={1.5}
                    dot={false}
                    name="实体比"
                  />
                  <Line
                    type="monotone"
                    dataKey="wick_imb"
                    stroke="hsl(30, 90%, 55%)"
                    strokeWidth={1.5}
                    dot={false}
                    name="影线失衡"
                  />
                  <Legend />
                </ComposedChart>
              </ResponsiveContainer>
            </div>
          </div>
        </>
      )}
    </div>
  )
}
