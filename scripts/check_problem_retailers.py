"""Check current state of retailers with GPS coverage issues."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from config.supabase import get_supabase_client
sb = get_supabase_client()

def check(retailer_key, label):
    res = sb.table("store_locations").select("id, zip_code, city, state, latitude, longitude, geocode_confidence, full_address").eq("retailer_key", retailer_key).execute().data or []
    real = [r for r in res if r.get("latitude") is not None and r.get("geocode_confidence") not in ("zip_centroid", "zip")]
    null_lat = [r for r in res if r.get("latitude") is None]
    centroid = [r for r in res if r.get("geocode_confidence") in ("zip_centroid", "zip")]
    print(f"\n{'='*60}")
    print(f"{label} (key={retailer_key}): {len(res)} total, {len(real)} real GPS, {len(centroid)} centroid, {len(null_lat)} null lat")
    for r in res[:10]:
        print(f"  id={r['id']} zip={r.get('zip_code')} {r.get('city')},{r.get('state')} lat={r.get('latitude')} conf={r.get('geocode_confidence')}")
    if len(res) > 10:
        print(f"  ... +{len(res)-10} more")

check("hmart", "H Mart")
check("vallarta", "Vallarta Supermarkets")
check("food4less", "Food4Less")
check("gelsons", "Gelson's")
check("bristolfarms", "Bristol Farms")
check("restaurantdepot", "Restaurant Depot")
check("giantfood", "Giant Food")
check("superiorgrocers", "Superior Grocers")
check("northgate", "Northgate Market")
check("erewhon", "Erewhon")
