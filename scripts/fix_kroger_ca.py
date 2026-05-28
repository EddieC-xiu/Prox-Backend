"""Find and neutralize all non-centroid Kroger entries in CA (Kroger doesn't operate in CA)."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from config.supabase import get_supabase_client

sb = get_supabase_client()

# Find all Kroger entries with real GPS in the western US / CA (lon west of -115)
res = (
    sb.table("store_locations")
    .select("id, zip_code, city, state, latitude, longitude, geocode_confidence, full_address")
    .eq("retailer_key", "kroger")
    .not_.is_("latitude", "null")
    .lte("longitude", -114.0)
    .execute()
    .data or []
)
print(f"Kroger entries with real GPS west of -114: {len(res)}")
for r in res:
    print(f"  id={r['id']} zip={r.get('zip_code')} {r.get('city')},{r.get('state')} lat={r.get('latitude')},{r.get('longitude')} conf={r.get('geocode_confidence')} addr={r.get('full_address')}")

# In CA (state='CA' or lat/lng in CA bounding box) — neutralize the real-GPS ones
# CA is roughly lat 32-42, lng -124 to -114
ca_bad_ids = [r["id"] for r in res if r.get("state") == "CA" and r.get("geocode_confidence") not in ("zip_centroid", "zip")]
print(f"\nCA Kroger entries to neutralize: {len(ca_bad_ids)}")
print(f"  IDs: {ca_bad_ids}")

if ca_bad_ids:
    result = (
        sb.table("store_locations")
        .update({"latitude": None, "longitude": None, "geocode_confidence": "zip_centroid"})
        .in_("id", ca_bad_ids)
        .execute()
    )
    print(f"Neutralized: {len(result.data)} rows")
