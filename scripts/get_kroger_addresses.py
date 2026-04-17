import requests
import time
from config.supabase import supabase

def geocode_kroger_by_zip(zip_code):
    url = "https://nominatim.openstreetmap.org/search"
    params = {
        "q": f"Kroger {zip_code}",
        "format": "json",
        "limit": 1,
        "countrycodes": "us"
    }
    headers = {"User-Agent": "prox-backend-sai"}
    try:
        response = requests.get(url, params=params, headers=headers, timeout=10)
        results = response.json()
        if results:
            r = results[0]
            return float(r["lat"]), float(r["lon"])
    except Exception as e:
        print(f"  Error for ZIP {zip_code}: {e}")
    return None, None

def run():
    print("Fetching Kroger stores with no address...")

    stores = supabase.table("store_locations")\
    .select("id, store_id, zip_code")\
    .eq("retailer_key", "kroger")\
    .eq("geocode_source", "pgeocode")\
    .limit(2000)\
    .execute().data

    total = len(stores)
    print(f"Found {total} Kroger stores to geocode\n")

    found = 0
    not_found = 0
    skipped = 0

    for i, store in enumerate(stores, 1):
        if not store["zip_code"]:
            skipped += 1
            print(f"[{i}/{total}] No ZIP — skipping")
            continue

        print(f"[{i}/{total}] ZIP {store['zip_code']}")

        lat, lon = geocode_kroger_by_zip(store["zip_code"])

        if lat and lon:
            supabase.table("store_locations").update({
                "latitude": lat,
                "longitude": lon,
                "geocode_source": "nominatim",
                "geocode_confidence": "medium",
                "geocoded_at": "now()"
            }).eq("id", store["id"]).execute()
            found += 1
            print(f"  ✓ ({lat}, {lon})")
        else:
            not_found += 1
            print(f"  ✗ Not found")

        time.sleep(1)

    print(f"\n--- Done ---")
    print(f"Total:      {total}")
    print(f"Found:      {found}")
    print(f"Not found:  {not_found}")
    print(f"Skipped:    {skipped}")

if __name__ == "__main__":
    run()