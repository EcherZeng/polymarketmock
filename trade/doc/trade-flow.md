# Trade Service 流程图文档

## 1. 系统总体架构

```mermaid
graph TB
    subgraph External["外部服务"]
        GAMMA["Polymarket Gamma API<br/>(市场发现)"]
        CLOB["Polymarket CLOB API<br/>(下单/撤单)"]
        POLY_WS["Polymarket WebSocket<br/>(订单簿实时推送)"]
        BINANCE["Binance WebSocket<br/>(BTCUSDT 实时价格)"]
        STRATEGY_SVC["Strategy Service :8072<br/>(预设/组合策略)"]
    end

    subgraph TradeService["Trade Service :8073"]
        MAIN["main.py<br/>Uvicorn 入口"]
        APP["api/app.py<br/>FastAPI Lifespan"]

        subgraph Engine["引擎层"]
            SM["SessionManager<br/>双槽会话编排器"]
            SE["StrategyEngine<br/>组合分支选择"]
            BTC_TREND["BtcTrend<br/>双窗口动量过滤"]
        end

        subgraph Market["市场数据层"]
            SCANNER["MarketScanner<br/>市场发现(轮询)"]
            WS_CLIENT["WsClient<br/>Polymarket WS 客户端"]
            OB["OrderbookBuilder<br/>订单簿构建 & 锚定价"]
            BTC_STREAM["BtcPriceStreamer<br/>BTC 价格流"]
        end

        subgraph Strategy["策略层"]
            LIVE_STRAT["Btc15mLiveStrategy<br/>入场/出场信号"]
        end

        subgraph Execution["执行层"]
            FACTORY["ExecutorFactory"]
            REAL_EXEC["OrderExecutor<br/>(真实下单)"]
            MOCK_EXEC["MockExecutor<br/>(模拟下单)"]
        end

        subgraph Portfolio["仓位追踪"]
            POS_TRACK["PositionTracker<br/>余额/持仓/PnL"]
            SETTLE_TRACK["SettlementTracker<br/>结算轮询"]
        end

        subgraph Infra["基础设施"]
            STORE["DataStore<br/>DuckDB 持久化"]
            HUB["LiveHub<br/>WebSocket 广播"]
        end

        subgraph API["API 路由"]
            MONITOR["MonitorRoutes<br/>/health /status /pnl"]
            CONFIG["ConfigRoutes<br/>/config /config/load-preset"]
            CONTROL["ControlRoutes<br/>/pause /resume /executor-mode"]
            WS_HANDLER["WsHandler<br/>/ws/live"]
        end
    end

    subgraph Clients["客户端"]
        FRONTEND["TradeFrontend<br/>实时监控 UI"]
    end

    MAIN --> APP
    APP --> SM
    APP --> SCANNER
    APP --> BTC_STREAM
    APP --> STORE
    APP --> HUB

    SM --> SCANNER
    SM --> SE
    SM --> BTC_TREND
    SM --> LIVE_STRAT
    SM --> FACTORY
    SM --> POS_TRACK
    SM --> SETTLE_TRACK
    SM --> STORE
    SM --> HUB

    SCANNER -->|轮询 120s| GAMMA
    WS_CLIENT -->|订阅 token_ids| POLY_WS
    BTC_STREAM --> BINANCE
    REAL_EXEC --> CLOB
    SETTLE_TRACK -->|轮询 60s| GAMMA
    CONFIG -->|获取预设| STRATEGY_SVC

    FACTORY --> REAL_EXEC
    FACTORY --> MOCK_EXEC

    WS_CLIENT --> OB
    OB --> SM

    HUB --> WS_HANDLER
    WS_HANDLER --> FRONTEND
    MONITOR --> STORE
    MONITOR --> POS_TRACK
```

---

## 2. 启动流程 (Lifespan)

