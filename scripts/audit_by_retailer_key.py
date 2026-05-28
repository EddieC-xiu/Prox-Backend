"""Audit store_locations by retailer_key — find all keys with 0 or low real GPS."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from config.supabase import get_supabase_client
from collections import Counter

sb = get_supabase_client()

def paginate(table, select_cols, page_size=1000):
    rows, offset = [], 0
    while True:
        batch = sb.table(table).select(select_cols).range(offset, offset + page_size - 1).execute().data or []
        rows.extend(batch)
        if len(batch) < page_size:
            break
        offset += page_size
    return rows

print("Loading store_locations...")
sl_rows = paginate("store_locations", "retailer_key, geocode_confidence, latitude, longitude, zip_code")
print(f"Total rows: {len(sl_rows)}\n")

from collections import defaultdict
by_key = defaultdict(list)
for r in sl_rows:
    by_key[r["retailer_key"]].append(r)

null_zip_keys = {}
results = []
for rk, rows in by_key.items():
    total = len(rows)
    real = sum(1 for r in rows if r.get("latitude") is not None and r.get("geocode_confidence") not in ("zip_centroid", "zip"))
    null_zip = sum(1 for r in rows if not r.get("zip_code"))
    if null_zip > 0:
        null_zip_keys[rk] = null_zip
    results.append((rk, total, real, null_zip))

# Sort by real GPS ascending
results.sort(key=lambda x: x[2])

print(f"{'retailer_key':<30} {'total':>7} {'real_gps':>9} {'null_zip':>9}  status")
print("-" * 65)
for rk, total, real, null_zip in results:
    if real == 0:
        status = "NO REAL GPS"
    elif real < 5:
        status = f"LOW ({real})"
    elif real < total * 0.3:
        status = f"{real/total*100:.0f}% coverage"
    else:
        status = ""
    nz = f" nz={null_zip}" if null_zip > 0 else ""
    print(f"{rk:<30} {total:>7} {real:>9} {null_zip:>9}  {status}{nz}")

print(f"\nKeys with null-zip entries (affected by collapse bug): {len(null_zip_keys)}")
for rk, count in sorted(null_zip_keys.items(), key=lambda x: -x[1]):
    print(f"  {rk}: {count} null-zip rows")
