"""
Fix kroger retailer_key to only contain actual Kroger-branded stores.

Steps:
1. Fetch all real Kroger stores from OSM (brand=Kroger)
2. For each active kroger row in DB, check if it's within 2 miles of a real Kroger
   - Yes -> keep (real Kroger store)
   - No  -> disable (banner store, not a real Kroger)
3. Upsert missing real Kroger stores from OSM

Usage:
    python scripts/fix_kroger_banners.py [--dry-run]
"""
import sys
sys.path.insert(0, ".")

import math
import time
import argparse
import requests
from datetime import datetime, timezone
from config.supabase import get_supabase_client

OVERPASS_URLS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://maps.mail.ru/osm/tools/overpass/api/interpreter",
]
US_BBOX = (24.0, -168.0, 71.5, -66.0)


def haversine(lat1, lon1, lat2, lon2):
    R = 3958.8
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon/2)**2
    return R * 2 * math.asin(math.sqrt(a))


def fetch_real_kroger():
    lat_min, lon_min, lat_max, lon_max = US_BBOX
    query = f"""
[out:json][timeout:90];
(
  node["brand"="Kroger"]({lat_min},{lon_min},{lat_max},{lon_max});
  node["name"="Kroger"]["shop"="supermarket"]({lat_min},{lon_min},{lat_max},{lon_max});
);
out;
"""
    for url in OVERPASS_URLS:
        for attempt in range(3):
            try:
                r = requests.post(url, data={"data": query}, timeout=120,
                                  headers={"User-Agent": "prox-backend/1.0"})
                r.raise_for_status()
                elements = r.json().get("elements", [])
                print(f"Fetched {len(elements)} real Kroger stores from OSM")
                return elements
            except Exception as e:
                wait = 5 * (attempt + 1)
                print(f"  attempt {attempt+1} failed ({e}) — retrying in {wait}s...")
                time.sleep(wait)
    print("All endpoints failed")
    return []


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if args.dry_run:
        print("[DRY RUN] Nothing will be written.\n")

    sb = get_supabase_client()

    # Step 1: Fetch real Kroger stores from OSM
    print("Fetching real Kroger stores from OSM...")
    elements = fetch_real_kroger()

    osm_stores = []
    for el in elements:
        if not el.get("lat") or not el.get("lon"):
            continue
        tags = el.get("tags", {})
        zip_code = tags.get("addr:postcode", "")[:5]
        if not zip_code:
            continue
        house = tags.get("addr:housenumber", "")
        street = tags.get("addr:street", "")
        city = tags.get("addr:city", "")
        state = tags.get("addr:state", "")
        address = f"{house} {street}".strip() if street else None
        osm_stores.append({
            "lat": el["lat"], "lon": el["lon"],
            "zip_code": zip_code, "address": address,
            "city": city or None, "state": state or None,
        })

    print(f"Real Kroger stores with zip codes: {len(osm_stores)}")

    # Step 2: Load all active kroger rows from DB
    print("\nLoading active kroger rows from DB...")
    db_rows = []
    offset = 0
    while True:
        res = sb.table("store_locations").select(
            "id,latitude,longitude,zip_code,geocode_source"
        ).eq("retailer_key", "kroger").eq("show_on_map", True).range(offset, offset+999).execute()
        db_rows.extend(res.data)
        if len(res.data) < 1000:
            break
        offset += 1000
    print(f"Active kroger rows in DB: {len(db_rows)}")

    # Step 3: For each DB row, check if it's within 2 miles of a real Kroger
    keep_ids = []
    banner_ids = []
    for row in db_rows:
        lat = row.get("latitude")
        lon = row.get("longitude")
        if not lat or not lon:
            banner_ids.append(row["id"])
            continue
        is_real = any(
            haversine(float(lat), float(lon), s["lat"], s["lon"]) <= 2.0
            for s in osm_stores
        )
        if is_real:
            keep_ids.append(row["id"])
        else:
            banner_ids.append(row["id"])

    print(f"\nReal Kroger rows (keep): {len(keep_ids)}")
    print(f"Banner rows (disable):   {len(banner_ids)}")

    if not args.dry_run:
        # Disable banner rows
        print("\nDisabling banner rows...")
        for i in range(0, len(banner_ids), 50):
            batch = banner_ids[i:i+50]
            sb.table("store_locations").update({"show_on_map": False}).in_("id", batch).execute()
        print(f"Disabled {len(banner_ids)} banner rows.")

    # Step 4: Upsert missing real Kroger stores
    # Find OSM stores that aren't already covered by a DB row within 2 miles
    print("\nFinding missing Kroger stores to add...")
    missing = []
    for s in osm_stores:
        covered = any(
            haversine(s["lat"], s["lon"], float(r["latitude"]), float(r["longitude"])) <= 2.0
            for r in db_rows if r["id"] in keep_ids and r.get("latitude") and r.get("longitude")
        )
        if not covered:
            missing.append(s)

    # Dedupe by zip
    seen_zips = set()
    to_insert = []
    for s in missing:
        if s["zip_code"] not in seen_zips:
            seen_zips.add(s["zip_code"])
            to_insert.append({
                "retailer": "Kroger",
                "retailer_key": "kroger",
                "zip_code": s["zip_code"],
                "address": s["address"],
                "city": s["city"],
                "state": s["state"],
                "latitude": s["lat"],
                "longitude": s["lon"],
                "geocode_source": "osm",
                "geocode_confidence": "exact",
                "show_on_map": True,
                "geocoded_at": datetime.now(timezone.utc).isoformat(),
            })

    print(f"Missing stores to add: {len(to_insert)}")

    if args.dry_run:
        print("\n[DRY RUN] Would disable:", len(banner_ids), "| Would add:", len(to_insert))
        return

    if to_insert:
        print("Upserting missing Kroger stores...")
        added = 0
        for i in range(0, len(to_insert), 50):
            batch = to_insert[i:i+50]
            try:
                sb.table("store_locations").upsert(
                    batch, ignore_duplicates=True, on_conflict="retailer_key,zip_code"
                ).execute()
                added += len(batch)
            except Exception as e:
                print(f"  Batch {i} failed: {e}")
        print(f"Added {added} new Kroger stores.")

    print("\nDone.")


if __name__ == "__main__":
    main()
