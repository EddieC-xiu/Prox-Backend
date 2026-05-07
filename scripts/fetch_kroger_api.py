"""
Fetch all Kroger-branded store locations from the official Kroger API.

Uses a lat/lon grid scan across the continental US + AK to ensure full coverage.
Only imports chain=KROGER stores (not banners like Harris Teeter, Fred Meyer, etc.)

Usage:
    python scripts/fetch_kroger_api.py [--dry-run]
"""
import sys
sys.path.insert(0, ".")

import time
import argparse
import requests
import base64
import os
from datetime import datetime, timezone
from dotenv import load_dotenv
from config.supabase import get_supabase_client

load_dotenv()

CLIENT_ID = os.getenv("KROGER_CLIENT_ID", "proxgrocerysavings-bbcdkn5r")
CLIENT_SECRET = os.getenv("KROGER_CLIENT_SECRET", "bBukLVfdPPKuichlKrxHPBP6fxiJg5S859AeUIiL")
API_BASE = "https://api.kroger.com/v1"

# Grid points covering continental US
# ~1.2 deg lat / 1.5 deg lon spacing (~85-100 miles), 75 mile search radius = full coverage
LAT_RANGE = (25.0, 49.0, 1.2)
LON_RANGE = (-124.0, -67.0, 1.5)


def get_token():
    creds = base64.b64encode(f"{CLIENT_ID}:{CLIENT_SECRET}".encode()).decode()
    resp = requests.post(
        f"{API_BASE}/connect/oauth2/token",
        headers={"Authorization": f"Basic {creds}", "Content-Type": "application/x-www-form-urlencoded"},
        data={"grant_type": "client_credentials", "scope": "product.compact"},
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json()["access_token"]


def fetch_locations_at(token, lat, lon, radius=100):
    stores = []
    start = 1
    while True:
        resp = requests.get(
            f"{API_BASE}/locations",
            headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
            params={
                "filter.latLng.near": f"{lat},{lon}",
                "filter.radiusInMiles": radius,
                "filter.limit": 200,
                "filter.start": start,
            },
            timeout=20,
        )
        if resp.status_code == 401:
            return None, True  # token expired
        if resp.status_code != 200:
            return stores, False
        data = resp.json()
        batch = data.get("data", [])
        for loc in batch:
            if loc.get("chain") == "KROGER":
                stores.append(loc)
        pagination = data.get("meta", {}).get("pagination", {})
        total = pagination.get("total", 0)
        if start + len(batch) - 1 >= total or not batch:
            break
        start += len(batch)
    return stores, False


def loc_to_row(loc):
    addr = loc.get("address", {})
    geo = loc.get("geolocation", {})
    zip_code = addr.get("zipCode", "")[:5]
    if not zip_code or not geo.get("latitude") or not geo.get("longitude"):
        return None
    address_line = addr.get("addressLine1", "")
    return {
        "retailer": "Kroger",
        "retailer_key": "kroger",
        "address": address_line or None,
        "city": addr.get("city") or None,
        "state": addr.get("state") or None,
        "zip_code": zip_code,
        "latitude": geo["latitude"],
        "longitude": geo["longitude"],
        "geocode_source": "kroger_api",
        "geocode_confidence": "exact",
        "show_on_map": True,
        "geocoded_at": datetime.now(timezone.utc).isoformat(),
    }


def build_grid():
    points = []
    lat = LAT_RANGE[0]
    while lat <= LAT_RANGE[1]:
        lon = LON_RANGE[0]
        while lon <= LON_RANGE[1]:
            points.append((round(lat, 2), round(lon, 2)))
            lon += LON_RANGE[2]
        lat += LAT_RANGE[2]
    return points


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if args.dry_run:
        print("[DRY RUN] Nothing will be written.\n")

    sb = get_supabase_client()
    grid = build_grid()
    print(f"Grid points: {len(grid)}")

    token = get_token()
    token_time = time.time()

    all_stores = {}  # locationId -> row, deduplication
    for i, (lat, lon) in enumerate(grid):
        # Refresh token every 25 min (expires in 30)
        if time.time() - token_time > 1500:
            token = get_token()
            token_time = time.time()

        stores, expired = fetch_locations_at(token, lat, lon, radius=75)
        if expired:
            token = get_token()
            token_time = time.time()
            stores, _ = fetch_locations_at(token, lat, lon, radius=75)

        for loc in (stores or []):
            loc_id = loc.get("locationId")
            if loc_id and loc_id not in all_stores:
                row = loc_to_row(loc)
                if row:
                    all_stores[loc_id] = row

        if (i + 1) % 20 == 0:
            print(f"  Grid {i+1}/{len(grid)} — unique Kroger stores found: {len(all_stores)}")
        time.sleep(0.3)

    print(f"\nTotal unique Kroger stores: {len(all_stores)}")
    rows = list(all_stores.values())

    if args.dry_run:
        print(f"[DRY RUN] Would upsert {len(rows)} stores.")
        for r in rows[:5]:
            print(f"  {r['address']}, {r['city']}, {r['state']} {r['zip_code']} ({r['latitude']}, {r['longitude']})")
        return

    # Upsert — use location's lat/lon as source of truth, overwrite existing rows
    print(f"\nUpserting {len(rows)} stores to DB...")
    written = 0
    for i in range(0, len(rows), 50):
        batch = rows[i:i+50]
        try:
            sb.table("store_locations").upsert(
                batch,
                ignore_duplicates=False,
                on_conflict="retailer_key,zip_code",
            ).execute()
            written += len(batch)
        except Exception as e:
            # Fall back row-by-row on conflict errors
            for row in batch:
                try:
                    sb.table("store_locations").upsert(
                        [row], ignore_duplicates=False, on_conflict="retailer_key,zip_code"
                    ).execute()
                    written += 1
                except Exception:
                    pass

    print(f"Done. {written}/{len(rows)} rows written to DB.")


if __name__ == "__main__":
    main()
