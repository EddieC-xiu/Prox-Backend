"""
Flag ZIP-centroid and non-store rows in store_locations by setting
geocode_confidence = 'zip_centroid'. Does NOT delete them (avoids FK issues).
The service code already skips rows where confidence = 'zip'.

Run: PYTHONPATH=. venv/Scripts/python.exe scripts/flag_zip_centroid_stores.py
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

print("Loading store_locations with coords...")
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

print(f"  Loaded {len(all_rows)} rows")

# Phase 1: ZIP-centroid (null address + coord shared by 2+ different retailers)
coord_retailers: dict[str, set] = defaultdict(set)
coord_ids: dict[str, list] = defaultdict(list)

for r in all_rows:
    if r.get("full_address"):
        continue
    ck = coord_key(r["latitude"], r["longitude"])
    rk = r.get("retailer_key") or norm_key(r.get("retailer", ""))
    coord_retailers[ck].add(rk)
    coord_ids[ck].append(r["id"])

zip_centroid_ids = []
for ck, retailers in coord_retailers.items():
    if len(retailers) >= 2:
        zip_centroid_ids.extend(coord_ids[ck])

# Phase 2: Non-store variants
non_store_ids = []
for r in all_rows:
    name = (r.get("retailer") or "").lower()
    if any(kw in name for kw in NON_STORE_KEYWORDS):
        non_store_ids.append(r["id"])

all_flag = list(set(zip_centroid_ids + non_store_ids))
print(f"ZIP-centroid rows: {len(zip_centroid_ids)}")
print(f"Non-store variants: {len(non_store_ids)}")
print(f"Total to flag: {len(all_flag)}")

# Flag in batches of 500 (UPDATE, no FK issues)
flagged = 0
for i in range(0, len(all_flag), 500):
    batch = all_flag[i:i + 500]
    sb.table("store_locations").update({"geocode_confidence": "zip_centroid"}).in_("id", batch).execute()
    flagged += len(batch)
    print(f"  Flagged {flagged}/{len(all_flag)}...")

print(f"\nDone. Flagged {flagged} rows as 'zip_centroid'.")
print("These rows will be skipped by _load_store_locations (confidence != 'zip' check).")
