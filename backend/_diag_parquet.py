"""Diagnostic: test DuckDB parquet query directly."""
import os, sys
sys.path.insert(0, ".")
from app.config import settings

slug = "btc-updown-5m-1774405800"
fp = os.path.join(settings.data_dir, "archives", slug, "prices.parquet")
print(f"File path: {fp}")
print(f"Exists: {os.path.exists(fp)}")
print(f"Size: {os.path.getsize(fp) if os.path.exists(fp) else 0}")

import duckdb
fp_unix = fp.replace("\\", "/")
sql = "SELECT * FROM read_parquet('" + fp_unix + "') ORDER BY timestamp LIMIT 3"
print(f"SQL: {sql}")

con = duckdb.connect()
try:
    result = con.execute(sql).fetchdf()
    print(f"Success! Rows: {len(result)}")
    print(result.head())
    records = result.to_dict(orient="records")
    print(f"Records count: {len(records)}")
    if records:
        print(f"First record: {records[0]}")
except Exception as e:
    print(f"ERROR: {type(e).__name__}: {e}")
    import traceback
    traceback.print_exc()
finally:
    con.close()

# Also test orderbooks
fp2 = os.path.join(settings.data_dir, "archives", slug, "orderbooks.parquet")
print(f"\nOrderbook file: {fp2}")
print(f"Exists: {os.path.exists(fp2)}")
if os.path.exists(fp2):
    fp2_unix = fp2.replace("\\", "/")
    sql2 = "SELECT * FROM read_parquet('" + fp2_unix + "') ORDER BY timestamp LIMIT 3"
    con2 = duckdb.connect()
    try:
        result2 = con2.execute(sql2).fetchdf()
        print(f"Success! Rows: {len(result2)}")
        print(f"Columns: {list(result2.columns)}")
    except Exception as e:
        print(f"ERROR: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
    finally:
        con2.close()
