"""Audit: all distinct retailers in flyer_deals vs store_locations GPS coverage."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from config.supabase import get_supabase_client
from collections import Counter

sb = get_supabase_client()

def paginate(table, select_cols, page_size=1000):
    rows = []
    offset = 0
    while True:
        batch = sb.table(table).select(select_cols).range(offset, offset + page_size - 1).execute().data or []
        rows.extend(batch)
        if len(batch) < page_size:
            break
        offset += page_size
    return rows

print("Loading flyer_deals retailers (paginating)...")
rows = paginate("test_flyer_deals_duplicate", "retailer")
retailer_counts = Counter()
for r in rows:
    retailer_counts[r.get("retailer") or "__none__"] += 1

print(f"Total flyer_deals rows: {len(rows)}")
print(f"Distinct retailers: {len(retailer_counts)}\n")

print("Loading store_locations (paginating)...")
sl_rows = paginate("store_locations", "retailer_key, retailer, geocode_confidence, latitude")
sl_total_rk = Counter()
sl_real_rk = Counter()
sl_total_disp = Counter()
sl_real_disp = Counter()
for r in sl_rows:
    rk = r.get("retailer_key") or "__none__"
    disp = (r.get("retailer") or "").lower().strip()
    is_real = r.get("latitude") is not None and r.get("geocode_confidence") not in ("zip_centroid", "zip")
    sl_total_rk[rk] += 1
    sl_real_rk[rk] += int(is_real)
    sl_total_disp[disp] += 1
    sl_real_disp[disp] += int(is_real)

print(f"Total store_locations rows: {len(sl_rows)}\n")
print(f"{'retailer (flyer_deals)':<32} {'deals':>6}  {'sl_total':>8}  {'real_gps':>8}  status")
print("-" * 72)

for retailer, deal_count in sorted(retailer_counts.items(), key=lambda x: -x[1]):
    disp_key = retailer.lower().strip()
    total = sl_total_disp.get(disp_key, 0)
    real = sl_real_disp.get(disp_key, 0)
    status = ""
    if real == 0:
        status = "NO GPS"
    elif real < 5:
        status = f"LOW ({real})"
    elif total > 0 and real < total * 0.5:
        status = f"{real/total*100:.0f}% coverage"
    print(f"{retailer:<32} {deal_count:>6}  {total:>8}  {real:>8}  {status}")
