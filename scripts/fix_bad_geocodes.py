#!/usr/bin/env python3
"""
scripts/fix_bad_geocodes.py

Identifies and re-geocodes bad rows in store_locations across three tiers:

  Tier 1  nominatim+high rows OUTSIDE US bounding box (excl. AK/HI)
  Tier 2  nominatim+high rows inside US but >50 km from their ZIP centroid
          (wrong-city matches -- e.g. Chicago store geocoded to Montana)
  Tier 3  zip / zip_centroid rows (certain centroids)

Fix strategy:
  Tiers 1+2 -> re-geocode using full_address (already has city+state+zip)
               new result is ZIP-proximity-validated before accepting
  Tier 3    -> re-geocode using retailer name + zip via Nominatim

Fixes vs original:
  1. Alaska/Hawaii bounding boxes added -- AK/HI stores no longer falsely
     flagged as "outside US".
  2. Pagination -- fetches all rows past Supabase's 1,000-row default cap.
  3. ZIP proximity validation on re-geocoded results -- prevents accepting
     a new wrong-city match (e.g. "Hwy 16, Emmett, ID" -> California).

Usage:
  PYTHONPATH=. python scripts/fix_bad_geocodes.py --dry-run
  PYTHONPATH=. python scripts/fix_bad_geocodes.py
  PYTHONPATH=. python scripts/fix_bad_geocodes.py --tier 1 --dry-run
  PYTHONPATH=. python scripts/fix_bad_geocodes.py --tier 3 --limit 50
"""

import argparse
import math
import time
from datetime import datetime, timezone

import pgeocode
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut, GeocoderServiceError

from config.supabase import get_supabase_client

# -- Constants -----------------------------------------------------------------
# Contiguous US
US_LAT_MIN, US_LAT_MAX =  24.0,  49.5
US_LNG_MIN, US_LNG_MAX = -125.0, -66.0
# Alaska  (longitude runs ~-130 to -168W -- entirely west of -125)
AK_LAT_MIN, AK_LAT_MAX =  51.0,  72.0
AK_LNG_MIN, AK_LNG_MAX = -170.0, -129.0
# Hawaii
HI_LAT_MIN, HI_LAT_MAX =  18.0,  23.0
HI_LNG_MIN, HI_LNG_MAX = -162.0, -154.5

ZIP_DISTANCE_THRESHOLD_KM = 50.0
NOMINATIM_DELAY           =  1.1

# -- Singletons ----------------------------------------------------------------
sb          = get_supabase_client()
_pgeocode   = pgeocode.Nominatim('us')
_geolocator = Nominatim(user_agent="prox-backend-fix-geocodes-v1")


# -- Helpers -------------------------------------------------------------------

def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (math.sin(dlat / 2) ** 2
         + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2))
         * math.sin(dlon / 2) ** 2)
    return R * 2 * math.asin(math.sqrt(a))


def is_in_us(lat, lng) -> bool:
    if lat is None or lng is None:
        return False
    lat, lng = float(lat), float(lng)
    if US_LAT_MIN <= lat <= US_LAT_MAX and US_LNG_MIN <= lng <= US_LNG_MAX:
        return True
    if AK_LAT_MIN <= lat <= AK_LAT_MAX and AK_LNG_MIN <= lng <= AK_LNG_MAX:
        return True
    if HI_LAT_MIN <= lat <= HI_LAT_MAX and HI_LNG_MIN <= lng <= HI_LNG_MAX:
        return True
    return False


def get_zip_centroid(zip_code: str):
    try:
        r = _pgeocode.query_postal_code(zip_code)
        lat, lng = r.latitude, r.longitude
        if lat and lng and not math.isnan(lat) and not math.isnan(lng):
            return float(lat), float(lng)
    except Exception:
        pass
    return None, None


def nominatim_geocode(query: str):
    try:
        time.sleep(NOMINATIM_DELAY)
        loc = _geolocator.geocode(query, timeout=10, country_codes="us")
        if loc and is_in_us(loc.latitude, loc.longitude):
            return float(loc.latitude), float(loc.longitude)
    except (GeocoderTimedOut, GeocoderServiceError) as e:
        print(f"    [WARN] Nominatim error: {e}")
    return None, None


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# -- Classification ------------------------------------------------------------

