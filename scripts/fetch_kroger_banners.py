"""
Fetch Kroger banner brand locations from OSM and write to store_locations.

All Kroger banner stores (Fred Meyer, King Soopers, Harris Teeter, etc.)
are stored with retailer_key="kroger" so they count toward nearby_kroger
proximity checks.

Usage:
    python scripts/fetch_kroger_banners.py [--dry-run] [--banner "Fred Meyer"]
"""
import sys
sys.path.insert(0, ".")

import time
import argparse
import requests
from datetime import datetime, timezone
from config.supabase import get_supabase_client

sb = get_supabase_client()

# Approx bounding box for continental US + AK
US_BBOX = (24.0, -168.0, 71.5, -66.0)

OVERPASS_URLS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://maps.mail.ru/osm/tools/overpass/api/interpreter",
]

# Maps OSM brand tag → display name used in store_locations.retailer
# All use retailer_key="kroger"
KROGER_BANNERS = {
    "Fred Meyer": "Fred Meyer",
    "King Soopers": "King Soopers",
    "Harris Teeter": "Harris Teeter",
    "Fry's Food and Drug": "Fry's Food and Drug",
    "Smith's": "Smith's",
    "Dillons": "Dillons",
    "QFC": "QFC",
    "Pick 'n Save": "Pick 'n Save",
    "Mariano's Fresh Market": "Mariano's",
    "City Market": "City Market",
    "Ruler Foods": "Ruler Foods",
}


def now_iso():
    return datetime.now(timezone.utc).isoformat()


def fetch_banner(brand_name, retries=3):
    lat_min, lon_min, lat_max, lon_max = US_BBOX
    query = f"""
[out:json][timeout:60];
node["brand"="{brand_name}"]({lat_min},{lon_min},{lat_max},{lon_max});
out;
"""
    for url in OVERPASS_URLS:
        for attempt in range(retries):
            try:
                r = requests.post(url, data={"data": query}, timeout=90, headers={"User-Agent": "prox-backend/1.0"})
                r.raise_for_status()
                elements = r.json().get("elements", [])
                print(f"  {brand_name}: {len(elements)} locations (via {url})")
                return elements
            except Exception as e:
                wait = 5 * (attempt + 1)
                print(f"  {brand_name}: attempt {attempt + 1} failed ({e}) — retrying in {wait}s...")
                time.sleep(wait)
    print(f"  {brand_name}: all endpoints failed — skipping")
    return []


def element_to_row(el, display_name):
    tags = el.get("tags", {})
    house = tags.get("addr:housenumber", "")
    street = tags.get("addr:street", "")
    city = tags.get("addr:city", "")
    state = tags.get("addr:state", "")
    zip_code = tags.get("addr:postcode", "")[:5]  # truncate ZIP+4
    full_address = f"{house} {street}, {city}, {state} {zip_code}".strip(", ")
    if not zip_code:
        return None  # can't store without a zip
    return {
        "retailer": display_name,
        "retailer_key": "kroger",
        "full_address": full_address,
        "zip_code": zip_code,
        "latitude": el["lat"],
        "longitude": el["lon"],
        "geocode_source": "osm",
        "geocode_confidence": "exact",
        "show_on_map": True,
        "geocoded_at": now_iso(),
    }


def write_batch(rows):
    # ignore_duplicates skips rows that violate the (retailer_key, zip_code) unique constraint
    sb.table("store_locations").upsert(rows, ignore_duplicates=True, on_conflict="retailer_key,zip_code").execute()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--banner",
        type=str,
        default=None,
        help='Run only a specific banner, e.g. --banner "Fred Meyer"',
    )
    args = parser.parse_args()

    if args.dry_run:
        print("[DRY RUN] Nothing will be written.\n")

    if args.banner:
        if args.banner not in KROGER_BANNERS:
            print(f"Unknown banner: {args.banner}")
            print(f"Valid banners: {', '.join(KROGER_BANNERS.keys())}")
            sys.exit(1)
        banners = {args.banner: KROGER_BANNERS[args.banner]}
    else:
        banners = KROGER_BANNERS

    all_rows = []
    for brand_name, display_name in banners.items():
        print(f"\nFetching {brand_name}...")
        elements = fetch_banner(brand_name)
        for el in elements:
            if el.get("lat") and el.get("lon"):
                row = element_to_row(el, display_name)
                if row:
                    all_rows.append(row)
        time.sleep(3)

    print(f"\nTotal locations found: {len(all_rows)}")

    # Deduplicate within our own results by (retailer_key, zip_code)
    seen = set()
    deduped = []
    for row in all_rows:
        key = (row["retailer_key"], row["zip_code"])
        if key not in seen:
            seen.add(key)
            deduped.append(row)
    if len(deduped) < len(all_rows):
        print(f"After dedup: {len(deduped)} rows (dropped {len(all_rows) - len(deduped)} duplicates)")
    all_rows = deduped

    if args.dry_run:
        print("\nSample rows:")
        for r in all_rows[:10]:
            print(f"  [{r['retailer']}] {r['full_address']} -> ({r['latitude']:.4f}, {r['longitude']:.4f})")
        print("\n[DRY RUN] Nothing was written.")
        return

    print("\nWriting to DB...")
    written = 0
    for i in range(0, len(all_rows), 50):
        batch = all_rows[i : i + 50]
        try:
            write_batch(batch)
            written += len(batch)
            print(f"  Written {written} / {len(all_rows)}...")
        except Exception as e:
            print(f"  Batch {i} failed: {e}")

    print(f"\nDone. {written} Kroger banner locations written to store_locations.")


if __name__ == "__main__":
    main()
