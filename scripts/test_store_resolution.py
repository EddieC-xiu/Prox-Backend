"""
Test: does _get_store_info correctly resolve a store near LA (90046) for each major retailer?
Also checks retailer column values for smart_final / trader_joes keys.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

# Load the service
from services.cross_retailer_service import _load_store_locations, _get_store_info

LA_LAT = 34.0901
LA_LNG = -118.3617

print("Loading store_locations cache...", flush=True)
store_locs = _load_store_locations()
print(f"Cache size: {len(store_locs)} entries\n")

RETAILERS = [
    "Walmart",
    "Target",
    "Kroger",
    "Publix",
    "Smart & Final",
    "Ralphs",
    "CVS",
    "Walgreens",
    "Albertsons",
    "Safeway",
    "Vons",
    "Sprouts",
    "ALDI",
    "Costco",
    "Trader Joe's",
    "Whole Foods Market",
    "H Mart",
    "Food4Less",
    "Dollar Tree",
    "Family Dollar",
    "Sam's Club",
    "BJ's Wholesale Club",
    "Pavilions",
    "Gelson's",
    "Bristol Farms",
    "Lazy Acres",
    "Stater Bros.",
    "El Super",
    "Northgate Market",
    "Superior Grocers",
    "Wegmans",
    "Meijer",
    "H-E-B",
    "ShopRite",
    "Stop & Shop",
    "Food Lion",
    "Winn-Dixie",
    "Hy-Vee",
    "Food Bazaar",
    "99 Ranch Market",
    "Key Food",
    "Western Beef",
]

print(f"{'retailer':<30} {'status':<12} {'dist_mi':>8} {'lat':>10} {'lng':>11} {'addr'}")
print("-" * 100)

import math

def haversine(lat1, lon1, lat2, lon2):
    R = 3958.8
    lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])
    dlat, dlon = lat2 - lat1, lon2 - lon1
    a = math.sin(dlat/2)**2 + math.cos(lat1)*math.cos(lat2)*math.sin(dlon/2)**2
    return R * 2 * math.asin(math.sqrt(a))

for retailer in RETAILERS:
    info = _get_store_info(retailer, "90046", store_locs, user_lat=LA_LAT, user_lng=LA_LNG)
    if info:
        dist = haversine(LA_LAT, LA_LNG, info["lat"], info["lng"])
        addr = (info.get("address") or "")[:50]
        store = (info.get("store_name") or "")[:20]
        print(f"{retailer:<30} {'FOUND':<12} {dist:>8.1f} {info['lat']:>10.4f} {info['lng']:>11.4f}  {store}  {addr}")
    else:
        print(f"{retailer:<30} {'NO RESULT':<12}")

# ── Check what retailer column says for smart_final / trader_joes rows ─────
print("\n=== retailer column values for smart_final / trader_joes ===")
from config.supabase import get_supabase_client
sb = get_supabase_client()
for key in ("smart_final", "trader_joes"):
    res = sb.table("store_locations").select("retailer_key, retailer, geocode_confidence, zip_code").eq("retailer_key", key).limit(5).execute().data or []
    for r in res:
        print(f"  retailer_key={r['retailer_key']} retailer={repr(r['retailer'])} conf={r.get('geocode_confidence')} zip={r.get('zip_code')}")

# ── Check the collapse issue: how many trader_joes entries in cache? ─────────
print("\n=== trader_joes / traderjoes cache entries count ===")
tj_keys_0 = [(k,v) for k,v in store_locs.items() if k[0] in ("traderjoes", "trader joe's", "trader joes", "trader_joes")]
print(f"  traderjoes / trader joe's entries: {len(tj_keys_0)}")
tj_keys_1 = [(k,v) for k,v in store_locs.items() if k[0] == "traderjoes"]
print(f"  traderjoes only: {len(tj_keys_1)}")
