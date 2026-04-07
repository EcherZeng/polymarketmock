# 策略参数说明

> 参数来源：`strategy_presets.json` → `param_schema`

---

## 一、风控规则（Risk Management）

| 参数键 | 中文名 | 类型 | 禁用值 | 说明 |
|---|---|---|---|---|
| `take_profit_price` | 止盈价格 | float [0.5, 1.0] | 1.0 | 持仓标的中间价达到此价格时自动触发止盈平仓 |
| `take_profit_pct` | 止盈比例（基于买入价） | float [0.0, 1.0] | 0.0 | 价格相对买入价上涨超过此比例时触发止盈；与绝对止盈价独立生效 |
| `stop_loss_price` | 止损价格 | float [0.0, 1.0] | 0.0 | 持仓标的中间价跌破此价格时自动触发止损平仓 |
| `stop_loss_pct` | 止损比例（基于买入价） | float [0.0, 1.0] | 0.0 | 价格相对买入价下跌超过此比例时触发止损；与绝对止损价独立生效 |
| `force_close_remaining_seconds` | 强制平仓剩余秒数 | int [0, 300] | 0 | 市场到期前剩余秒数不足此值时强制平掉所有持仓 |
| `consecutive_loss_threshold` | 连续亏损降仓阈值 | int [1, 20] | 20 | 连续亏损次数达到此值时触发仓位缩减机制 |
| `loss_position_reduction_pct` | 亏损降仓比例 | float [0.0, 1.0] | 0.0 | 触发连续亏损阈值后每次入场仓位缩减的比例；0=不缩减，1=完全不入场 |
| `exit_use_orderbook_mode` | 退出使用挂单减仓模式 | bool | — | 关闭=理想卖出（无滑点）；开启=通过 orderbook 深度 VWAP 撮合卖出 |
| `exit_min_sell_price` | 退出最低卖出价 | float [0.0, 1.0] | 0.0 | 挂单减仓模式下低于此价格的买方挂单不参与撮合 |
| `exit_reduction_pct` | 退出每 tick 减仓比例 | float [0.0, 1.0] | 1.0 | 挂单减仓模式下每个 tick 最多减掉剩余仓位的此比例 |

---

## 二、入场条件（Entry Conditions）

| 参数键 | 中文名 | 类型 | 禁用值 | 说明 |
|---|---|---|---|---|
| `min_price` | 入场最低价格 | float [0.5, 1.0] | 0.5 | 只在中间价高于此阈值的标的上入场，过滤价格过低、流动性差的标的 |
| `time_remaining_ratio` | 剩余时间比例阈值 | float [0.0, 1.0] | 1.0 | 只允许在剩余时间比例（剩余 ticks / 总 ticks）低于此阈值时入场 |
| `momentum_window` | 动量检测窗口 | int [60, 3600] 秒 | — | 计算入场动量所用的历史价格窗口时长；需开启「启用动量检测」 |
| `momentum_min` | 最小涨幅 | float [0.0, 0.1] | 0.0 | 入场所需的最小动量涨幅，过滤横盘或下跌行情；需开启「启用动量检测」 |
| `max_spread` | 最大 Spread 阈值 | float [0.01, 1.0] | 1.0 | 入场时 best_ask − best_bid 超过此值则跳过，避免宽价差市场 |
| `max_ask_deviation` | 最大 Ask 偏离度 | float [0.01, 1.0] | 1.0 | best_ask 相对锚点价格偏离比例上限，防止实际买入价远高于参考价 |
| `min_profit_room` | 最小利润空间 | float [0.0, 0.5] | 0.0 | 要求 `1.0 − best_ask > 此值` 才入场，确保有足够潜在利润空间 |

---

## 三、波动过滤（Volatility Filters）

| 参数键 | 中文名 | 类型 | 禁用值 | 说明 |
|---|---|---|---|---|
| `volatility_window` | 波动检测窗口 | int [60, 3600] 秒 | — | 振幅、标准差、最大回撤等指标共用的历史窗口时长 |
| `amplitude_min` | 振幅下限 | float [0.0, 5.0] | 0.0 | 入场所需最小价格振幅（窗口高低价差/最低价）；需开启「启用振幅检测」 |
| `amplitude_max` | 振幅上限 | float [0.0, 5.0] | 5.0 | 入场允许最大价格振幅，防止在波动过大市场进场；需开启「启用振幅检测」 |
| `max_std` | 最大标准差 | float [0.0, 1.0] | 1.0 | 入场允许最大相对标准差（std/均价），过高说明价格不稳定；需开启「启用标准差检测」 |
| `max_drawdown` | 窗口最大回撤 | float [0.0, 1.0] | 1.0 | 入场允许波动窗口内最大回撤比例（峰值到底部跌幅）；需开启「启用回撤检测」 |
| `reverse_tick_window` | 反向检测窗口 | int [5, 300] 秒 | — | 检测近期是否存在反向回调的时间窗口；需开启「启用反转检测」 |
| `reverse_threshold` | 反向波动阈值 | float [0.0, 0.1] | 0.1 | 反向窗口内价格回调超过此值则放弃入场；需开启「启用反转检测」 |

---

## 四、仓位管理（Position Sizing）

| 参数键 | 中文名 | 类型 | 禁用值 | 说明 |
|---|---|---|---|---|
| `position_min_pct` | 最小仓位比例 | float [0.01, 1.0] | 0.01 | 单次入场使用的最小仓位比例（占可用资金） |
| `position_max_pct` | 最大仓位比例 | float [0.01, 1.0] | 1.0 | 单次入场使用的最大仓位比例（占可用资金） |

---

## 五、特性开关（Feature Toggles）

| 参数键 | 中文名 | 依赖参数 | 说明 |
|---|---|---|---|
| `use_momentum_check` | 启用动量检测 | `momentum_window`, `momentum_min` | 开启后过滤低涨幅标的，只选取高涨幅趋势标的入场 |
| `use_direction_check` | 启用方向一致性检测 | `direction_window` | 开启后要求窗口内上涨 tick 占比 > 50% 才允许入场 |
| `use_std_check` | 启用标准差检测 | `max_std` | 开启后过滤相对标准差过高（价格不稳定）的市场 |
| `use_drawdown_check` | 启用回撤检测 | `max_drawdown` | 开启后过滤窗口最大回撤过高的市场，避免追跌 |
| `use_amplitude_check` | 启用振幅检测 | `amplitude_min`, `amplitude_max` | 开启后要求振幅落在 [振幅下限, 振幅上限] 范围内 |
| `use_reverse_check` | 启用反转检测 | `reverse_tick_window`, `reverse_threshold` | 开启后检测近期局部反转，防止在已反转时追高 |

---

## 参数分组（scope 说明）

| scope 值 | 含义 |
|---|---|
| `unified` | 全局风控参数，所有策略共用（在 `unified_rules` 中设置默认值） |
| `strategy` | 策略级参数，每个策略可独立配置 |
