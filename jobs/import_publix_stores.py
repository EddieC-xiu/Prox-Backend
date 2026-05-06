import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from data.publix_locations import publix_data
from supabase import create_client
from dotenv import load_dotenv
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut, GeocoderServiceError
from datetime import datetime, timezone
import pgeocode
import re
import time

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

geolocator = Nominatim(user_agent="prox-backend-sai")
nomi = pgeocode.Nominatim("us")

def clean_zip(zip_str):
    return str(zip_str).split("-")[0].strip()

def strip_suite(address):
    """Remove suite/unit/apt suffixes so Nominatim has a better shot."""
    return re.sub(r'\s+(Ste|Suite|Unit|Apt|#)\s+\S+', '', address, flags=re.IGNORECASE).strip()

def geocode_with_nominatim(address_str):
    """Try Nominatim, return (lat, lon) or (None, None)."""
    try:
        location = geolocator.geocode(address_str, timeout=10, country_codes="us")
        if location:
            return location.latitude, location.longitude
    except (GeocoderTimedOut, GeocoderServiceError):
        time.sleep(2)
        try:
            location = geolocator.geocode(address_str, timeout=15, country_codes="us")
            if location:
                return location.latitude, location.longitude
        except Exception:
            pass
    return None, None

def geocode_store(store, zip_code):
    """
    Three-tier geocoding:
      1. Full address via Nominatim         → confidence: high
      2. Street (no suite) via Nominatim    → confidence: high
      3. ZIP centroid via pgeocode          → confidence: zip_centroid
    Returns (lat, lon, confidence, source)
    """
    full = f"{store['street_address']}, {store['city']}, {store['state']} {zip_code}"
    lat, lon = geocode_with_nominatim(full)
    if lat:
        return lat, lon, "high", "nominatim"
    time.sleep(1.1)

    # Retry without suite number
    stripped = strip_suite(store["street_address"])
    if stripped != store["street_address"]:
        short = f"{stripped}, {store['city']}, {store['state']} {zip_code}"
        lat, lon = geocode_with_nominatim(short)
        if lat:
            return lat, lon, "high", "nominatim"
        time.sleep(1.1)

    # ZIP centroid fallback
    result = nomi.query_postal_code(zip_code)
    if result is not None and not (result.latitude != result.latitude):  # NaN check
        return float(result.latitude), float(result.longitude), "zip_centroid", "pgeocode"

    return None, None, None, None

def import_publix_stores():
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

    inserted = 0
    updated = 0
    skipped = 0
    errors = 0
    total = len(publix_data)

    print(f"Starting Publix import: {total} stores")
    print("Geocoding via Nominatim (with pgeocode fallback)\n")

    for i, store in enumerate(publix_data, 1):
        try:
            zip_code = clean_zip(store["zip"])
            lat, lon, confidence, source = geocode_store(store, zip_code)

            if lat is None:
                print(f"  [{i}/{total}] SKIPPED store {store['store_id']} — all geocoding failed: {store['street_address']}, {store['city']}")
                skipped += 1
                time.sleep(1)
                continue

            full_address = f"{store['street_address']}, {store['city']}, {store['state']} {zip_code}"

            record = {
                "retailer":           "Publix",
                "retailer_key":       "publix",
                "store_id":           str(store["store_id"]),
                "address":            store["street_address"],
                "full_address":       full_address,
                "zip_code":           zip_code,
                "latitude":           lat,
                "longitude":          lon,
                "geocode_confidence": confidence,
                "geocode_source":     source,
                "geocoded_at":        datetime.now(timezone.utc).isoformat(),
            }

            existing = supabase.table("store_locations") \
                .select("id") \
                .eq("retailer", "Publix") \
                .eq("store_id", str(store["store_id"])) \
                .execute()

            if existing.data:
                supabase.table("store_locations") \
                    .update(record) \
                    .eq("id", existing.data[0]["id"]) \
                    .execute()
                updated += 1
                action = "updated"
            else:
                supabase.table("store_locations").insert(record).execute()
                inserted += 1
                action = "inserted"

            if i % 25 == 0 or i == total:
                print(f"  [{i}/{total}] {action} — {store['city']}, {store['state']} ({confidence})")

            time.sleep(1.1)

        except Exception as e:
            print(f"  [{i}/{total}] ERROR store {store.get('store_id')}: {e}")
            errors += 1
            time.sleep(1)

    print(f"\n{'='*40}")
    print(f"  Publix Import Complete")
    print(f"  Inserted : {inserted}")
    print(f"  Updated  : {updated}")
    print(f"  Skipped  : {skipped}  (total geocode failure)")
    print(f"  Errors   : {errors}")
    print(f"  Total    : {total}")
    print(f"{'='*40}")

if __name__ == "__main__":
    import_publix_stores()