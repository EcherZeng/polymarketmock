import asyncio
import httpx
import json

async def test():
    async with httpx.AsyncClient(timeout=15.0) as c:
        r = await c.get("http://localhost:8071/api/resolve/btc-updown-5m-1774341300")
        print(f"status: {r.status_code}")
        d = r.json()
        print(f"event keys: {list(d.keys())}")
        print(f"id={d.get('id')}, title={d.get('title')}")
        print(f"active={d.get('active')}, closed={d.get('closed')}")
        markets = d.get("markets", [])
        print(f"markets count: {len(markets)}")
        if markets:
            m = markets[0]
            print(f"\nmarket keys: {list(m.keys())}")
            print(f"id={m.get('id')}")
            print(f"question={m.get('question')}")
            print(f"clobTokenIds type={type(m.get('clobTokenIds')).__name__}: {m.get('clobTokenIds')}")
            print(f"outcomes type={type(m.get('outcomes')).__name__}: {m.get('outcomes')}")
            print(f"outcomePrices type={type(m.get('outcomePrices')).__name__}: {m.get('outcomePrices')}")
            print(f"active={m.get('active')}, closed={m.get('closed')}")
            print(f"volume24hr={m.get('volume24hr')}")
            print(f"liquidity={m.get('liquidity')}")
            print(f"spread={m.get('spread')}")

asyncio.run(test())
