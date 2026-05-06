"""
Retry geocoding for failed Publix stores using normalized highway names.
Usage:
    PYTHONUTF8=1 PYTHONPATH=. python scripts/geocode_publix_retry.py --dry-run
    PYTHONUTF8=1 PYTHONPATH=. python scripts/geocode_publix_retry.py
"""
import sys
import re
import time
import logging
import requests

sys.path.insert(0, ".")
from config.supabase import get_supabase_client
from data.publix_locations import publix_data

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)

DRY_RUN = "--dry-run" in sys.argv
HEADERS = {"User-Agent": "ProxApp/1.0 (grocery store locator)"}

def strip_suite(address):
    return re.sub(r'\s+(Ste|Suite|Unit|Apt|#|Bldg|Fl|Floor)\s+[\w-]+.*$', '', address, flags=re.IGNORECASE).strip()

def normalize_address(address):
    address = re.sub(r'\bHwy\b', 'Highway', address, flags=re.IGNORECASE)
    address = re.sub(r'\bUS[-\s]?Highway\b', 'US-', address, flags=re.IGNORECASE)
    address = re.sub(r'\bU\.S\.\s*Highway\b', 'US-', address, flags=re.IGNORECASE)
    address = re.sub(r'\bState Road\b', 'SR', address, flags=re.IGNORECASE)
    address = re.sub(r'\bGA[-\s]?Highway\b', 'GA-', address, flags=re.IGNORECASE)
    address = re.sub(r'\bGeorgia Highway\b', 'GA-', address, flags=re.IGNORECASE)
    address = re.sub(r'\bFL[-\s]?Highway\b', 'FL-', address, flags=re.IGNORECASE)
    address = re.sub(r'\bAL[-\s]?Highway\b', 'AL-', address, flags=re.IGNORECASE)
    address = re.sub(r'\bSuncoast Blvd\b', 'Suncoast Parkway', address, flags=re.IGNORECASE)
    address = re.sub(r'\bDr Martin Luther King Jr\b', 'Martin Luther King Jr Dr', address, flags=re.IGNORECASE)
    return address.strip()

def geocode_address(full_address):
    try:
        res = requests.get(
            "https://nominatim.openstreetmap.org/search",
            params={"q": full_address, "countrycodes": "us", "format": "json", "limit": 1},
            headers=HEADERS,
            timeout=15
        )
        data = res.json()
        if data:
            return float(data[0]["lat"]), float(data[0]["lon"])
    except Exception as e:
        logger.warning("Geocode error: %s", e)
    return None, None

def main():
    sb = get_supabase_client()

    # Get already-geocoded zips
    res = sb.table("store_locations").select("zip_code").eq("retailer_key", "publix").eq("geocode_source", "nominatim_refix").execute()
    geocoded_zips = {r["zip_code"] for r in res.data}
    logger.info("Already geocoded: %d zips", len(geocoded_zips))

    failed_stores = [s for s in publix_data if s["zip"][:5] not in geocoded_zips]
    logger.info("Retrying %d failed stores...", len(failed_stores))

    total_geocoded = 0
    total_failed = 0
    total_written = 0

    for i, store in enumerate(failed_stores):
        zip_code = store["zip"][:5]
        state = store["state"]
        street = normalize_address(strip_suite(store["street_address"]))
        city = store["city"]
        full_address = "%s, %s, %s %s" % (street, city, state, zip_code)

        lat, lon = geocode_address(full_address)
        time.sleep(1)

        if not lat or not lon:
            logger.warning("Failed: %s", full_address)
            total_failed += 1
            continue

        if not (24 < lat < 50 and -130 < lon < -65):
            logger.warning("Bad coords for %s: %s, %s", full_address, lat, lon)
            total_failed += 1
            continue

        total_geocoded += 1

        if DRY_RUN:
            logger.info("DRY RUN %s -> %s, %s", full_address, lat, lon)
            continue

        update_res = sb.table("store_locations") \
            .update({
                "latitude": lat,
                "longitude": lon,
                "full_address": full_address,
                "geocode_source": "nominatim_refix",
                "show_on_map": True,
            }) \
            .eq("retailer_key", "publix") \
            .eq("zip_code", zip_code) \
            .execute()

        if update_res.data:
            total_written += 1
        else:
            try:
                sb.table("store_locations").insert({
                    "retailer": "Publix",
                    "retailer_key": "publix",
                    "zip_code": zip_code,
                    "full_address": full_address,
                    "latitude": lat,
                    "longitude": lon,
                    "geocode_source": "nominatim_refix",
                    "show_on_map": True,
                }).execute()
                total_written += 1
            except Exception as e:
                logger.error("Insert failed for %s: %s", zip_code, e)

        if (i + 1) % 25 == 0:
            logger.info("Progress: %d/%d — geocoded %d, failed %d, written %d",
                        i+1, len(failed_stores), total_geocoded, total_failed, total_written)

    print("\nDone.")
    print("  Geocoded: %d" % total_geocoded)
    print("  Failed:   %d" % total_failed)
    print("  Written:  %d" % total_written)
    if DRY_RUN:
        print("\n[DRY RUN] Nothing was written.")

if __name__ == "__main__":
    main()