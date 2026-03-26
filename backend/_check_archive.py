"""Quick check of archive parquet data."""
import duckdb
import os

archives = os.listdir("data/archives")
slug = "btc-updown-15m-1774503000"
print("slug:", slug)

for name in ["prices", "orderbooks"]:
    fp = os.path.join("data", "archives", slug, f"{name}.parquet").replace("\\", "/")
    if not os.path.exists(fp):
        print(f"{name}: NOT FOUND")
        continue
    con = duckdb.connect()
    r = con.execute(f"SELECT * FROM read_parquet('{fp}') LIMIT 3").fetchdf()
    print(f"\n=== {name} ===")
    print("columns:", r.columns.tolist())
    print(r.to_string())
    con.close()
