import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from config.supabase import get_supabase_client
sb = get_supabase_client()
# Search by retailer_key containing 'hy'
res = sb.table("store_locations").select("retailer_key, retailer, geocode_confidence, latitude").ilike("retailer_key", "%hy%").limit(20).execute().data or []
print(f"retailer_key containing 'hy': {len(res)}")
for r in res:
    print(f"  rk={r['retailer_key']} retailer={r['retailer']} conf={r.get('geocode_confidence')}")
