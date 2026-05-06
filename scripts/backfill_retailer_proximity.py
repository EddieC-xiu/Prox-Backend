# scripts/backfill_retailer_proximity.py
#
# For each user in waitlist, checks which of the 9 target retailers
# have at least one store within 10 miles of the user's zip code.
# Updates the nearby_* boolean columns on the waitlist table.
#
# Usage:
#   PYTHONPATH=. python scripts/backfill_retailer_proximity.py --dry-run
#   PYTHONPATH=. python scripts/backfill_retailer_proximity.py

import sys
import time
import logging
import math
from config.supabase import get_supabase_client

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)

DRY_RUN        = "--dry-run" in sys.argv
RADIUS_MILES   = 10.0
RETAILERS      = [
    "walmart", "aldi", "publix", "trader_joes",
    "target", "smart_final", "kroger", "ralphs", "vons"
]


def haversine_miles(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 3958.8
    lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
    return R * 2 * math.asin(math.sqrt(a))


def load_store_locations(client) -> dict[str, list[dict]]:
    """Load all store locations grouped by retailer_key — one retailer at a time."""
    logger.info("Loading store locations...")
    grouped = {}
    for retailer in RETAILERS:
        stores = []
        offset = 0
        while True:
            res = (
                client.table("store_locations")
                .select("latitude, longitude")
                .eq("retailer_key", retailer)
                .not_.is_("latitude", "null")
                .not_.is_("longitude", "null")
                .eq("show_on_map", True)
                .range(offset, offset + 999)
                .execute()
            )
            batch = res.data or []
            stores.extend(batch)
            if len(batch) < 1000:
                break
            offset += 1000
        if stores:
            grouped[retailer] = [
                {"lat": float(s["latitude"]), "lon": float(s["longitude"])}
                for s in stores
            ]
            logger.info(f"  {retailer}: {len(stores)} stores loaded")
        else:
            logger.info(f"  {retailer}: 0 stores loaded")
    return grouped


def load_zip_centroids(client) -> dict[str, dict]:
    """Load zip centroids with pagination."""
    logger.info("Loading zip centroids...")
    all_rows = []
    offset = 0
    while True:
        res = (
            client.table("zip_centroids")
            .select("zip_code, latitude, longitude")
            .range(offset, offset + 999)

            .execute()
        )
        batch = res.data or []
        all_rows.extend(batch)
        if len(batch) < 1000:
            break
        offset += 1000
    return {
        row["zip_code"]: {
            "lat": float(row["latitude"]),
            "lon": float(row["longitude"])
        }
        for row in all_rows
    }
    


def check_retailer_nearby(
    user_lat: float,
    user_lon: float,
    stores: list[dict],
    radius: float = RADIUS_MILES
) -> bool:
    for store in stores:
        if haversine_miles(user_lat, user_lon, store["lat"], store["lon"]) <= radius:
            return True
    return False


def main():
    client = get_supabase_client()

    store_map  = load_store_locations(client)
    zip_map    = load_zip_centroids(client)

    logger.info("Loading waitlist users...")
    res = (
        client.table("waitlist")
        .select("id, zip_code, location_latitude, location_longitude")
        .not_.is_("zip_code", "null")
        .execute()
    )
    users = res.data or []
    logger.info(f"Found {len(users)} users to process")

    total_updated = 0
    total_skipped = 0

    for user in users:
        zip_code = user.get("zip_code", "").strip()

        user_lat = user.get("location_latitude")
        user_lon = user.get("location_longitude")

        if not user_lat or not user_lon:
            centroid = zip_map.get(zip_code)
            if not centroid:
                logger.warning(f"No coordinates for user {user['id']} zip {zip_code} — skipping")
                total_skipped += 1
                continue
            user_lat = centroid["lat"]
            user_lon = centroid["lon"]

        payload = {}
        for retailer in RETAILERS:
            stores = store_map.get(retailer, [])
            if stores:
                payload[f"nearby_{retailer}"] = check_retailer_nearby(
                    float(user_lat), float(user_lon), stores
                )
            else:
                payload[f"nearby_{retailer}"] = False

        if DRY_RUN:
            logger.info(f"DRY RUN user {user['id']} zip {zip_code}: {payload}")
            total_updated += 1
            continue

        for attempt in range(3):
            try:
                client.table("waitlist").update(payload).eq("id", user["id"]).execute()
                total_updated += 1
                break
            except Exception as e:
                if attempt == 2:
                    logger.error(f"Failed to update user {user['id']}: {e}")
                    total_skipped += 1
                else:
                    time.sleep(2)

    print(f"\nDone.")
    print(f"  Updated: {total_updated}")
    print(f"  Skipped: {total_skipped}")
    if DRY_RUN:
        print("\n[DRY RUN] Nothing was written.")


if __name__ == "__main__":
    main()