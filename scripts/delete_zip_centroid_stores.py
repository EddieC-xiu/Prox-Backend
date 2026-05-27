"""
Delete suspected ZIP-centroid rows from store_locations.

A row is a suspected ZIP-centroid if:
  - full_address IS NULL (no real street address)
  - The same (lat, lng) rounded to 4 decimal places is shared by
    2+ different normalized retailer_keys

These are fallback/geocoding rows where an entire zip was assigned
one coordinate, causing many unrelated retailers to appear at the same map pin.

Also deletes non-customer-facing store variants:
  Fuel Station, Gas Station, Pharmacy, Optical, Tire Center,
  Parking, Distribution Center, Corporate, Vision Center,
  Auto Care Center, Garden Center, Under Construction
"""
import re
from collections import defaultdict
from config.supabase import get_supabase_client

sb = get_supabase_client()

NON_STORE_KEYWORDS = [
    "fuel station", "gas station", " pharmacy", " optical",
    "tire center", " parking", "distribution center", "corporate",
    "vision center", "auto care", "garden center", "under construction",
]

def norm_key(retailer: str) -> str:
    return re.sub(r"[^a-z0-9]", "", retailer.lower().strip())

def coord_key(lat, lng) -> str:
    return f"{round(float(lat), 4)},{round(float(lng), 4)}"

print("Loading all store_locations with coords...")
page, all_rows = 0, []
while True:
    batch = (
        sb.table("store_locations")
        .select("id, retailer_key, retailer, latitude, longitude, full_address")
        .not_.is_("latitude", "null")
        .not_.is_("longitude", "null")
        .range(page * 1000, (page + 1) * 1000 - 1)
        .execute()
        .data or []
    )
    if not batch:
        break
    all_rows.extend(batch)
    page += 1

print(f"  Loaded {len(all_rows)} rows total")

# --- Phase 1: ZIP-centroid rows (null address + coord shared by 2+ retailers) ---
coord_retailers: dict[str, set] = defaultdict(set)
coord_ids: dict[str, list] = defaultdict(list)

for r in all_rows:
    if r.get("full_address"):
        continue  # has a real address — skip
    ck = coord_key(r["latitude"], r["longitude"])
    rk = r.get("retailer_key") or norm_key(r.get("retailer", ""))
    coord_retailers[ck].add(rk)
    coord_ids[ck].append(r["id"])

zip_centroid_ids = []
for ck, retailers in coord_retailers.items():
    if len(retailers) >= 2:
        zip_centroid_ids.extend(coord_ids[ck])

print(f"\nPhase 1 — suspected ZIP-centroid rows: {len(zip_centroid_ids)}")

# --- Phase 2: Non-store variants (fuel, pharmacy, parking, etc.) ---
non_store_ids = []
for r in all_rows:
    name = (r.get("retailer") or "").lower()
    if any(kw in name for kw in NON_STORE_KEYWORDS):
        non_store_ids.append(r["id"])

print(f"Phase 2 — non-store variant rows:       {len(non_store_ids)}")

all_delete = list(set(zip_centroid_ids + non_store_ids))
print(f"\nTotal rows to delete:                   {len(all_delete)}")

if not all_delete:
    print("Nothing to delete.")
    exit(0)

# Breakdown by retailer_key
from collections import Counter
id_to_rk = {r["id"]: (r.get("retailer_key") or norm_key(r.get("retailer", ""))) for r in all_rows}
by_retailer = Counter(id_to_rk[i] for i in all_delete if i in id_to_rk)
print("\nBreakdown by retailer_key (top 25):")
for k, v in sorted(by_retailer.items(), key=lambda x: -x[1])[:25]:
    print(f"  {k:<35} {v}")

# Find which bad store IDs are actually referenced in flyer_deals
# Query each individually to avoid full-table scan on unindexed store_id column
print("\nFinding which IDs are referenced in flyer_deals...")
referenced = []
for idx, sid in enumerate(all_delete):
    row = sb.table("flyer_deals").select("id").eq("store_id", sid).limit(1).execute().data
    if row:
        referenced.append(sid)
    if (idx + 1) % 500 == 0:
        print(f"  Checked {idx + 1}/{len(all_delete)}, found {len(referenced)} referenced...")

print(f"  {len(referenced)} of {len(all_delete)} IDs are referenced — nulling those...")
for sid in referenced:
    sb.table("flyer_deals").update({"store_id": None}).eq("store_id", sid).execute()
print(f"  Done nulling {len(referenced)} referenced store IDs")

# Now delete the bad rows
deleted = 0
for i in range(0, len(all_delete), 500):
    batch = all_delete[i:i + 500]
    sb.table("store_locations").delete().in_("id", batch).execute()
    deleted += len(batch)
    print(f"  Deleted {deleted}/{len(all_delete)}...")

print(f"\nDone. Deleted {deleted} rows.")