```mermaid
flowchart TD
    START([启动 main.py]) --> UVICORN["启动 Uvicorn 服务器<br/>host:port = 0.0.0.0:8073"]
    UVICORN --> LIFESPAN["进入 FastAPI Lifespan"]

    LIFESPAN --> P0_1["P0-1: 初始化核心服务"]
    P0_1 --> INIT_SCANNER["创建 MarketScanner"]
    P0_1 --> INIT_EXEC["创建 Executor (real/mock)"]
    P0_1 --> INIT_POS["创建 PositionTracker"]
    P0_1 --> INIT_SETTLE["创建 SettlementTracker"]
    P0_1 --> INIT_STORE["创建 DataStore (DuckDB)"]
    P0_1 --> INIT_HUB["创建 LiveHub"]
    P0_1 --> INIT_BTC["创建 BtcPriceStreamer"]

    INIT_SCANNER & INIT_EXEC & INIT_POS & INIT_SETTLE & INIT_STORE & INIT_HUB & INIT_BTC --> P0_2

    P0_2["P0-2: 同步初始余额<br/>(仅 real 模式)"] --> P0_3
    P0_3["P0-3: 从 DuckDB 恢复未结算持仓"] --> P0_4
    P0_4["P0-4: 创建 SessionManager<br/>注入所有依赖"] --> P0_5
    P0_5["P0-5: 验证 SELL 授权<br/>(仅 real 模式)"] --> ROUTES
    ROUTES["挂载路由 & WS 端点"] --> RUN["启动 SessionManager<br/>& 所有异步任务"]
    RUN --> READY([服务就绪])

    style START fill:#4CAF50,color:#fff
    style READY fill:#4CAF50,color:#fff
```

---

## 3. 会话管理主循环 (SessionManager)

```mermaid
flowchart TD
    TICK([主循环 1s Tick]) --> RECORD["A. 记录价格<br/>BTC → btc_history<br/>Token → poly_price_history"]

    RECORD --> DISCOVER["B. 发现会话<br/>current = scanner.get_current_or_next()<br/>next = scanner.get_next_after()"]

    DISCOVER --> PREPARE{"C. next 距开始<br/>< 60s ?"}
    PREPARE -->|是| WS_SUB["WS 预订阅<br/>next.token_ids"]
    PREPARE -->|否| ACTIVATE
    WS_SUB --> ACTIVATE

    ACTIVATE{"D. now >= current<br/>.start_epoch ?"}
    ACTIVATE -->|是, 且 state=PENDING| DO_ACTIVATE["激活会话<br/>创建策略实例<br/>on_session_start()<br/>state → ACTIVE"]
    ACTIVATE -->|否 或 已激活| HANDLE

    DO_ACTIVATE --> HANDLE

    HANDLE{"E. state == ACTIVE ?"}
    HANDLE -->|否| EXPIRE_CHECK
    HANDLE -->|是| TREND_CHECK

    TREND_CHECK{"已过 window_2<br/>且未计算趋势?"}
    TREND_CHECK -->|是| BTC_TREND["计算 BTC 趋势<br/>a1, a2, amplitude, direction"]
    TREND_CHECK -->|否| MARKET_UPDATE
    BTC_TREND --> BRANCH_SELECT["选择组合分支<br/>(按 amplitude 匹配)"]
    BRANCH_SELECT --> REINIT["重新初始化策略<br/>on_session_start(branch_config)<br/>on_btc_trend_result()"]
    REINIT --> MARKET_UPDATE

    MARKET_UPDATE["策略评估<br/>on_market_update(ctx)"] --> ENTRY{"有入场信号?"}
    ENTRY -->|是| EXEC_ENTRY["执行 BUY 信号"]
    ENTRY -->|否| EXIT_CHECK

    EXEC_ENTRY --> EXIT_CHECK
    EXIT_CHECK["should_close(ctx)"] --> EXIT{"有出场信号?"}
    EXIT -->|是| EXEC_EXIT["执行 SELL 信号<br/>(TP / SL / 强平)"]
    EXIT -->|否| BROADCAST

    EXEC_EXIT --> BROADCAST
    BROADCAST["广播 market snapshot<br/>至 WebSocket 客户端"] --> EXPIRE_CHECK

    EXPIRE_CHECK{"F. now >= current<br/>.end_epoch ?"}
    EXPIRE_CHECK -->|是| EXPIRE["到期处理<br/>尝试最后平仓<br/>state → SETTLING<br/>入结算队列<br/>next → current"]
    EXPIRE_CHECK -->|否| SETTLE_BG

    EXPIRE --> SETTLE_BG

    SETTLE_BG["G. 后台结算处理<br/>(轮询 Gamma 每 60s)"] --> TICK

    style TICK fill:#2196F3,color:#fff
```

