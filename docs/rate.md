> ## Documentation Index
> Fetch the complete documentation index at: https://docs.polymarket.com/llms.txt
> Use this file to discover all available pages before exploring further.

# 速率限制

> 所有 Polymarket 端点的 API 速率限制

所有 API 速率限制通过 Cloudflare 的限流系统执行。当你超过任何端点的限制时，请求会被限流（延迟/排队），而非立即拒绝。限制基于滑动时间窗口重置。

***

## 通用

| 端点          | 限制               |
| ----------- | ---------------- |
| 通用速率限制      | 15,000 req / 10s |
| 健康检查（`/ok`） | 100 req / 10s    |

***

## Gamma API

Base URL: `https://gamma-api.polymarket.com`

| 端点                        | 限制              |
| ------------------------- | --------------- |
| 通用                        | 4,000 req / 10s |
| `/events`                 | 500 req / 10s   |
| `/markets`                | 300 req / 10s   |
| `/markets` + `/events` 列表 | 900 req / 10s   |
| `/comments`               | 200 req / 10s   |
| `/tags`                   | 200 req / 10s   |
| `/public-search`          | 350 req / 10s   |

***

## Data API

Base URL: `https://data-api.polymarket.com`

| 端点                  | 限制              |
| ------------------- | --------------- |
| 通用                  | 1,000 req / 10s |
| `/trades`           | 200 req / 10s   |
| `/positions`        | 150 req / 10s   |
| `/closed-positions` | 150 req / 10s   |
| 健康检查（`/ok`）         | 100 req / 10s   |

***

## CLOB API

Base URL: `https://clob.polymarket.com`

### 通用

| 端点                         | 限制              |
| -------------------------- | --------------- |
| 通用                         | 9,000 req / 10s |
| `GET` balance allowance    | 200 req / 10s   |
| `UPDATE` balance allowance | 50 req / 10s    |

### 市场数据

| 端点                | 限制              |
| ----------------- | --------------- |
| `/book`           | 1,500 req / 10s |
| `/books`          | 500 req / 10s   |
| `/price`          | 1,500 req / 10s |
| `/prices`         | 500 req / 10s   |
| `/midpoint`       | 1,500 req / 10s |
| `/midpoints`      | 500 req / 10s   |
| `/prices-history` | 1,000 req / 10s |
| Market tick size  | 200 req / 10s   |

### 账本

| 端点                                               | 限制            |
| ------------------------------------------------ | ------------- |
| `/trades`, `/orders`, `/notifications`, `/order` | 900 req / 10s |
| `/data/orders`                                   | 500 req / 10s |
| `/data/trades`                                   | 500 req / 10s |
| `/notifications`                                 | 125 req / 10s |

### 身份验证

| 端点         | 限制            |
| ---------- | ------------- |
| API key 端点 | 100 req / 10s |

### 交易

交易端点同时有**突发**限制（允许短期峰值）和**持续**限制（较长期的平均值）。

| 端点                             | 突发限制            | 持续限制                |
| ------------------------------ | --------------- | ------------------- |
| `POST /order`                  | 3,500 req / 10s | 36,000 req / 10 min |
| `DELETE /order`                | 3,000 req / 10s | 30,000 req / 10 min |
| `POST /orders`                 | 1,000 req / 10s | 15,000 req / 10 min |
| `DELETE /orders`               | 1,000 req / 10s | 15,000 req / 10 min |
| `DELETE /cancel-all`           | 250 req / 10s   | 6,000 req / 10 min  |
| `DELETE /cancel-market-orders` | 1,000 req / 10s | 1,500 req / 10 min  |

***

## 其他

| 端点                | 限制             |
| ----------------- | -------------- |
| Relayer `/submit` | 25 req / 1 min |
| User PNL API      | 200 req / 10s  |

***

## 下一步

<CardGroup cols={2}>
  <Card title="身份验证" icon="key" href="/api-reference/authentication">
    了解如何对交易请求进行身份验证。
  </Card>

  <Card title="客户端与 SDK" icon="cube" href="/api-reference/clients-sdks">
    官方 TypeScript、Python 和 Rust 库。
  </Card>
</CardGroup>


Built with [Mintlify](https://mintlify.com).