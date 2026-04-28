# Poly 测试账号交接简版

## 最重要的一点

这个账号是用 Polymarket 官网的 Google / 邮箱方式注册的钱包。

所以它不是普通 MetaMask 钱包，也不要默认当成 Gnosis Safe。项目里必须按 `POLY_PROXY` 钱包处理：

```dotenv
POLY_SIGNATURE_TYPE=1
```

`.env` 里这几项最关键：

```dotenv
POLY_PRIVATE_KEY=0x...
POLY_FUNDER_ADDRESS=0x...
POLY_SIGNATURE_TYPE=1
POLY_API_KEY=...
POLY_API_SECRET=...
POLY_API_PASSPHRASE=...
```

其中 `POLY_FUNDER_ADDRESS` 要填 Polymarket 页面显示的钱包地址。不要用私钥推出来的 signer 地址替代它。

## 接手后先做什么

1. 把 `.env` 放到项目根目录。
2. 确认 `.env` 里有 `POLY_SIGNATURE_TYPE=1`。
3. 打开前端页面，看 bot 状态、钱包余额、行情和日志。
4. 先用小金额测试，不要一上来扩大金额。—————最小交易10刀，不然有触发止损，金额小于5刀会卖不出去 by 雷


## 千万别改错

- 不要把 `POLY_SIGNATURE_TYPE=1` 改成 `2`，除非明确换成真正的 Safe 钱包。
- 不要把 Google / 邮箱钱包误判成 Safe。
- 不要把 `POLY_FUNDER_ADDRESS` 填成 signer 地址。
- 不要同时开多个会操作同一个钱包的 bot 或测试脚本。
- 不要把 `.env` 提交到 Git。

## 如果 SELL 报错

Google / 邮箱钱包下，allowance 显示可能不完全可靠。SELL 出问题时，优先检查：

1. `.env` 里是不是 `POLY_SIGNATURE_TYPE=1`。
2. `POLY_FUNDER_ADDRESS` 是不是 Polymarket 页面显示的钱包地址。
3. 是否有多个进程同时操作同一个钱包。


只核验授权状态：

```bash
python -m scripts.set_allowances --verify-only
```

## 一句话结论

这个账号按 Google / 邮箱钱包测试账号交接，`.env` 直接给接手程序员即可。对方最需要注意的是：`POLY_SIGNATURE_TYPE=1`、`POLY_FUNDER_ADDRESS` 填页面钱包地址、先小额跑通，不要误当 Safe 钱包。
