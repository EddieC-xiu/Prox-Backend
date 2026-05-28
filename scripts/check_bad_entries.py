"""Check specific suspicious store_locations entries."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from config.supabase import get_supabase_client
sb = get_supabase_client()

# ── Kroger near Studio City ──────────────────────────────────────────────────
print("=== Kroger near 34.1441, -118.4131 (Studio City CA) ===")
res = sb.table("store_locations").select("id, retailer_key, retailer, store_name, zip_code, city, state, latitude, longitude, geocode_confidence, full_address").eq("retailer_key", "kroger").gte("latitude", 33.5).lte("latitude", 35.0).gte("longitude", -119.0).lte("longitude", -117.0).execute().data or []
for r in res:
    print(f"  id={r['id']} zip={r.get('zip_code')} {r.get('city')},{r.get('state')} lat={r.get('latitude')},{r.get('longitude')} conf={r.get('geocode_confidence')} store={r.get('store_name')} addr={r.get('full_address')}")

# ── Stop & Shop in SoCal ─────────────────────────────────────────────────────
print("\n=== Stop & Shop near 33.9394,-117.4682 (SoCal) ===")
res = sb.table("store_locations").select("id, retailer_key, retailer, store_name, zip_code, city, state, latitude, longitude, geocode_confidence, full_address").ilike("retailer_key", "%stop%").execute().data or []
for r in res:
    print(f"  id={r['id']} rk={r['retailer_key']} zip={r.get('zip_code')} {r.get('city')},{r.get('state')} lat={r.get('latitude')},{r.get('longitude')} conf={r.get('geocode_confidence')} store={r.get('store_name')}")

# ── Key Food in Michigan ─────────────────────────────────────────────────────
print("\n=== Key Food (all entries) ===")
res = sb.table("store_locations").select("id, retailer_key, retailer, store_name, zip_code, city, state, latitude, longitude, geocode_confidence").ilike("retailer_key", "%keyfood%").execute().data or []
for r in res:
    print(f"  id={r['id']} rk={r['retailer_key']} zip={r.get('zip_code')} {r.get('city')},{r.get('state')} lat={r.get('latitude')},{r.get('longitude')} conf={r.get('geocode_confidence')}")

# ── Western Beef ─────────────────────────────────────────────────────────────
print("\n=== Western Beef (all entries) ===")
res = sb.table("store_locations").select("id, retailer_key, retailer, store_name, zip_code, city, state, latitude, longitude, geocode_confidence").ilike("retailer_key", "%western%beef%").execute().data or []
for r in res:
    print(f"  id={r['id']} rk={r['retailer_key']} zip={r.get('zip_code')} {r.get('city')},{r.get('state')} lat={r.get('latitude')},{r.get('longitude')} conf={r.get('geocode_confidence')}")

# ── trader_joes no-zip collapse stats ────────────────────────────────────────
print("\n=== trader_joes entries with no zip (collapse issue) ===")
res = sb.table("store_locations").select("count", count="exact").eq("retailer_key", "trader_joes").is_("zip_code", "null").execute()
print(f"  trader_joes rows with null zip: {res.count}")
res2 = sb.table("store_locations").select("count", count="exact").eq("retailer_key", "trader_joes").execute()
print(f"  trader_joes total rows: {res2.count}")

# ── ShopRite in Oakland? ─────────────────────────────────────────────────────
print("\n=== ShopRite near Oakland (37.7714,-122.1926) ===")
res = sb.table("store_locations").select("id, retailer_key, retailer, store_name, zip_code, city, state, latitude, longitude, geocode_confidence").eq("retailer_key", "shoprite").gte("latitude", 36.0).lte("latitude", 39.0).execute().data or []
for r in res:
    print(f"  id={r['id']} zip={r.get('zip_code')} {r.get('city')},{r.get('state')} lat={r.get('latitude')},{r.get('longitude')} conf={r.get('geocode_confidence')} store={r.get('store_name')}")
