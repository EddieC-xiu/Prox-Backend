"""Check retailers with 0 real GPS and other specific gaps."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from config.supabase import get_supabase_client
sb = get_supabase_client()

def check(rk):
    res = sb.table("store_locations").select("id, zip_code, city, state, latitude, geocode_confidence, full_address").eq("retailer_key", rk).execute().data or []
    real = [r for r in res if r.get("latitude") is not None and r.get("geocode_confidence") not in ("zip_centroid", "zip")]
    null_lat = [r for r in res if r.get("latitude") is None]
    centroid = [r for r in res if r.get("geocode_confidence") in ("zip_centroid", "zip")]
    print(f"\n{rk}: {len(res)} total, {len(real)} real, {len(centroid)} centroid, {len(null_lat)} null-lat")
    for r in res:
        print(f"  id={r['id']} zip={r.get('zip_code')} {r.get('city')},{r.get('state')} lat={r.get('latitude')} conf={r.get('geocode_confidence')}")

# 0 real GPS
check("hubbens")
check("mathernes")

# Low real GPS
check("rouses")
check("superiorgrocers")
check("northgate")
check("bristolfarms")

# null retailer_key
res = sb.table("store_locations").select("id, retailer, zip_code, geocode_confidence, latitude").is_("retailer_key", "null").limit(20).execute().data or []
print(f"\nNull retailer_key rows: {len(res)}")
for r in res:
    print(f"  id={r['id']} retailer={r.get('retailer')} zip={r.get('zip_code')} conf={r.get('geocode_confidence')} lat={r.get('latitude')}")
