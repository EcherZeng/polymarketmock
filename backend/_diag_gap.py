"""Check precise data cutoff and gaps around 16:36."""
from __future__ import annotations
import duckdb
import os

archive = "data/archives/btc-updown-5m-1774600500"

print("=" * 80)
print("LIVE TRADES around 16:36")
print("=" * 80)
fp = os.path.join(archive, "live_trades.parquet").replace("\\", "/")
con = duckdb.connect()
# Last 10 trades before gap
rows = con.execute(f"""
    SELECT timestamp, token_id, side, price, size
    FROM read_parquet('{fp}')
    WHERE timestamp >= '2026-03-27T16:35:55+08:00' AND timestamp <= '2026-03-27T16:36:30+08:00'
    ORDER BY timestamp
""").fetchdf()
print(f"Trades between 16:35:55 and 16:36:30: {len(rows)} rows")
for _, r in rows.iterrows():
    print(f"  {r['timestamp']}  side={r['side']} price={r['price']:.4f} size={r['size']:.2f}")

# First 5 trades after gap
rows2 = con.execute(f"""
    SELECT timestamp, token_id, side, price, size
    FROM read_parquet('{fp}')
    WHERE timestamp >= '2026-03-27T16:39:00+08:00'
    ORDER BY timestamp
    LIMIT 10
""").fetchdf()
print(f"\nFirst 10 trades after 16:39:00:")
for _, r in rows2.iterrows():
    print(f"  {r['timestamp']}  side={r['side']} price={r['price']:.4f} size={r['size']:.2f}")

con.close()

print("\n" + "=" * 80)
print("OB_DELTAS around the gap boundary")
print("=" * 80)
fp2 = os.path.join(archive, "ob_deltas.parquet").replace("\\", "/")
con = duckdb.connect()
# Per-second distribution around 16:36
dist = con.execute(f"""
    SELECT date_trunc('second', timestamp) as sec, COUNT(*) as cnt
    FROM read_parquet('{fp2}')
    WHERE timestamp >= '2026-03-27T16:36:00+08:00' AND timestamp <= '2026-03-27T16:36:30+08:00'
    GROUP BY 1 ORDER BY 1
""").fetchdf()
print("ob_deltas per second 16:36:00-16:36:30:")
for _, r in dist.iterrows():
    print(f"  {r['sec']}  count={r['cnt']}")

# Last delta before gap
last = con.execute(f"""
    SELECT MAX(timestamp) as last_ts
    FROM read_parquet('{fp2}')
    WHERE timestamp < '2026-03-27T16:39:00+08:00'
""").fetchdf().to_dict(orient="records")[0]
print(f"\nLast ob_delta before gap: {last['last_ts']}")

# First delta after gap
first = con.execute(f"""
    SELECT MIN(timestamp) as first_ts
    FROM read_parquet('{fp2}')
    WHERE timestamp >= '2026-03-27T16:39:00+08:00'
""").fetchdf().to_dict(orient="records")[0]
print(f"First ob_delta after gap: {first['first_ts']}")

con.close()

print("\n" + "=" * 80)
print("ORDERBOOK snapshots around the gap boundary")
print("=" * 80)
fp3 = os.path.join(archive, "orderbooks.parquet").replace("\\", "/")
con = duckdb.connect()
dist = con.execute(f"""
    SELECT timestamp, token_id
    FROM read_parquet('{fp3}')
    WHERE timestamp >= '2026-03-27T16:36:00+08:00'
    ORDER BY timestamp
    LIMIT 20
""").fetchdf()
print("Orderbook snapshots from 16:36 onwards:")
for _, r in dist.iterrows():
    print(f"  {r['timestamp']}  token={str(r['token_id'])[:12]}...")
con.close()
