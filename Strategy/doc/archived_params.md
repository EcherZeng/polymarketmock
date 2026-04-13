# 已归档策略参数

> **归档日期**：2026-04-13
>
> **归档原因**：策略参数精简，仅保留 7 个核心参数（止盈价格、止损价格、强制平仓秒数、入场最低价、剩余时间比例阈值、最小仓位比例、最大仓位比例），以下参数从计算逻辑、AI 优化和前端 Schema 中移除。
>
> **已有结果数据**：不受影响，旧回测结果 JSON 中可能仍包含这些参数键。

---

## 一、风控规则（Risk Management）— 已归档项

| 参数键 | 中文名 | 类型 | 范围 | 默认值 | 禁用值 | scope | 说明 |
|---|---|---|---|---|---|---|---|
| `take_profit_pct` | 止盈比例（基于本金） | float | [0.0, 1.0] | 0 | 0.0 | unified | 账户权益相对初始本金盈利超过此比例时触发止盈。设为 0 则禁用 |
| `stop_loss_pct` | 止损比例（基于本金） | float | [0.0, 1.0] | 0 | 0.0 | unified | 账户权益相对初始本金亏损超过此比例时触发止损。设为 0 则禁用 |
| `consecutive_loss_threshold` | 连续亏损降仓阈值 | int | [1, 20] | 3 | 20 | unified | 连续亏损次数达到此阈值时触发仓位缩减机制 |
| `loss_position_reduction_pct` | 亏损降仓比例 | float | [0.0, 1.0] | 0.5 | 0.0 | unified | 触发连续亏损阈值后每次入场仓位缩减的比例 |
| `exit_use_orderbook_mode` | 平仓盘口撮合模式 | bool | — | false | — | unified | 开启后通过 orderbook 买方深度按 VWAP 撮合卖出 |
| `exit_min_sell_price` | 退出最低卖出价 | float | [0.0, 1.0] | 0 | 0.0 | unified | 盘口撮合模式下低于此价格的买方挂单不参与撮合。依赖 `exit_use_orderbook_mode` |
| `exit_reduction_pct` | 退出每 tick 减仓比例 | float | [0.01, 1.0] | 1 | 1.0 | unified | 盘口撮合模式下每个 tick 最多减掉剩余仓位的比例。依赖 `exit_use_orderbook_mode` |

---

## 二、入场条件（Entry Conditions）— 已归档项

| 参数键 | 中文名 | 类型 | 范围 | 禁用值 | scope | 说明 |
|---|---|---|---|---|---|---|
| `max_spread` | 最大 Spread 阈值 | float | [0.01, 1.0] | 1.0 | strategy | 入场时 best_ask − best_bid 超过此值则跳过 |
| `max_ask_deviation` | 最大 Ask 偏离度 | float | [0.01, 1.0] | 1.0 | strategy | best_ask 相对锚点价格偏离比例上限 |
| `min_profit_room` | 最小利润空间 | float | [0.0, 0.5] | 0.0 | strategy | 要求 `1.0 − best_ask > 此值` 才入场 |
| `max_entry_count` | 单场买入次数最多 | int | [1, 50] | null | strategy | 单个市场内最多允许的买入次数；选中即启用 |

---

## 三、动量检测（Momentum Detection）— 整组归档

| 参数键 | 中文名 | 类型 | 范围 | 禁用值 | 依赖 | scope | 说明 |
|---|---|---|---|---|---|---|---|
| `momentum_window` | 动量检测窗口 | int | [60, 3600] 秒 | null | — | strategy | 计算入场动量所用的历史价格窗口时长；选中即启用动量检测 |
| `momentum_min` | 最小涨幅 | float | [0.0, 0.1] | 0.0 | `momentum_window` | strategy | 入场所需的最小动量涨幅 |
| `direction_window` | 方向一致性检测窗口 | int | [60, 3600] 秒 | null | — | strategy | 要求窗口内上涨 tick 占比 > 50%；选中即启用 |

---

## 四、波动检测（Volatility Detection）— 整组归档

