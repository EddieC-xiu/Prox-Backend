"""Quick test: what does Kroger resolve to near LA now?"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from services.cross_retailer_service import _load_store_locations, _get_store_info
import math

LA_LAT, LA_LNG = 34.0901, -118.3617

print("Loading fresh cache...")
store_locs = _load_store_locations()

def dist(a, b, c, d):
    R = 3958.8
    a,b,c,d = map(math.radians, [a,b,c,d])
    dlat,dlon = c-a, d-b
    return R*2*math.asin(math.sqrt(math.sin(dlat/2)**2 + math.cos(a)*math.cos(c)*math.sin(dlon/2)**2))

# Check 10 nearest Kroger entries to LA
kroger_entries = [(k, v) for k, v in store_locs.items() if k[0] == "kroger" and v.get("lat")]
kroger_entries.sort(key=lambda x: dist(LA_LAT, LA_LNG, x[1]["lat"], x[1]["lng"]))
print("\n10 nearest Kroger entries to LA:")
for k, v in kroger_entries[:10]:
    d = dist(LA_LAT, LA_LNG, v["lat"], v["lng"])
    print(f"  {d:6.1f} mi  lat={v['lat']:.4f},{v['lng']:.4f}  zip={k[1]}  addr={v.get('address')}")

info = _get_store_info("Kroger", "90046", store_locs, LA_LAT, LA_LNG)
print(f"\n_get_store_info result: {info}")
