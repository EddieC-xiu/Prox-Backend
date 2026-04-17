import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from dotenv import load_dotenv
from supabase import create_client
from services.geocoding_service import geocode_store

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)


def get_unique_stores():
    """Pull unique retailer + zip_code + retailer_address combos from flyer_deals_testing."""
    response = supabase.table("flyer_deals_testing").select(
        "retailer, zip_code, retailer_address"
    ).execute()

    seen = set()
    stores = []
    for row in response.data:
        retailer = (row.get("retailer") or "").strip().lower()
        zip_code = (row.get("zip_code") or "").strip()
        address = row.get("retailer_address")

        key = (retailer, zip_code)
        if retailer and zip_code and key not in seen:
            seen.add(key)
            stores.append({
                "retailer": retailer,
                "zip_code": zip_code,
                "address": address,
            })
    return stores


def upsert_store(store: dict, lat, lng, confidence: str):
    supabase.table("store_locations").upsert({
        "retailer": store["retailer"],
        "zip_code": store["zip_code"],
        "address": store["address"],
        "latitude": lat,
        "longitude": lng,
        "geocode_confidence": confidence,
        "geocode_source": "nominatim",
    }, on_conflict="retailer,zip_code").execute()


def main():
    stores = get_unique_stores()
    print(f"Found {len(stores)} unique stores\n")

    geocoded = 0
    failed = 0

    for i, store in enumerate(stores, 1):
        print(f"[{i}/{len(stores)}] {store['retailer']} | zip: {store['zip_code']} | address: {store['address']}")
        lat, lng, confidence = geocode_store(
            retailer=store["retailer"],
            zip_code=store["zip_code"],
            address=store["address"],
        )

        if lat and lng:
            upsert_store(store, lat, lng, confidence)
            print(f"  ✓ lat={lat:.6f}, lng={lng:.6f} | confidence={confidence}")
            geocoded += 1
        else:
            upsert_store(store, None, None, "failed")
            print(f"  ✗ Failed — marked as 'failed' in table")
            failed += 1

    print(f"\n--- Done: {geocoded} geocoded, {failed} failed ---")


if __name__ == "__main__":
    main()