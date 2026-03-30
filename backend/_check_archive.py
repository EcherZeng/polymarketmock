"""Quick check of archive parquet data."""
import duckdb
import os

sessions_dir = "data/sessions"
archives = [d for d in os.listdir(sessions_dir) if os.path.isdir(os.path.join(sessions_dir, d, "archive"))]
slug = archives[0] if archives else "btc-updown-15m-1774503000"
print("slug:", slug)

for name in ["prices", "orderbooks"]:
    fp = os.path.join("data", "sessions", slug, "archive", f"{name}.parquet").replace("\\", "/")
    if not os.path.exists(fp):
        print(f"{name}: NOT FOUND")
        continue
    con = duckdb.connect()
    r = con.execute(f"SELECT * FROM read_parquet('{fp}') LIMIT 3").fetchdf()
    print(f"\n=== {name} ===")
    print("columns:", r.columns.tolist())
    print(r.to_string())
    con.close()
