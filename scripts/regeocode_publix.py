import re
import requests
import time
from config.supabase import supabase

# Publix only operates in the southeastern US
PUBLIX_LAT_BOUNDS = (24.0, 37.5)
PUBLIX_LON_BOUNDS = (-88.5, -75.0)

def clean_address(address):
    """Strip suite/unit/bldg suffixes that confuse Nominatim."""
    cleaned = re.sub(r'\s+(Ste|Suite|Unit|Apt|Bldg|Building|#)\s*\S*', '', address, flags=re.IGNORECASE)
    return cleaned.strip()

def is_valid_coordinate(lat, lon):
    """Check coordinate falls within Publix's operating region."""
    return (PUBLIX_LAT_BOUNDS[0] <= lat <= PUBLIX_LAT_BOUNDS[1] and
            PUBLIX_LON_BOUNDS[0] <= lon <= PUBLIX_LON_BOUNDS[1])

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
        print(f"  Error: {e}")
    return None, None

def geocode_with_fallback(address, zip_code):
    """Four attempts: original+zip, stripped+zip, original only, stripped only."""
    cleaned = clean_address(address)

    attempts = [
        (f"{address}, {zip_code}",   "original+zip"),
        (f"{cleaned}, {zip_code}",   "stripped+zip"),
        (address,                     "original"),
        (cleaned,                     "stripped"),
    ]

    # Deduplicate attempts (e.g. if clean_address didn't change anything)
    seen = set()
    deduped = []
    for query, label in attempts:
        if query not in seen:
            seen.add(query)
            deduped.append((query, label))

    for i, (query, label) in enumerate(deduped):
        if i > 0:
            time.sleep(1)  # respect Nominatim rate limit between retries
        lat, lon = geocode_address(query)
        if lat and lon:
            if is_valid_coordinate(lat, lon):
                return lat, lon, label
            else:
                print(f"  ⚠ Bad coordinate on '{label}' ({lat}, {lon}) — trying next")

    return None, None, None

def run():
    print("Fetching Publix stores with pgeocode source...")

    stores = supabase.table("store_locations")\
        .select("id, address, zip_code")\
        .eq("retailer_key", "publix")\
        .eq("geocode_source", "pgeocode")\
        .execute().data

    total = len(stores)
    print(f"Found {total} stores to re-geocode\n")

    success = 0
    failed = 0
    skipped = 0

    for i, store in enumerate(stores, 1):
        if not store["address"]:
            skipped += 1
            continue

        print(f"[{i}/{total}] {store['address']}")

        lat, lon, method = geocode_with_fallback(store["address"], store["zip_code"])

        if lat and lon:
            supabase.table("store_locations").update({
                "latitude": lat,
                "longitude": lon,
                "geocode_source": "nominatim",
                "geocode_confidence": "high",
                "geocoded_at": "now()"
            }).eq("id", store["id"]).execute()
            success += 1
            print(f"  ✓ ({lat}, {lon}) [{method}]")
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