---

## 4. 会话状态机

```mermaid
stateDiagram-v2
    [*] --> PENDING : Scanner 发现市场

    PENDING --> ACTIVE : now >= start_epoch<br/>创建策略 & WS 订阅

    ACTIVE --> SETTLING : now >= end_epoch<br/>尝试最终平仓

    SETTLING --> SETTLED : Gamma 确认结算<br/>计算最终 PnL

    SETTLING --> SETTLED : 超时(600s)<br/>标记错误

    SETTLED --> [*] : 持久化 & 清理

    note right of PENDING
        - Scanner 轮询发现
        - 开始前 60s 预订阅 WS
    end note

    note right of ACTIVE
        - BTC 趋势过滤
        - 组合分支选择
        - 入场/出场信号评估
        - 实时价格记录
    end note

    note right of SETTLING
        - 轮询 Gamma 每 60s
        - 最长等待 600s
    end note

    note right of SETTLED
        - 结算 PnL 写入 DuckDB
        - WS 取消订阅旧 token
    end note
```

---

## 5. BTC 双窗口趋势过滤

```mermaid
flowchart LR
    subgraph 时间线["15 分钟会话时间线"]
        T0["T0<br/>会话开始<br/>P0 = BTC open"]
        TW1["T0 + window_1<br/>Pw1 = BTC open"]
        TW2["T0 + window_2<br/>Pw2 = BTC open"]
        TEND["T0 + 900s<br/>会话结束"]
    end

    T0 --> TW1 --> TW2 --> TEND

    TW2 --> CALC["计算动量<br/>a1 = (Pw1 - P0) / P0<br/>a2 = (Pw2 - Pw1) / Pw1"]

    CALC --> CHECK{"abs(a1+a2) > min_momentum<br/>AND a1 × a2 > 0 ?"}

    CHECK -->|通过| PASS["✅ 趋势通过<br/>direction = UP/DOWN<br/>amplitude = abs(a1+a2)"]
    CHECK -->|未通过| FAIL["❌ 趋势未通过<br/>跳过本会话"]

    PASS --> BRANCH["匹配组合分支<br/>(按 amplitude 降序)"]
    BRANCH --> TRADE["开始交易"]

    style PASS fill:#4CAF50,color:#fff
    style FAIL fill:#f44336,color:#fff
```

---

## 6. 组合策略分支选择 (Composite Config)

```mermaid
flowchart TD
    AMP["BTC 趋势 amplitude"] --> B1{"amplitude >= 0.02<br/>(High Vol) ?"}
    B1 -->|是| HIGH["使用 High Vol 配置<br/>激进参数"]
    B1 -->|否| B2{"amplitude >= 0.01<br/>(Medium Vol) ?"}
    B2 -->|是| MED["使用 Medium Vol 配置<br/>标准参数"]
    B2 -->|否| B3{"amplitude >= 0.0<br/>(Low Vol) ?"}
    B3 -->|是| LOW["使用 Low Vol 配置<br/>保守参数"]
    B3 -->|否| SKIP["无匹配分支<br/>跳过会话"]

    HIGH & MED & LOW --> INIT["重新初始化策略<br/>strategy.on_session_start(branch_config)"]

    style HIGH fill:#FF9800,color:#fff
    style MED fill:#2196F3,color:#fff
    style LOW fill:#9E9E9E,color:#fff
    style SKIP fill:#f44336,color:#fff
```

---

## 7. 策略入场/出场逻辑 (Btc15mLiveStrategy)

