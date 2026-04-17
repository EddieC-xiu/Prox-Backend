import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from data.kroger_data import kroger_data
from supabase import create_client
from dotenv import load_dotenv
from datetime import datetime, timezone
import pgeocode
import math
import time

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

def import_kroger_stores():
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
    nomi = pgeocode.Nominatim('us')

    inserted = 0
    updated = 0
    skipped = 0
    errors = 0
    total = len(kroger_data)

    print(f"Starting Kroger import: {total} stores to process...")

    for i, (zip_code, store_id) in enumerate(kroger_data.items(), 1):
        try:
            geo = nomi.query_postal_code(zip_code)
            lat = float(geo.latitude)
            lon = float(geo.longitude)

            if math.isnan(lat) or math.isnan(lon):
                print(f"  [{i}/{total}] ZIP {zip_code}: no geocode result, skipping")
                skipped += 1
                continue

            city  = None if str(geo.place_name) == 'nan' else str(geo.place_name)
            state = None if str(geo.state_code)  == 'nan' else str(geo.state_code)

            full_address = f"{city}, {state} {zip_code}" if city and state else zip_code

            existing = supabase.table("store_locations") \
                .select("id") \
                .eq("retailer", "Kroger") \
                .eq("store_id", str(store_id)) \
                .execute()

            if existing.data:
                supabase.table("store_locations") \
                    .update({
                        "zip_code":           zip_code,
                        "full_address":       full_address,
                        "latitude":           lat,
                        "longitude":          lon,
                        "geocode_confidence": "zip_centroid",
                        "geocode_source":     "pgeocode",
                        "geocoded_at":        datetime.now(timezone.utc).isoformat(),
                    }) \
                    .eq("id", existing.data[0]["id"]) \
                    .execute()
                updated += 1
            else:
                supabase.table("store_locations").insert({
                    "retailer":           "Kroger",
                    "retailer_key":       "kroger",
                    "store_id":           str(store_id),
                    "zip_code":           zip_code,
                    "full_address":       full_address,
                    "latitude":           lat,
                    "longitude":          lon,
                    "geocode_confidence": "zip_centroid",
                    "geocode_source":     "pgeocode",
                    "geocoded_at":        datetime.now(timezone.utc).isoformat(),
                }).execute()
                inserted += 1

            if i % 100 == 0 or i == total:
                print(f"  [{i}/{total}] ZIP {zip_code} → store {store_id}")

        except Exception as e:
            print(f"  [{i}/{total}] ERROR on ZIP {zip_code}: {e}")
            errors += 1

        if i % 200 == 0:
            time.sleep(0.3)

    print(f"\n{'='*40}")
    print(f"  Kroger Import Complete")
    print(f"  Inserted : {inserted}")
    print(f"  Updated  : {updated}")
    print(f"  Skipped  : {skipped}")
    print(f"  Errors   : {errors}")
    print(f"  Total    : {total}")
    print(f"{'='*40}")

if __name__ == "__main__":
    import_kroger_stores()