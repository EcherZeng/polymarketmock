import httpx, json

# Test timeline
r = httpx.get("http://localhost:8071/api/backtest/replay/btc-updown-5m-1774405800/timeline")
print(f"Status: {r.status_code}")
print(r.text[:500])
