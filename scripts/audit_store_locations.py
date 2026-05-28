"""
Audit store_locations table — check coverage per retailer.
Prints: retailer_key, total rows, rows with real GPS (non-centroid), confidence breakdown.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from config.supabase import get_supabase_client

sb = get_supabase_client()

# ── Pull ALL store_locations rows (paginated) ────────────────────────────────
print("Loading store_locations …", flush=True)
rows = []
offset = 0
while True:
    batch = (
        sb.table("store_locations")
        .select("retailer_key, retailer, geocode_confidence, latitude, longitude, state")
        .range(offset, offset + 999)
        .execute()
        .data or []
    )
    rows.extend(batch)
    print(f"  fetched {len(rows)} rows …", flush=True)
    if len(batch) < 1000:
        break
    offset += 1000

print(f"\nTotal rows in store_locations: {len(rows)}\n")

# ── Aggregate per retailer_key ───────────────────────────────────────────────
from collections import defaultdict

# key → {total, real_gps, confidence_counts, states}
stats: dict[str, dict] = defaultdict(lambda: {
    "total": 0, "real_gps": 0,
    "confidence": defaultdict(int),
    "states": set(),
})

for r in rows:
    key = (r.get("retailer_key") or "").strip().lower() or "(blank)"
    s   = stats[key]
    s["total"] += 1
    conf = (r.get("geocode_confidence") or "null").strip()
    s["confidence"][conf] += 1
    if conf not in ("zip_centroid", "zip"):
        if r.get("latitude") is not None and r.get("longitude") is not None:
            s["real_gps"] += 1
    state = (r.get("state") or "").strip()
    if state:
        s["states"].add(state)

# ── Print sorted by retailer_key ─────────────────────────────────────────────
KEY_TARGETS = {
    "walmart", "target", "kroger", "publix",
    "smart_and_final", "smartfinal", "smart_final",
    "ralphs", "vons", "albertsons", "safeway",
    "cvs", "walgreens",
    "sprouts", "sproutsfarmersmarket",
    "food4less", "aldi", "costco", "traderjoes", "trader_joes",
    "wholefoods", "whole_foods", "wholefoodsmarket",
    "hmart", "h_mart",
    "foodmaxx", "stater_bros", "staterbros",
    "meijer", "heb", "wegmans", "shoprite",
    "samsclub", "sam_s_club",
    "familydollar", "family_dollar", "dollartree", "dollar_tree",
    "bristolfarms", "bristol_farms",
    "gelsons", "gelson_s",
    "lazyacres", "lazy_acres",
    "pavilions",
    "northgatemarket", "northgate_market",
    "elsuper", "el_super",
    "superiorgrocer", "superior_grocers",
}

print(f"{'retailer_key':<30} {'total':>7} {'real_gps':>9} {'states':>6}  confidence breakdown")
print("-" * 90)

# Print targeted retailers first
printed = set()
for key in sorted(stats.keys()):
    if key not in KEY_TARGETS:
        continue
    s = stats[key]
    conf_str = " | ".join(f"{c}={n}" for c, n in sorted(s["confidence"].items(), key=lambda x: -x[1]))
    states_n = len(s["states"])
    print(f"{key:<30} {s['total']:>7} {s['real_gps']:>9} {states_n:>6}  {conf_str}")
    printed.add(key)

print("\n── Other retailers ─────────────────────────────────────────────────────────")
for key in sorted(stats.keys()):
    if key in printed:
        continue
    s = stats[key]
    conf_str = " | ".join(f"{c}={n}" for c, n in sorted(s["confidence"].items(), key=lambda x: -x[1]))
    states_n = len(s["states"])
    print(f"{key:<30} {s['total']:>7} {s['real_gps']:>9} {states_n:>6}  {conf_str}")