```mermaid
flowchart TD
    subgraph Entry["入场逻辑 on_market_update()"]
        E1{"已有持仓?"}
        E1 -->|是| NO_ENTRY["不入场"]
        E1 -->|否| E2{"BTC 趋势通过?"}
        E2 -->|否| NO_ENTRY
        E2 -->|是| E3["选择偏好方向<br/>trend.direction → UP/DOWN"]
        E3 --> E4{"mid_price >= min_price ?"}
        E4 -->|否| NO_ENTRY
        E4 -->|是| E5{"entry_ask 有深度<br/>且 TP 空间足够?"}
        E5 -->|否| NO_ENTRY
        E5 -->|是| SIGNAL["生成 BUY 信号<br/>LiveSignal(side=BUY)"]
    end

    subgraph Exit["出场逻辑 should_close()"]
        X0{"有持仓?"}
        X0 -->|否| NO_EXIT["不出场"]
        X0 -->|是| X1{"effective_price<br/>>= take_profit_price ?"}
        X1 -->|是| TP["✅ 止盈<br/>reason=take_profit"]
        X1 -->|否| X2{"effective_price<br/><= stop_loss_price ?"}
        X2 -->|是| SL["🛑 止损<br/>reason=stop_loss"]
        X2 -->|否| X3{"remaining_time<br/><= force_close_s<br/>AND profit >= min_close_profit ?"}
        X3 -->|是| FC["⏰ 强制平仓<br/>reason=force_close"]
        X3 -->|否| HOLD["继续持有"]
    end

    SIGNAL --> EXEC["执行下单"]
    TP & SL & FC --> SELL["执行 SELL 信号"]

    style TP fill:#4CAF50,color:#fff
    style SL fill:#f44336,color:#fff
    style FC fill:#FF9800,color:#fff
```

---

## 8. 订单执行流程

```mermaid
flowchart TD
    SIG["接收 LiveSignal"] --> MODE{"Executor 模式?"}

    MODE -->|real| REAL_START["创建签名订单<br/>create_order(OrderArgs)"]
    REAL_START --> POST["提交 CLOB<br/>post_order(GTC)"]
    POST --> POLL["轮询成交状态<br/>(每 2s)"]
    POLL --> TIMEOUT{"超时 30s ?"}
    TIMEOUT -->|否| FILLED{"已成交?"}
    FILLED -->|否| POLL
    FILLED -->|是| FILL_OK["返回 LiveFill"]
    TIMEOUT -->|是| CANCEL["取消订单"]
    CANCEL --> PARTIAL{"部分成交?"}
    PARTIAL -->|是| FILL_OK
    PARTIAL -->|否| RETRY{"重试次数<br/>< max_retries ?"}
    RETRY -->|是| REAL_START
    RETRY -->|否| FAIL["下单失败"]

    MODE -->|mock| MOCK_START["验证余额"]
    MOCK_START --> MOCK_LAT["模拟延迟 200ms"]
    MOCK_LAT --> MOCK_FILL["返回模拟 LiveFill"]

    FILL_OK & MOCK_FILL --> APPLY["应用成交<br/>tracker.apply_fill()"]
    APPLY --> SAVE["持久化<br/>store.save_trade()"]
    SAVE --> NOTIFY["策略通知<br/>strategy.on_fill()"]
    NOTIFY --> BROADCAST["WebSocket 广播<br/>hub.broadcast('trade')"]

    style FILL_OK fill:#4CAF50,color:#fff
    style MOCK_FILL fill:#4CAF50,color:#fff
    style FAIL fill:#f44336,color:#fff
```

---

## 9. 结算流程

