import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import time
from dotenv import load_dotenv
from supabase import create_client
from services.geocoding_service import geocode_store
load_dotenv()

sb = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))


def get_zip_only_stores():
    """Get all stores currently sitting at zip_only confidence."""
    result = sb.table("store_locations").select(
        "id, retailer, zip_code, retailer_key, geocode_confidence"
    ).eq("geocode_confidence", "zip_only").execute()
    return result.data


def find_real_address(retailer: str, zip_code: str):
    """
    Look in flyer_deals_testing for a real address
    for this retailer + zip_code combo.
    Returns the first non-null address found, or None.
    """
    result = sb.table("flyer_deals_testing").select(
        "retailer_address"
    ).eq("retailer", retailer).eq("zip_code", zip_code).not_.is_(
        "retailer_address", "null"
    ).limit(1).execute()

    if result.data and result.data[0].get("retailer_address"):
        return result.data[0]["retailer_address"]
    return None


def upgrade_store(store: dict, address: str):
    """
    Re-geocode using the real address and update store_locations.
    Only upgrades if we get confidence=high back.
    """
    lat, lng, confidence = geocode_store(
        retailer=store["retailer"],
        zip_code=store["zip_code"],
        address=address
    )

    if confidence == "high" and lat and lng:
        sb.table("store_locations").update({
            "latitude": lat,
            "longitude": lng,
            "geocode_confidence": "high",
            "full_address": address,
        }).eq("id", store["id"]).execute()
        return True
    return False


def print_summary(total, upgraded, no_address, failed):
    print("\n" + "="*50)
    print("PHASE A UPGRADE SUMMARY")
    print("="*50)
    print(f"  Total zip_only stores found : {total}")
    print(f"  ✓ Upgraded to high          : {upgraded}")
    print(f"  ~ No address in DB          : {no_address}")
    print(f"  ✗ Geocoding failed          : {failed}")
    print(f"  zip_only remaining          : {total - upgraded}")
    print("="*50)


def main():
    print("Starting Phase A: upgrading zip_only stores using existing address data...\n")

    stores = get_zip_only_stores()
    total = len(stores)
    print(f"Found {total} zip_only stores to process\n")

    upgraded = 0
    no_address = 0
    failed = 0

    for i, store in enumerate(stores, 1):
        retailer = store["retailer"]
        zip_code = store["zip_code"]

        print(f"[{i}/{total}] {retailer} | zip: {zip_code}")

        # Step 1: look for a real address in our own DB
        address = find_real_address(retailer, zip_code)

        if not address:
            print(f"  ~ No address found in flyer_deals_testing, skipping")
            no_address += 1
            continue

        print(f"  Found address: {address}")

        # Step 2: re-geocode with the real address
        success = upgrade_store(store, address)

        if success:
            print(f"  ✓ Upgraded to high confidence")
            upgraded += 1
        else:
            print(f"  ✗ Geocoding failed, keeping zip_only")
            failed += 1

        time.sleep(1)  # Nominatim rate limit

    print_summary(total, upgraded, no_address, failed)


if __name__ == "__main__":
    main()