| 参数键 | 中文名 | 类型 | 范围 | 禁用值 | 依赖 | scope | 说明 |
|---|---|---|---|---|---|---|---|
| `volatility_window` | 波动检测窗口 | int | [60, 3600] 秒 | null | — | strategy | 振幅、标准差、回撤共用的历史窗口；选中即启用波动检测 |
| `amplitude_min` | 振幅下限 | float | [0.0, 5.0] | 0.0 | `volatility_window` | strategy | 入场所需最小价格振幅 |
| `amplitude_max` | 振幅上限 | float | [0.0, 5.0] | 5.0 | `volatility_window` | strategy | 入场允许最大价格振幅 |
| `max_std` | 最大标准差 | float | [0.0, 1.0] | 1.0 | `volatility_window` | strategy | 入场允许最大相对标准差 |
| `max_drawdown` | 窗口最大回撤 | float | [0.0, 1.0] | 1.0 | `volatility_window` | strategy | 入场允许波动窗口内最大回撤比例 |
| `reverse_tick_window` | 反向检测窗口 | int | [5, 300] 秒 | null | — | strategy | 检测近期反向回调的时间窗口；选中即启用反转检测 |
| `reverse_threshold` | 反向波动阈值 | float | [0.0, 0.1] | 0.1 | `reverse_tick_window` | strategy | 反向窗口内价格回调超过此值则放弃入场 |

---

## 参数依赖关系（归档时有效）

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

## 参数分组（归档时有效）

| 组 | 中文名 | 归档状态 |
|---|---|---|
| `risk` | 风控规则 | 部分归档（保留 take_profit_price、stop_loss_price、force_close_remaining_seconds） |
| `entry` | 入场条件 | 部分归档（保留 min_price、time_remaining_ratio） |
| `momentum` | 动量检测 | 整组归档 |
| `volatility` | 波动检测 | 整组归档 |
| `position` | 仓位管理 | 保留（position_min_pct、position_max_pct） |

---

## 归档前的计算逻辑摘要

### 资金比例止盈止损 (`take_profit_pct`, `stop_loss_pct`)

```python
pnl_ratio = (equity - initial_balance) / initial_balance
if pnl_ratio >= take_profit_pct: close_all()
if pnl_ratio <= -stop_loss_pct: close_all()
```

### 连续亏损降仓 (`consecutive_loss_threshold`, `loss_position_reduction_pct`)

```python
if consecutive_losses >= threshold:
    position_scale *= (1.0 - loss_position_reduction_pct)
# 入场时: signal.amount *= position_scale
```

### 盘口撮合退出 (`exit_use_orderbook_mode`, `exit_min_sell_price`, `exit_reduction_pct`)

```python
if exit_use_orderbook_mode:
    amount = qty * exit_reduction_pct
    sell_mode = "orderbook"
    min_sell_price = exit_min_sell_price
else:
    sell_mode = "ideal"
```

### 入场过滤 (`max_spread`, `max_ask_deviation`, `min_profit_room`, `max_entry_count`)

```python
if spread > max_spread: skip
if (best_ask - anchor) / anchor > max_ask_deviation: skip
if (1.0 - best_ask) < min_profit_room: skip
if entry_count >= max_entry_count: skip
```

### 动量检测 (`momentum_window`, `momentum_min`, `direction_window`)

```python
momentum = (price[-1] - price[-window]) / price[-window]
if momentum < momentum_min: skip

up_count = count(price[i] > price[i-1] for i in direction_window)
if up_count <= down_count: skip
```

### 波动检测 (`volatility_window`, `amplitude_*`, `max_std`, `max_drawdown`, `reverse_*`)

```python
amplitude = (high - low) / low
if amplitude < amplitude_min or amplitude > amplitude_max: skip

std_pct = std(prices) / mean(prices)
if std_pct > max_std: skip

max_dd = max(peak_to_trough_ratio in window)
if max_dd > max_drawdown: skip

if any(price_drop > reverse_threshold in reverse_tick_window): skip
```