def classify_nominatim_row(row: dict) -> tuple:
    lat = float(row["latitude"]) if row["latitude"] else None
    lng = float(row["longitude"]) if row["longitude"] else None

    if not is_in_us(lat, lng):
        return "outside_us", None

    zip_lat, zip_lng = get_zip_centroid(row.get("zip_code", ""))
    if zip_lat and zip_lng:
        dist = haversine_km(lat, lng, zip_lat, zip_lng)
        if dist > ZIP_DISTANCE_THRESHOLD_KM:
            return "wrong_city", round(dist, 1)
        return "ok", round(dist, 1)

    return "ok", None


# -- Geocoding strategies ------------------------------------------------------

def regeocode_from_full_address(row: dict) -> tuple:
    zip_code = (row.get("zip_code") or "").strip()
    zip_lat, zip_lng = get_zip_centroid(zip_code)

    def accept(lat, lng, confidence):
        if not (lat and lng):
            return None, None, "failed"
        if zip_lat and zip_lng:
            dist = haversine_km(lat, lng, zip_lat, zip_lng)
            if dist > ZIP_DISTANCE_THRESHOLD_KM:
                print(f"    [WARN] New result ({lat:.4f}, {lng:.4f}) is {dist:.0f} km "
                      f"from ZIP centroid -- rejecting, trying next strategy")
                return None, None, "failed"
        return lat, lng, confidence

    # Strategy 1: full_address as-is
    full_addr = (row.get("full_address") or "").strip()
    if full_addr:
        lat, lng = nominatim_geocode(full_addr)
        result = accept(lat, lng, "high")
        if result[0]:
            return result

        # Strategy 2: full_address with ", USA" appended
        lat, lng = nominatim_geocode(f"{full_addr}, USA")
        result = accept(lat, lng, "high")
        if result[0]:
            return result

    # Strategy 3: street + zip only
    address = (row.get("address") or "").strip()
    if address and zip_code:
        lat, lng = nominatim_geocode(f"{address}, {zip_code}, USA")
        result = accept(lat, lng, "medium")
        if result[0]:
            return result

    return None, None, "failed"


def regeocode_from_retailer_zip(row: dict) -> tuple:
    retailer = row.get("retailer", "").title()
    zip_code = (row.get("zip_code") or "").strip()
    zip_lat, zip_lng = get_zip_centroid(zip_code)

    if retailer and zip_code:
        lat, lng = nominatim_geocode(f"{retailer}, {zip_code}, USA")
        if lat and lng:
            if zip_lat and zip_lng:
                dist = haversine_km(lat, lng, zip_lat, zip_lng)
                if dist > ZIP_DISTANCE_THRESHOLD_KM:
                    print(f"    [WARN] Result ({lat:.4f}, {lng:.4f}) is {dist:.0f} km "
                          f"from ZIP centroid -- rejecting")
                    return None, None, "failed"
            return lat, lng, "high"

    return None, None, "failed"


# -- DB helpers ----------------------------------------------------------------

def fetch_all_pages(query_builder) -> list:
    all_rows  = []
    page_size = 1000
    page      = 0
    while True:
        result = query_builder.range(
            page * page_size, (page + 1) * page_size - 1
        ).execute()
        all_rows.extend(result.data)
        if len(result.data) < page_size:
            break
        page += 1
    return all_rows


def fetch_nominatim_high_rows() -> list:
    q = sb.table("store_locations").select(
        "id, retailer, retailer_key, address, zip_code, "
        "latitude, longitude, full_address"
    ).eq("geocode_source", "nominatim").eq("geocode_confidence", "high")
    return fetch_all_pages(q)


def fetch_zip_centroid_rows() -> list:
    q = sb.table("store_locations").select(
        "id, retailer, retailer_key, zip_code, latitude, longitude, "
        "geocode_confidence, geocode_source"
    ).in_("geocode_confidence", ["zip", "zip_centroid"])
    return fetch_all_pages(q)


def write_fix(row_id: int, lat: float, lng: float,
              confidence: str, dry_run: bool) -> None:
    if dry_run:
        return
    sb.table("store_locations").update({
        "latitude":           lat,
        "longitude":          lng,
        "geocode_confidence": confidence,
        "geocode_source":     "nominatim_refix",
        "geocoded_at":        now_iso(),
    }).eq("id", row_id).execute()


# -- Main ----------------------------------------------------------------------

