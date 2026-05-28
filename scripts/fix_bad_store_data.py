"""
Neutralize confirmed bad store_locations entries by nulling their GPS coords
and marking them as zip_centroid (excluded from cache). Can't delete due to FK.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from config.supabase import get_supabase_client

sb = get_supabase_client()

bad_ids = [
    # Kroger in California (Kroger doesn't operate in CA — uses Ralphs brand)
    4618,   # Studio City CA 91604
    4639,   # Torrance CA 90501
    4699,   # Los Angeles CA 90064

    # Stop & Shop in wrong states (NE chain only)
    23666,  # Riverside CA 92503
    23472,  # Spokane WA 99202
    23504,  # British Columbia zip 98844

    # Key Food outside NY metro area
    70663,  # Sarasota FL 34235
    70664,  # Detroit MI 48207
    70665,  # Coconut Creek FL 33073
    70657,  # Petoskey MI 49770
    70672,  # Lorain OH 44055
    70659,  # Cape Coral FL 33909

    # Western Beef in Canada
    63917,  # Ottawa area K4B1H

    # ShopRite in California
    22710,  # Oakland CA 94613
]

print(f"Neutralizing {len(bad_ids)} bad store_locations entries (null GPS + zip_centroid)...")

result = (
    sb.table("store_locations")
    .update({"latitude": None, "longitude": None, "geocode_confidence": "zip_centroid"})
    .in_("id", bad_ids)
    .execute()
)
print(f"Updated: {len(result.data)} rows")
for r in result.data:
    print(f"  neutralized id={r['id']} rk={r.get('retailer_key')} zip={r.get('zip_code')} city={r.get('city')} state={r.get('state')}")

# Verify Kroger near LA is gone from cache view
print("\nVerifying fix — Kroger high-conf entries in CA (should be 0):")
check = (
    sb.table("store_locations")
    .select("id, zip_code, city, state, latitude, longitude, geocode_confidence")
    .eq("retailer_key", "kroger")
    .neq("geocode_confidence", "zip_centroid")
    .neq("geocode_confidence", "zip")
    .gte("latitude", 33.5).lte("latitude", 35.5)
    .execute()
    .data or []
)
print(f"  {len(check)} remaining non-centroid Kroger entries in CA lat range")