```mermaid
flowchart TD
    EXPIRE["会话到期<br/>state → SETTLING"] --> QUEUE["加入结算队列"]
    QUEUE --> POLL["轮询 Gamma API<br/>(每 60s)"]
    POLL --> RESOLVED{"market.resolved<br/>== true ?"}
    RESOLVED -->|否| TIMEOUT{"已超过<br/>600s ?"}
    TIMEOUT -->|否| POLL
    TIMEOUT -->|是| ERR["标记结算超时<br/>state → SETTLED (error)"]

    RESOLVED -->|是| WINNER["获取获胜结果<br/>winning_token_id"]
    WINNER --> APPLY_WIN{"持仓 token<br/>== winning ?"}
    APPLY_WIN -->|是| WIN["获胜: value = $1 × shares<br/>settlement_pnl = value - cost"]
    APPLY_WIN -->|否| LOSE["失败: value = $0<br/>settlement_pnl = -cost"]

    WIN & LOSE --> SETTLE_DB["持久化结算结果<br/>store.settle_session()"]
    SETTLE_DB --> UPDATE_BAL["更新余额<br/>tracker.apply_settlement()"]
    UPDATE_BAL --> UNSUB["WS 取消订阅旧 token"]
    UNSUB --> DONE["state → SETTLED"]
    ERR --> DONE

    style WIN fill:#4CAF50,color:#fff
    style LOSE fill:#f44336,color:#fff
    style ERR fill:#FF9800,color:#fff
```

---

## 10. 实时数据流 (WebSocket)

```mermaid
flowchart LR
    subgraph 数据源
        BIN_WS["Binance WS<br/>btcusdt@aggTrade"]
        POLY_WS2["Polymarket WS<br/>book/price_change<br/>last_trade_price<br/>best_bid_ask"]
    end

    subgraph Trade服务
        BTC_S["BtcPriceStreamer<br/>1s 节流"]
        WS_C["WsClient<br/>事件路由"]
        OB2["OrderbookBuilder<br/>维护买卖盘"]
        SM2["SessionManager<br/>记录历史"]
        HUB2["LiveHub<br/>广播中心"]
    end

    subgraph 前端
        UI["TradeFrontend<br/>/ws/live"]
    end

    BIN_WS --> BTC_S --> SM2
    POLY_WS2 --> WS_C --> OB2 --> SM2
    SM2 -->|session| HUB2
    SM2 -->|market| HUB2
    SM2 -->|trade| HUB2
    SM2 -->|btc_history| HUB2
    SM2 -->|poly_price_history| HUB2
    HUB2 --> UI
```

---

## 11. API 路由总览

```mermaid
graph LR
    subgraph Monitor["监控路由"]
        GET_H["GET /health"]
        GET_S["GET /status"]
        GET_P["GET /positions"]
        GET_B["GET /balance"]
        GET_PNL["GET /pnl"]
        GET_SESS["GET /sessions"]
        GET_SESS_D["GET /sessions/{slug}"]
        GET_T["GET /trades"]
        GET_SNAP["GET /price-snapshots/{slug}"]
        GET_BTC["GET /btc-price"]
    end

    subgraph Config["配置路由"]
        GET_CAT["GET /config/catalog"]
        GET_STATE["GET /config/state"]
        PUT_CFG["PUT /config"]
        POST_PRESET["POST /config/load-preset"]
        POST_COMP["POST /config/load-composite"]
    end

    subgraph Control["控制路由"]
        POST_PAUSE["POST /pause"]
        POST_RESUME["POST /resume"]
        GET_EXEC["GET /executor-mode"]
        PUT_EXEC["PUT /executor-mode"]
    end

    subgraph WS["WebSocket"]
        WS_LIVE["WS /ws/live"]
    end

    GET_H & GET_S & GET_P & GET_B & GET_PNL --> STORE2["DataStore / Tracker"]
    PUT_CFG & POST_PRESET & POST_COMP --> SM3["SessionManager"]
    POST_PAUSE & POST_RESUME & PUT_EXEC --> SM3
    WS_LIVE --> HUB3["LiveHub"]
```

---

## 12. 锚定价格计算 (Tiered Anchor Price)

