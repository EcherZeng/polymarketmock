# 策略参数说明

> 参数来源：`strategy_presets.json` → `param_schema`
> 
> **参数激活规则**：前端采用「参数池自选」模式，选中参数即启用，未选中即禁用（不发送给后端）。

---

## 一、风控规则（Risk Management）

| 参数键 | 中文名 | 类型 | 禁用值 | 说明 |
|---|---|---|---|---|
| `take_profit_price` | 止盈价格 | float [0.5, 1.0] | 1.0 | 持仓标的中间价达到此价格时自动触发止盈平仓 |
| `take_profit_pct` | 止盈比例（基于本金） | float [0.0, 1.0] | 0.0 | 账户权益相对初始本金盈利超过此比例时触发止盈 |
| `stop_loss_price` | 止损价格 | float [0.0, 1.0] | 0.0 | 持仓标的中间价跌破此价格时自动触发止损平仓 |
| `stop_loss_pct` | 止损比例（基于本金） | float [0.0, 1.0] | 0.0 | 账户权益相对初始本金亏损超过此比例时触发止损 |
| `force_close_remaining_seconds` | 强制平仓剩余秒数 | int [0, 300] | 0 | 市场到期前剩余秒数不足此值时强制平掉所有持仓 |
| `consecutive_loss_threshold` | 连续亏损降仓阈值 | int [1, 20] | 20 | 连续亏损次数达到此值时触发仓位缩减机制 |
| `loss_position_reduction_pct` | 亏损降仓比例 | float [0.0, 1.0] | 0.0 | 触发连续亏损阈值后每次入场仓位缩减的比例 |
| `exit_use_orderbook_mode` | 平仓盘口撮合模式 | bool | — | 开启后通过 orderbook 买方深度按 VWAP 撮合卖出 |
| ↳ `exit_min_sell_price` | 退出最低卖出价 | float [0.0, 1.0] | 0.0 | 盘口撮合模式下低于此价格的买方挂单不参与撮合。**需先选 `exit_use_orderbook_mode`** |
| ↳ `exit_reduction_pct` | 退出每 tick 减仓比例 | float [0.01, 1.0] | 1.0 | 盘口撮合模式下每个 tick 最多减掉剩余仓位的比例。**需先选 `exit_use_orderbook_mode`** |

---

## 二、入场条件（Entry Conditions）

| 参数键 | 中文名 | 类型 | 禁用值 | 说明 |
|---|---|---|---|---|
| `min_price` | 入场最低价格 | float [0.01, 1.0] | 0.01 | 只在中间价高于此阈值的标的上入场 |
| `time_remaining_ratio` | 剩余时间比例阈值 | float [0.0, 1.0] | 1.0 | 只允许在剩余时间比例低于此阈值时入场 |
| `max_spread` | 最大 Spread 阈值 | float [0.01, 1.0] | 1.0 | 入场时 best_ask − best_bid 超过此值则跳过 |
| `max_ask_deviation` | 最大 Ask 偏离度 | float [0.01, 1.0] | 1.0 | best_ask 相对锚点价格偏离比例上限 |
| `min_profit_room` | 最小利润空间 | float [0.0, 0.5] | 0.0 | 要求 `1.0 − best_ask > 此值` 才入场 |
| `max_entry_count` | 单场买入次数最多 | int [1, 50] | null | 单个市场内最多允许的买入次数；选中即启用 |

---

## 三、动量检测（Momentum Detection）

| 参数键 | 中文名 | 类型 | 禁用值 | 依赖 | 说明 |
|---|---|---|---|---|---|
| `momentum_window` | 动量检测窗口 | int [60, 3600] 秒 | null | — | 计算入场动量所用的历史价格窗口时长；选中即启用动量检测 |
| ↳ `momentum_min` | 最小涨幅 | float [0.0, 0.1] | 0.0 | `momentum_window` | 入场所需的最小动量涨幅 |
| `direction_window` | 方向一致性检测窗口 | int [60, 3600] 秒 | null | — | 要求窗口内上涨 tick 占比 > 50%；选中即启用 |

---

## 四、波动检测（Volatility Detection）

| 参数键 | 中文名 | 类型 | 禁用值 | 依赖 | 说明 |
|---|---|---|---|---|---|
| `volatility_window` | 波动检测窗口 | int [60, 3600] 秒 | null | — | 振幅、标准差、回撤共用的历史窗口；选中即启用波动检测 |
| ↳ `amplitude_min` | 振幅下限 | float [0.0, 5.0] | 0.0 | `volatility_window` | 入场所需最小价格振幅 |
| ↳ `amplitude_max` | 振幅上限 | float [0.0, 5.0] | 5.0 | `volatility_window` | 入场允许最大价格振幅 |
| ↳ `max_std` | 最大标准差 | float [0.0, 1.0] | 1.0 | `volatility_window` | 入场允许最大相对标准差 |
| ↳ `max_drawdown` | 窗口最大回撤 | float [0.0, 1.0] | 1.0 | `volatility_window` | 入场允许波动窗口内最大回撤比例 |
| `reverse_tick_window` | 反向检测窗口 | int [5, 300] 秒 | null | — | 检测近期反向回调的时间窗口；选中即启用反转检测 |
| ↳ `reverse_threshold` | 反向波动阈值 | float [0.0, 0.1] | 0.1 | `reverse_tick_window` | 反向窗口内价格回调超过此值则放弃入场 |

---

## 五、仓位管理（Position Sizing）

| 参数键 | 中文名 | 类型 | 禁用值 | 说明 |
|---|---|---|---|---|
| `position_min_pct` | 最小仓位比例 | float [0.01, 1.0] | 0.01 | 单次入场使用的最小仓位比例（占可用资金） |
| `position_max_pct` | 最大仓位比例 | float [0.01, 1.0] | 1.0 | 单次入场使用的最大仓位比例（占可用资金） |

---

## 参数依赖关系（自动关联）

选中子参数时，前端自动添加其父参数；移除父参数时，子参数联动移除。

```
exit_use_orderbook_mode
  ├── exit_min_sell_price
  └── exit_reduction_pct

momentum_window
  └── momentum_min

volatility_window
  ├── amplitude_min
  ├── amplitude_max
  ├── max_std
  └── max_drawdown

reverse_tick_window
  └── reverse_threshold
```

---

## 参数分组（scope 说明）

| scope 值 | 含义 |
|---|---|
| `unified` | 全局风控参数，所有策略共用（在 `unified_rules` 中设置默认值） |
| `strategy` | 策略级参数，每个策略可独立配置 |
