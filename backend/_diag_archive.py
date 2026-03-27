"""Diagnose archived data completeness."""
from __future__ import annotations
import duckdb
import os

archive = "data/archives/btc-updown-5m-1774600500"

for name in ["prices", "orderbooks", "live_trades", "ob_deltas"]:
    fp = os.path.join(archive, f"{name}.parquet").replace("\\", "/")
    if not os.path.exists(fp):
        print(f"{name}: FILE NOT FOUND")
        continue
    con = duckdb.connect()
    # Overall range
    r = con.execute(f"SELECT COUNT(*) as cnt, MIN(timestamp) as mn, MAX(timestamp) as mx FROM read_parquet('{fp}')").fetchdf().to_dict(orient="records")[0]
    print(f"\n{name}: count={r['cnt']}, min={r['mn']}, max={r['mx']}")

    # Per-minute distribution
    dist = con.execute(f"""
        SELECT date_trunc('minute', timestamp) as minute, COUNT(*) as cnt
        FROM read_parquet('{fp}')
        GROUP BY 1 ORDER BY 1
    """).fetchdf()
    for _, row in dist.iterrows():
        print(f"  {row['minute']}  count={row['cnt']}")

    con.close()