```mermaid
flowchart TD
    INPUT["当前订单簿<br/>bids[], asks[]"] --> SPREAD{"计算 spread<br/>= best_ask - best_bid"}

    SPREAD --> TIGHT{"spread < 5% ?"}
    TIGHT -->|是| MID["锚定价 = mid price<br/>(best_bid + best_ask) / 2"]

    TIGHT -->|否| MEDIUM{"spread < 15% ?"}
    MEDIUM -->|是| MICRO["锚定价 = micro price<br/>深度加权平均<br/>(top 3 levels)"]

    MEDIUM -->|否| WIDE["宽价差"]
    WIDE --> HAS_LAST{"有最近成交价?"}
    HAS_LAST -->|是| LAST["锚定价 = last trade price"]
    HAS_LAST -->|否| FALLBACK["锚定价 = micro price"]

    style MID fill:#4CAF50,color:#fff
    style MICRO fill:#2196F3,color:#fff
    style LAST fill:#FF9800,color:#fff
    style FALLBACK fill:#9E9E9E,color:#fff
```

---

## 13. 文件模块依赖关系

```mermaid
graph TD
    main["main.py"] --> app["api/app.py"]

    app --> sm["engine/session_manager.py"]
    app --> scanner["market/market_scanner.py"]
    app --> btc_stream["market/btc_price.py"]
    app --> store["infra/data_store.py"]
    app --> hub["infra/live_hub.py"]
    app --> exec_factory["execution/executor_factory.py"]
    app --> pos_tracker["portfolio/position_tracker.py"]
    app --> settle_tracker["portfolio/settlement_tracker.py"]

    sm --> se["engine/strategy_engine.py"]
    sm --> btc_trend["engine/btc_trend.py"]
    sm --> ws_client["market/ws_client.py"]
    sm --> ob["market/orderbook_builder.py"]
    sm --> strat["strategies/btc_15m_live.py"]
    sm --> types["models/types.py"]

    exec_factory --> real_exec["execution/order_executor.py"]
    exec_factory --> mock_exec["execution/mock_executor.py"]
    real_exec --> base_exec["execution/base_executor.py"]
    mock_exec --> base_exec

    app --> monitor["api/monitor_routes.py"]
    app --> config_rt["api/config_routes.py"]
    app --> control["api/control_routes.py"]
    app --> ws_handler["api/ws_handler.py"]
    app --> auth["api/auth.py"]

    config_rt --> se
    ws_handler --> hub

    style main fill:#FF9800,color:#fff
    style sm fill:#2196F3,color:#fff
    style strat fill:#4CAF50,color:#fff
```

---

## 14. 关键配置参数

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `TRADE_EXECUTOR_MODE` | `mock` | 执行模式: real / mock |
| `TRADE_SCAN_INTERVAL_S` | `120` | 市场扫描间隔 (秒) |
| `TRADE_SCAN_SLUG_PREFIX` | `btc-updown-15m` | 市场 slug 前缀 |
| `TRADE_SCAN_DURATION_S` | `900` | 会话时长 (15 分钟) |
| `TRADE_SESSION_PREPARE_AHEAD_S` | `60` | 提前预订阅 WS (秒) |
| `TRADE_MIN_TRADE_USDC` | `10.0` | 最小下单金额 (USDC) |
| `TRADE_ORDER_TIMEOUT_S` | `30` | 下单超时 (秒) |
| `TRADE_ORDER_MAX_RETRIES` | `3` | 下单最大重试次数 |
| `TRADE_SETTLEMENT_POLL_INTERVAL_S` | `60` | 结算轮询间隔 (秒) |
| `TRADE_SETTLEMENT_POLL_MAX_S` | `600` | 结算最长等待 (秒) |

---

## 15. 数据持久化 (DuckDB Schema)

```mermaid
erDiagram
    sessions {
        string slug PK "btc-updown-15m-XXXX"
        string token_ids "JSON array"
        string outcomes "JSON array"
        int start_epoch
        int end_epoch
        int duration_s
        string state "PENDING|ACTIVE|SETTLING|SETTLED"
        float trade_pnl
        float settlement_pnl
        float total_pnl
        string settlement_outcome
        string error
        datetime created_at
        datetime updated_at
    }

    trades {
        int id PK "auto-increment"
        string order_id
        string session_slug FK
        string token_id
        string side "BUY|SELL"
        float filled_shares
        float avg_price
        float total_cost
        float fees
        datetime timestamp
        datetime created_at
    }

    sessions ||--o{ trades : "1:N"
```
