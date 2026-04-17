# scripts/fetch_kroger_locations.py
import time
import argparse
import requests
from datetime import datetime, timezone
from config.supabase import get_supabase_client

sb = get_supabase_client()

def now_iso():
    return datetime.now(timezone.utc).isoformat()

STATE_BOXES = [
    ("AL", 30.14, -88.47, 35.01, -84.89),
    ("AK", 54.68, -168.00, 71.54, -130.00),
    ("AZ", 31.33, -114.82, 37.00, -109.05),
    ("AR", 33.00, -94.62, 36.50, -89.64),
    ("CA", 32.53, -124.41, 42.01, -114.13),
    ("CO", 36.99, -109.05, 41.00, -102.04),
    ("CT", 40.99, -73.73, 42.05, -71.79),
    ("DE", 38.45, -75.79, 39.84, -75.05),
    ("FL", 24.54, -87.63, 31.00, -80.03),
    ("GA", 30.36, -85.61, 35.00, -80.84),
    ("HI", 18.91, -160.25, 22.24, -154.81),
    ("ID", 41.99, -117.24, 49.00, -111.04),
    ("IL", 36.97, -91.51, 42.51, -87.02),
    ("IN", 37.77, -88.10, 41.76, -84.78),
    ("IA", 40.38, -96.64, 43.50, -90.14),
    ("KS", 36.99, -102.05, 40.00, -94.59),
    ("KY", 36.49, -89.57, 39.15, -81.96),
    ("LA", 28.93, -94.04, 33.02, -88.82),
    ("ME", 43.06, -71.08, 47.46, -66.95),
    ("MD", 37.91, -79.49, 39.72, -75.05),
    ("MA", 41.24, -73.50, 42.89, -69.93),
    ("MI", 41.70, -90.42, 48.19, -82.41),
    ("MN", 43.50, -97.24, 49.38, -89.49),
    ("MS", 30.17, -91.66, 35.01, -88.10),
    ("MO", 35.99, -95.77, 40.61, -89.10),
    ("MT", 44.36, -116.05, 49.00, -104.04),
    ("NE", 39.99, -104.05, 43.00, -95.31),
    ("NV", 35.00, -120.01, 42.00, -114.03),
    ("NH", 42.70, -72.56, 45.31, -70.61),
    ("NJ", 38.93, -75.56, 41.36, -73.89),
    ("NM", 31.33, -109.05, 37.00, -103.00),
    ("NY", 40.50, -79.76, 45.01, -71.86),
    ("NC", 33.84, -84.32, 36.59, -75.46),
    ("ND", 45.94, -104.05, 49.00, -96.55),
    ("OH", 38.40, -84.82, 42.00, -80.52),
    ("OK", 33.62, -103.00, 37.00, -94.43),
    ("OR", 41.99, -124.57, 46.24, -116.46),
    ("PA", 39.72, -80.52, 42.27, -74.69),
    ("RI", 41.15, -71.91, 42.02, -71.12),
    ("SC", 32.05, -83.35, 35.22, -78.54),
    ("SD", 42.48, -104.06, 45.95, -96.44),
    ("TN", 34.98, -90.31, 36.68, -81.65),
    ("TX", 25.84, -106.65, 36.50, -93.51),
    ("UT", 36.99, -114.05, 42.00, -109.04),
    ("VT", 42.73, -73.44, 45.02, -71.50),
    ("VA", 36.54, -83.68, 39.47, -75.24),
    ("WA", 45.54, -124.73, 49.00, -116.92),
    ("WV", 37.20, -82.64, 40.64, -77.72),
    ("WI", 42.49, -92.89, 47.08, -86.25),
    ("WY", 40.99, -111.06, 45.01, -104.05),
    ("DC", 38.79, -77.12, 38.99, -76.91),
]

OVERPASS_URLS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://maps.mail.ru/osm/tools/overpass/api/interpreter",
]

def fetch_kroger_for_state(state_abbr, bbox, retries=3):
    lat_min, lon_min, lat_max, lon_max = bbox
    query = f"""
    [out:json];
    node["brand"="Kroger"]({lat_min},{lon_min},{lat_max},{lon_max});
    out;
    """
    for url in OVERPASS_URLS:
        for attempt in range(retries):
            try:
                r = requests.post(url, data={"data": query}, timeout=60)
                r.raise_for_status()
                elements = r.json().get("elements", [])
                print(f"  {state_abbr}: {len(elements)} locations found (via {url})")
                return elements
            except Exception as e:
                wait = 5 * (attempt + 1)
                print(f"  {state_abbr}: attempt {attempt+1} failed ({e}) — retrying in {wait}s...")
                time.sleep(wait)
    print(f"  {state_abbr}: all endpoints failed — skipping")
    return []

def element_to_row(el):
    tags = el.get("tags", {})
    house = tags.get("addr:housenumber", "")
    street = tags.get("addr:street", "")
    city = tags.get("addr:city", "")
    state = tags.get("addr:state", "")
    zip_code = tags.get("addr:postcode", "")
    full_address = f"{house} {street}, {city}, {state} {zip_code}".strip(", ")
    return {
        "retailer": "kroger",
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
    sb.table("store_locations").insert(rows).execute()

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--state", type=str, default=None)
    args = parser.parse_args()

    if args.dry_run:
        print("[DRY RUN] Nothing will be written.\n")

    states = [s for s in STATE_BOXES if s[0] == args.state] if args.state else STATE_BOXES

    all_rows = []
    for entry in states:
        state_abbr = entry[0]
        bbox = entry[1:]
        print(f"Fetching {state_abbr}...")
        elements = fetch_kroger_for_state(state_abbr, bbox)
        for el in elements:
            if el.get("lat") and el.get("lon"):
                all_rows.append(element_to_row(el))
        time.sleep(3)

    print(f"\nTotal locations found: {len(all_rows)}")

    if args.dry_run:
        print("\nSample rows:")
        for r in all_rows[:5]:
            print(f"  {r['full_address']} → ({r['latitude']}, {r['longitude']})")
        print("\n[DRY RUN] Nothing was written.")
        return

    print("\nWriting to DB...")
    written = 0
    for i in range(0, len(all_rows), 50):
        batch = all_rows[i:i + 50]
        try:
            write_batch(batch)
            written += len(batch)
            print(f"  Written {written} / {len(all_rows)}...")
        except Exception as e:
            print(f"  Batch {i} failed: {e}")

    print(f"\nDone. {written} Kroger locations written to store_locations.")

if __name__ == "__main__":
    main()