def run_tiers_1_and_2(args):
    print("=" * 60)
    print("TIERS 1+2  nominatim+high rows")
    print("=" * 60)

    rows = fetch_nominatim_high_rows()
    print(f"Fetched {len(rows)} nominatim+high rows -- classifying...\n")

    outside_us = []
    wrong_city = []
    ok_rows    = []

    for row in rows:
        status, dist = classify_nominatim_row(row)
        if   status == "outside_us": outside_us.append((row, dist))
        elif status == "wrong_city": wrong_city.append((row, dist))
        else:                        ok_rows.append((row, dist))

    print(f"  Outside US bounds              : {len(outside_us)}")
    print(f"  Wrong city (>{ZIP_DISTANCE_THRESHOLD_KM} km from ZIP) : {len(wrong_city)}")
    print(f"  Likely OK                      : {len(ok_rows)}")
    print()

    to_fix = []
    if args.tier in (None, 1): to_fix += [(r, "outside_us", d) for r, d in outside_us]
    if args.tier in (None, 2): to_fix += [(r, "wrong_city", d) for r, d in wrong_city]

    if args.limit:
        to_fix = to_fix[:args.limit]

    fixed = failed = skipped = 0

    for row, reason, dist in to_fix:
        dist_str = f" ({dist} km from ZIP)" if dist else ""
        print(f"  [{reason}{dist_str}] id={row['id']} | {row['retailer']} | zip={row['zip_code']}")
        print(f"    current  : ({row['latitude']}, {row['longitude']})")
        print(f"    query    : {row.get('full_address') or row.get('address')}")

        if not row.get("full_address") and not row.get("address"):
            print(f"    [SKIP] no address data at all")
            skipped += 1
            continue

        lat, lng, confidence = regeocode_from_full_address(row)

        if lat and lng:
            tag = "[DRY RUN] " if args.dry_run else ""
            print(f"    {tag}[FIXED] ({lat:.6f}, {lng:.6f})  confidence={confidence}")
            write_fix(row["id"], lat, lng, confidence, args.dry_run)
            fixed += 1
        else:
            print(f"    [FAIL] re-geocoding failed -- row left unchanged")
            failed += 1

    print(f"\nTier 1+2 result: {fixed} fixed, {failed} failed, {skipped} skipped\n")
    return fixed, failed, skipped


def run_tier_3(args):
    print("=" * 60)
    print("TIER 3  zip / zip_centroid rows")
    print("=" * 60)

    rows = fetch_zip_centroid_rows()
    print(f"Fetched {len(rows)} rows with confidence in (zip, zip_centroid)\n")

    if args.limit:
        rows = rows[:args.limit]

    fixed = failed = 0

    for row in rows:
        print(f"  id={row['id']} | {row['retailer']} | zip={row['zip_code']} "
              f"| source={row['geocode_source']}")

        lat, lng, confidence = regeocode_from_retailer_zip(row)

        if lat and lng:
            tag = "[DRY RUN] " if args.dry_run else ""
            print(f"    {tag}[FIXED] ({lat:.6f}, {lng:.6f})  confidence={confidence}")
            write_fix(row["id"], lat, lng, confidence, args.dry_run)
            fixed += 1
        else:
            print(f"    [FAIL] failed -- row left unchanged")
            failed += 1

    print(f"\nTier 3 result: {fixed} fixed, {failed} failed\n")
    return fixed, failed


def main():
    parser = argparse.ArgumentParser(
        description="Re-geocode bad store_locations rows")
    parser.add_argument("--dry-run", action="store_true",
                        help="Classify and report without writing any changes")
    parser.add_argument("--tier", type=int, choices=[1, 2, 3],
                        help="Run only a specific tier (default: all)")
    parser.add_argument("--limit", type=int,
                        help="Cap the number of rows fixed per tier (for testing)")
    args = parser.parse_args()

    if args.dry_run:
        print("[DRY RUN] No DB writes will occur\n")

    t1_fixed = t1_failed = t1_skipped = 0
    t3_fixed = t3_failed = 0

    if args.tier in (None, 1, 2):
        t1_fixed, t1_failed, t1_skipped = run_tiers_1_and_2(args)

    if args.tier in (None, 3):
        t3_fixed, t3_failed = run_tier_3(args)

    print("=" * 60)
    print("OVERALL SUMMARY")
    print("=" * 60)
    print(f"  Tiers 1+2 fixed   : {t1_fixed}")
    print(f"  Tiers 1+2 failed  : {t1_failed}")
    print(f"  Tiers 1+2 skipped : {t1_skipped}")
    print(f"  Tier 3 fixed      : {t3_fixed}")
    print(f"  Tier 3 failed     : {t3_failed}")
    print(f"  Total fixed       : {t1_fixed + t3_fixed}")
    if args.dry_run:
        print("\n  [DRY RUN] Nothing was written.")
    print("=" * 60)


if __name__ == "__main__":
    main()