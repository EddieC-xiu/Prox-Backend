import requests
import time
from config.supabase import supabase

ALBERTSONS_BANNERS = [
    "acmemarkets", "albertsons", "balduccis", "carrsqc",
    "haggen", "jewelosco", "kingsfoodmarkets", "randalls",
    "safeway", "shaws", "shopmarketstreet", "shopunitedsupermarkets",
    "starmarket", "tomthumb"
]

def geocode_address(address):
    url = "https://nominatim.openstreetmap.org/search"
    params = {"q": address, "format": "json", "limit": 1}
    headers = {"User-Agent": "prox-backend-sai"}
    try:
        response = requests.get(url, params=params, headers=headers, timeout=10)
        results = response.json()
        if results:
            return float(results[0]["lat"]), float(results[0]["lon"])
    except Exception as e:
        print(f"Error geocoding {address}: {e}")
    return None, None

def run():
    print("Fetching Albertsons-family stores with zip_centroid source...")

    stores = supabase.table("store_locations")\
        .select("id, address, zip_code, retailer_key")\
        .in_("retailer_key", ALBERTSONS_BANNERS)\
        .eq("geocode_source", "zip_centroid")\
        .execute().data

    total = len(stores)
    print(f"Found {total} stores to geocode\n")

    success = 0
    failed = 0
    skipped = 0

    for i, store in enumerate(stores, 1):
        if not store["address"]:
            skipped += 1
            continue

        print(f"[{i}/{total}] {store['retailer_key']} — {store['address']}")

        lat, lon = geocode_address(store["address"])

        if lat and lon:
            supabase.table("store_locations").update({
                "latitude": lat,
                "longitude": lon,
                "geocode_source": "nominatim",
                "geocode_confidence": "high",
                "geocoded_at": "now()"
            }).eq("id", store["id"]).execute()
            success += 1
            print(f"  ✓ ({lat}, {lon})")
        else:
            failed += 1
            print(f"  ✗ Could not geocode")

        time.sleep(1)

    print(f"\n--- Done ---")
    print(f"Total:    {total}")
    print(f"Success:  {success}")
    print(f"Failed:   {failed}")
    print(f"Skipped:  {skipped}")

if __name__ == "__main__":
    run()