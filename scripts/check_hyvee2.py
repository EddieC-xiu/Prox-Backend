import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from config.supabase import get_supabase_client
sb = get_supabase_client()

# Search retailer display name containing 'hy'
res = sb.table("store_locations").select("retailer_key, retailer, geocode_confidence, latitude, longitude").ilike("retailer", "%hy%").limit(50).execute().data or []
print(f"retailer containing 'hy': {len(res)}")
for r in res:
    print(f"  rk={r['retailer_key']} retailer={r['retailer']} conf={r.get('geocode_confidence')} lat={r.get('latitude')}")

print()
# Also check distinct retailer_keys that have 'hyvee' or 'hy_vee' or 'hy vee'
for term in ("hyvee", "hy-vee", "hy_vee", "hv"):
    res2 = sb.table("store_locations").select("retailer_key, retailer").ilike("retailer_key", f"%{term}%").limit(5).execute().data or []
    print(f"retailer_key LIKE '%{term}%': {len(res2)} rows {[r['retailer_key'] for r in res2[:3]]}")

# Check flyer_deals for Hy-Vee
from config.supabase import get_supabase_client
sb2 = get_supabase_client()
res3 = sb2.table("test_flyer_deals_duplicate").select("retailer, retailer_key, zip_code").ilike("retailer", "%hy%").limit(10).execute().data or []
print(f"\nflyer_deals retailer LIKE '%hy%': {len(res3)}")
for r in res3:
    print(f"  retailer={r['retailer']} rk={r.get('retailer_key')} zip={r.get('zip_code')}")
