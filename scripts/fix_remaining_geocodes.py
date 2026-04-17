# fix_remaining_geocodes.py
import time
import requests
import argparse
import pgeocode
from math import radians, cos, sin, asin, sqrt
from datetime import datetime, timezone
from config.supabase import get_supabase_client

# ── DB client ──────────────────────────────────────────────────────────────────
sb = get_supabase_client()
_pgeocode = pgeocode.Nominatim("us")

def now_iso():
    return datetime.now(timezone.utc).isoformat()

# ── Distance helper ────────────────────────────────────────────────────────────
def haversine_km(lat1, lon1, lat2, lon2):
    R = 6371
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)
    a = sin(dlat/2)**2 + cos(radians(lat1))*cos(radians(lat2))*sin(dlon/2)**2
    return R * 2 * asin(sqrt(a))

# ── Census Bureau geocoder ─────────────────────────────────────────────────────
CENSUS_URL = "https://geocoding.geo.census.gov/geocoder/locations/onelineaddress"
def geocode_census(address: str) -> tuple[float, float] | None:
    try:
        r = requests.get(CENSUS_URL, params={
            "address": address,
            "benchmark": "2020",
            "format": "json"
        }, timeout=10)
        r.raise_for_status()
        matches = r.json().get("result", {}).get("addressMatches", [])
        if matches:
            coords = matches[0]["coordinates"]
            return float(coords["y"]), float(coords["x"])
    except Exception:
        pass
    return None

# ── Photon geocoder ────────────────────────────────────────────────────────────
PHOTON_URL = "https://photon.komoot.io/api/"
def geocode_photon(address: str) -> tuple[float, float] | None:
    try:
        r = requests.get(PHOTON_URL, params={
            "q": address,
            "limit": 1,
            "lang": "en"
        }, timeout=10)
        r.raise_for_status()
        features = r.json().get("features", [])
        if features:
            coords = features[0]["geometry"]["coordinates"]
            return float(coords[1]), float(coords[0])
    except Exception:
        pass
    return None

# ── Geocode with fallbacks + ZIP guard ────────────────────────────────────────
def geocode_with_fallbacks(address: str, zip_code: str,
                            zip_lat: float, zip_lon: float,
                            max_km: float = 50.0,
                            dry_run: bool = False) -> tuple[float, float] | None:
    sources = [
        ("census", geocode_census),
        ("photon", geocode_photon),
    ]
    for name, fn in sources:
        result = fn(address)
        time.sleep(0.5)
        if result is None:
            print(f"    [{name}] no result")
            continue
        lat, lon = result
        dist = haversine_km(lat, lon, zip_lat, zip_lon)
        if dist > max_km:
            print(f"    [{name}] ({lat:.4f}, {lon:.4f}) is {dist:.0f} km from ZIP — rejecting")
            continue
        print(f"    [{name}] ({lat:.6f}, {lon:.6f})  dist={dist:.1f} km  [{'DRY RUN' if dry_run else 'WRITING'}]")
        return lat, lon
    return None

# ── ZIP centroid lookup ────────────────────────────────────────────────────────
def get_zip_centroid(zip_code: str):
    try:
        r = _pgeocode.query_postal_code(zip_code)
        lat, lng = r.latitude, r.longitude
        if lat and lng:
            return float(lat), float(lng)
    except Exception:
        pass
    return None, None

# ── Write fix to DB ────────────────────────────────────────────────────────────
def write_fix(row_id, lat, lng, dry_run):
    if dry_run:
        return
    sb.table("store_locations").update({
        "latitude":           lat,
        "longitude":          lng,
        "geocode_confidence": "high",
        "geocode_source":     "census_photon_refix",
        "geocoded_at":        now_iso(),
    }).eq("id", row_id).execute()

# ── Fetch failed rows from DB ──────────────────────────────────────────────────
def get_failed_rows():
    resp = sb.table("store_locations").select(
        "id, retailer, full_address, zip_code, latitude, longitude, geocode_confidence, geocode_source"
    ).eq("geocode_source", "nominatim").eq("geocode_confidence", "high").execute()
    rows = resp.data or []

    failed = []
    for row in rows:
        full_addr = (row.get("full_address") or "").strip()
        if not full_addr:
            continue
        zip_code = str(row.get("zip_code") or "").strip().zfill(5)
        zip_lat, zip_lon = get_zip_centroid(zip_code)
        if zip_lat is None:
            continue
        cur_lat = float(row["latitude"]) if row["latitude"] else None
        cur_lon = float(row["longitude"]) if row["longitude"] else None
        if cur_lat is None or cur_lon is None:
            failed.append(row)
            continue
        dist = haversine_km(cur_lat, cur_lon, zip_lat, zip_lon)
        if dist > 50.0:
            failed.append(row)
    return failed

# ── Main ───────────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args()

    if args.dry_run:
        print("[DRY RUN] Nothing will be written.\n")

    rows = get_failed_rows()
    if args.limit:
        rows = rows[:args.limit]

    print(f"Found {len(rows)} rows to attempt.\n")

    fixed = failed = 0
    for row in rows:
        full_addr = (row.get("full_address") or "").strip()
        zip_code  = str(row.get("zip_code") or "").strip().zfill(5)
        zip_lat, zip_lon = get_zip_centroid(zip_code)
        print(f"  id={row['id']} | {row.get('retailer')} | zip={zip_code}")
        print(f"    address: {full_addr}")

        result = geocode_with_fallbacks(
            full_addr, zip_code, zip_lat, zip_lon,
            max_km=50.0, dry_run=args.dry_run
        )
        if result:
            lat, lon = result
            tag = "[DRY RUN] " if args.dry_run else ""
            print(f"    {tag}[FIXED] ({lat:.6f}, {lon:.6f})")
            write_fix(row["id"], lat, lon, args.dry_run)
            fixed += 1
        else:
            print(f"    [FAIL] all geocoders failed -- row left unchanged")
            failed += 1

    print(f"\nCensus+Photon result: {fixed} fixed, {failed} failed")
    print(f"\n{'[DRY RUN] Nothing was written.' if args.dry_run else 'Done.'}")

if __name__ == "__main__":
    main()