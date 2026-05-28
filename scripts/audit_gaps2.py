"""
Quick targeted audit:
1. Distinct `retailer` values in flyer_deals (first 5000 rows sample is enough — all retailers appear early)
2. For each, check if real GPS exists in store_locations
3. Sample 'unknown' confidence rows for trader_joes/smart_final
4. Detail bristolfarms / gelsons non-centroid rows
"""
import sys, os, re
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from config.supabase import get_supabase_client

sb = get_supabase_client()

# ── 1. Distinct retailers from flyer_deals (sample first 5000) ──────────────
print("Sampling distinct retailers from flyer_deals...", flush=True)
fd_retailers: set[str] = set()
for offset in range(0, 20000, 1000):
    batch = (
        sb.table("flyer_deals")
        .select("retailer")
        .range(offset, offset + 999)
        .execute()
        .data or []
    )
    for r in batch:
        rn = (r.get("retailer") or "").strip()
        if rn:
            fd_retailers.add(rn)
    if len(batch) < 1000:
        break

print(f"Retailers found in first 20k rows: {len(fd_retailers)}")
for r in sorted(fd_retailers):
    print(f"  {r}")

# ── 2. Build store_locations real-GPS key set ────────────────────────────────
print("\nBuilding store_locations real-GPS keys...", flush=True)
# Key by (normalized display name) → bool has_real_gps
from collections import defaultdict
sl_stats: dict[str, dict] = defaultdict(lambda: {"total": 0, "real": 0})

offset = 0
while True:
    batch = (
        sb.table("store_locations")
        .select("retailer_key, retailer, geocode_confidence, latitude, longitude")
        .range(offset, offset + 999)
        .execute()
        .data or []
    )
    for r in batch:
        rn = (r.get("retailer") or "").strip().lower()
        rk = (r.get("retailer_key") or "").strip().lower()
        conf = (r.get("geocode_confidence") or "").strip()
        for key in {rn, rk}:
            if not key:
                continue
            sl_stats[key]["total"] += 1
            if conf not in ("zip_centroid", "zip", "") and r.get("latitude") and r.get("longitude"):
                sl_stats[key]["real"] += 1
    if len(batch) < 1000:
        break
    offset += 1000

print(f"Built {len(sl_stats)} store_locations keys\n")

# ── 3. Gap analysis ──────────────────────────────────────────────────────────
print("=== Coverage check for retailers in flyer_deals ===")
print(f"{'retailer':<35} {'computed_key':<25} {'sl_real':>8} {'sl_total':>9} status")
print("-" * 90)

def normalize_retailer_key(name: str) -> str:
    return re.sub(r"[^a-z0-9]", "", name.lower().strip())

for retailer in sorted(fd_retailers):
    display_key = retailer.lower().strip()
    computed_key = normalize_retailer_key(retailer)

    # Check by display key or computed key
    by_display = sl_stats.get(display_key, {})
    by_computed = sl_stats.get(computed_key, {})

    real = max(by_display.get("real", 0), by_computed.get("real", 0))
    total = max(by_display.get("total", 0), by_computed.get("total", 0))

    if real == 0 and total == 0:
        status = "COMPLETELY MISSING"
    elif real == 0:
        status = "centroid-only"
    elif real < 10:
        status = f"LOW ({real} real)"
    else:
        status = "ok"

    print(f"{retailer:<35} {computed_key:<25} {real:>8} {total:>9} {status}")

# ── 4. Sample 'unknown' confidence rows ─────────────────────────────────────
for key in ("trader_joes", "smart_final"):
    print(f"\n=== Sample 'unknown' conf for {key} ===")
    res = (
        sb.table("store_locations")
        .select("zip_code, city, state, latitude, longitude, store_name, full_address")
        .eq("retailer_key", key)
        .eq("geocode_confidence", "unknown")
        .limit(5)
        .execute()
        .data or []
    )
    for r in res:
        print(f"  zip={r.get('zip_code')} {r.get('city')},{r.get('state')} lat={r.get('latitude')} lng={r.get('longitude')} store={r.get('store_name')}")

# ── 5. bristolfarms / gelsons non-centroid rows ──────────────────────────────
for key in ("bristolfarms", "gelsons"):
    print(f"\n=== {key} non-centroid rows ===")
    res = (
        sb.table("store_locations")
        .select("zip_code, city, state, latitude, longitude, geocode_confidence, store_name, full_address")
        .eq("retailer_key", key)
        .neq("geocode_confidence", "zip_centroid")
        .execute()
        .data or []
    )
    for r in res:
        print(f"  zip={r.get('zip_code')} {r.get('city')},{r.get('state')} lat={r.get('latitude')},{r.get('longitude')} conf={r.get('geocode_confidence')} store={r.get('store_name')}")
