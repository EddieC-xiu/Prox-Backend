"""
Find retailers in flyer_deals that have no real GPS in store_locations.
Also check 'unknown' confidence rows for trader_joes and smart_final.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from config.supabase import get_supabase_client

sb = get_supabase_client()

# ── 1. Retailer keys in flyer_deals ─────────────────────────────────────────
print("=== Retailer keys in flyer_deals ===")
res = sb.rpc("", {}).execute() if False else None  # placeholder

# Manual paginated pull
from collections import defaultdict

print("Fetching flyer_deals retailer/zip sample...", flush=True)
fd_retailer_keys: set[str] = set()
offset = 0
while True:
    batch = (
        sb.table("flyer_deals")
        .select("retailer_key, retailer")
        .range(offset, offset + 999)
        .execute()
        .data or []
    )
    for r in batch:
        rk = (r.get("retailer_key") or "").strip().lower()
        if rk:
            fd_retailer_keys.add(rk)
    print(f"  {offset + len(batch)} rows scanned, {len(fd_retailer_keys)} distinct keys...", flush=True)
    if len(batch) < 1000:
        break
    offset += 1000

print(f"\nDistinct retailer_keys in flyer_deals: {len(fd_retailer_keys)}")

# ── 2. Retailer keys in store_locations (with real GPS) ──────────────────────
print("\nFetching store_locations real-GPS retailer keys...", flush=True)
sl_real: set[str] = set()
sl_any: set[str] = set()
offset = 0
while True:
    batch = (
        sb.table("store_locations")
        .select("retailer_key, geocode_confidence, latitude, longitude")
        .range(offset, offset + 999)
        .execute()
        .data or []
    )
    for r in batch:
        rk = (r.get("retailer_key") or "").strip().lower()
        if not rk:
            continue
        sl_any.add(rk)
        conf = (r.get("geocode_confidence") or "").strip()
        if conf not in ("zip_centroid", "zip", "") and r.get("latitude") and r.get("longitude"):
            sl_real.add(rk)
    if len(batch) < 1000:
        break
    offset += 1000

# ── 3. Gap analysis ──────────────────────────────────────────────────────────
print("\n=== Retailers in flyer_deals with NO real GPS in store_locations ===")
missing_real = sorted(fd_retailer_keys - sl_real)
for rk in missing_real:
    in_any = "centroid-only" if rk in sl_any else "COMPLETELY MISSING"
    print(f"  {rk:<35} {in_any}")

print(f"\nTotal missing real GPS: {len(missing_real)}")

# ── 4. Sample 'unknown' confidence rows for trader_joes/smart_final ──────────
for key in ("trader_joes", "smart_final"):
    print(f"\n=== Sample 'unknown' confidence rows for {key} ===")
    res = (
        sb.table("store_locations")
        .select("id, retailer_key, retailer, store_name, zip_code, city, state, latitude, longitude, geocode_confidence, full_address")
        .eq("retailer_key", key)
        .eq("geocode_confidence", "unknown")
        .limit(5)
        .execute()
        .data or []
    )
    for r in res:
        print(f"  zip={r.get('zip_code')} state={r.get('state')} lat={r.get('latitude')} lng={r.get('longitude')} store={r.get('store_name')} addr={r.get('full_address')}")

# ── 5. bristolfarms and gelsons detail ───────────────────────────────────────
for key in ("bristolfarms", "gelsons"):
    print(f"\n=== {key} non-centroid rows ===")
    res = (
        sb.table("store_locations")
        .select("id, retailer_key, retailer, store_name, zip_code, city, state, latitude, longitude, geocode_confidence, full_address")
        .eq("retailer_key", key)
        .neq("geocode_confidence", "zip_centroid")
        .execute()
        .data or []
    )
    for r in res:
        print(f"  zip={r.get('zip_code')} state={r.get('state')} lat={r.get('latitude'):.5f},{r.get('longitude'):.5f} conf={r.get('geocode_confidence')} store={r.get('store_name')}")
