"""
Geocodes Publix store addresses via Nominatim and updates store_locations.
Usage:
    PYTHONPATH=. python scripts/geocode_publix.py --dry-run
    PYTHONPATH=. python scripts/geocode_publix.py
"""
import sys
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

# Publix operates in Southeast US + KY + VA + NC
VALID_STATES = {"FL","GA","SC","NC","TN","AL","VA","KY","MS","IN","OH"}
import re

def strip_suite(address):
    """Remove suite/unit/apt numbers that confuse Nominatim."""
    return re.sub(r'\s+(Ste|Suite|Unit|Apt|#|Bldg|Fl|Floor)\s+[\w-]+.*$', '', address, flags=re.IGNORECASE).strip()

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
    logger.info("Geocoding %d Publix stores...", len(publix_data))

    total_geocoded = 0
    total_failed = 0
    total_written = 0

    for i, store in enumerate(publix_data):
        zip_code = store["zip"][:5]
        state = store["state"]
        street = store["street_address"]
        city = store["city"]
        full_address = "%s, %s, %s %s" % (strip_suite(street), city, state, zip_code)

        lat, lon = geocode_address(full_address)
        time.sleep(1)

        if not lat or not lon:
            logger.warning("Failed: %s", full_address)
            total_failed += 1
            continue

        # Sanity check — must be in US and valid state
        if not (24 < lat < 50 and -130 < lon < -65):
            logger.warning("Bad coords for %s: %s, %s", full_address, lat, lon)
            total_failed += 1
            continue

        total_geocoded += 1

        if DRY_RUN:
            logger.info("DRY RUN %s -> %s, %s", full_address, lat, lon)
            continue

        res = sb.table("store_locations") \
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

        if res.data:
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

        if (i + 1) % 50 == 0:
            logger.info("Progress: %d/%d — geocoded %d, failed %d, written %d",
                        i+1, len(publix_data), total_geocoded, total_failed, total_written)

    print("\nDone.")
    print("  Geocoded: %d" % total_geocoded)
    print("  Failed:   %d" % total_failed)
    print("  Written:  %d" % total_written)
    if DRY_RUN:
        print("\n[DRY RUN] Nothing was written.")

if __name__ == "__main__":
    main()