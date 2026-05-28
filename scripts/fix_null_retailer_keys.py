"""
Neutralize all store_locations rows with null retailer_key.
These are all duplicates of existing entries (SQL NULL bypasses the unique constraint
on retailer_key+zip_code, so these accumulated as shadows).
Setting latitude=NULL excludes them from the cache query (which filters NOT NULL lat).
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from config.supabase import get_supabase_client

sb = get_supabase_client()

# Fetch all null retailer_key row IDs
print("Loading null-key rows...")
all_ids = []
offset = 0
while True:
    batch = sb.table("store_locations").select("id").is_("retailer_key", "null").range(offset, offset + 999).execute().data or []
    all_ids.extend(r["id"] for r in batch)
    if len(batch) < 1000:
        break
    offset += 1000

print(f"Found {len(all_ids)} null retailer_key rows")
print("Neutralizing (setting lat=NULL, lng=NULL, geocode_confidence='zip_centroid')...")

neutralized = 0
for i in range(0, len(all_ids), 100):
    batch_ids = all_ids[i:i+100]
    sb.table("store_locations").update({
        "latitude": None,
        "longitude": None,
        "geocode_confidence": "zip_centroid"
    }).in_("id", batch_ids).execute()
    neutralized += len(batch_ids)
    print(f"  {neutralized}/{len(all_ids)} neutralized...")

# Verify
remaining_with_lat = sb.table("store_locations").select("id", count="exact").is_("retailer_key", "null").not_.is_("latitude", "null").execute()
print(f"\nNull-key rows still with real lat: {remaining_with_lat.count}")
print("Done.")
