"""
Delete all store_locations rows with coordinates outside the USA
(continental US, Hawaii, Alaska, Puerto Rico).
Fetches IDs first, then deletes in batches of 500.
"""
from config.supabase import get_supabase_client

sb = get_supabase_client()

# Fetch all rows with coordinates to check bounds
print("Fetching all store_locations with coordinates...")

US_BOUNDS = [
    # (lat_min, lat_max, lng_min, lng_max)
    (24.0, 49.5, -125.0, -66.0),   # Continental US
    (18.0, 23.0, -161.0, -154.0),  # Hawaii
    (51.0, 72.0, -180.0, -129.0),  # Alaska
    (17.9, 18.6, -67.3, -65.6),    # Puerto Rico
]

def is_us(lat, lng):
    for lat_min, lat_max, lng_min, lng_max in US_BOUNDS:
        if lat_min <= lat <= lat_max and lng_min <= lng <= lng_max:
            return True
    return False

# Paginate through all rows
page_size = 1000
offset = 0
to_delete = []

while True:
    rows = (
        sb.table("store_locations")
        .select("id, retailer_key, zip_code, latitude, longitude")
        .not_.is_("latitude", "null")
        .not_.is_("longitude", "null")
        .range(offset, offset + page_size - 1)
        .execute()
        .data or []
    )
    if not rows:
        break
    for r in rows:
        lat = float(r["latitude"])
        lng = float(r["longitude"])
        if not is_us(lat, lng):
            to_delete.append((r["id"], r["retailer_key"], r["zip_code"], lat, lng))
    offset += page_size
    print(f"  Scanned {offset} rows, found {len(to_delete)} non-US so far...")
    if len(rows) < page_size:
        break

print(f"\nTotal non-US rows to delete: {len(to_delete)}")
if not to_delete:
    print("Nothing to delete.")
    exit(0)

# Show breakdown by retailer
from collections import Counter
by_retailer = Counter(r[1] for r in to_delete)
print("\nBreakdown by retailer_key:")
for k, v in sorted(by_retailer.items(), key=lambda x: -x[1]):
    print(f"  {k:<30} {v}")

# Confirm
print(f"\nDeleting {len(to_delete)} rows...")

batch_size = 500
deleted = 0
ids = [r[0] for r in to_delete]

for i in range(0, len(ids), batch_size):
    batch = ids[i:i + batch_size]
    sb.table("store_locations").delete().in_("id", batch).execute()
    deleted += len(batch)
    print(f"  Deleted {deleted}/{len(ids)}...")

print(f"\nDone. Deleted {deleted} international rows from store_locations.")
