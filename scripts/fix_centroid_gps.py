"""
Re-import real GPS from OSM for retailers where most entries are zip_centroid.
Upserts on retailer_key+zip_code, upgrading centroid entries with real coordinates.
"""
import sys, os, time, logging, requests
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from config.supabase import get_supabase_client

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)
sb = get_supabase_client()

# Retailers to re-import: (osm_search_name, retailer_key, display_name)
TARGETS = [
    ("Bristol Farms",     "bristolfarms",     "Bristol Farms"),
    ("Gelson's",          "gelsons",          "Gelson's"),
    ("Superior Grocers",  "superiorgrocers",  "Superior Grocers"),
    ("Northgate Market",  "northgate",        "Northgate Market"),
    ("Restaurant Depot",  "restaurantdepot",  "Restaurant Depot"),
    ("Erewhon",           "erewhon",          "Erewhon"),
]

OVERPASS_URLS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass.openstreetmap.ru/api/interpreter",
]

US_LAT_MIN, US_LAT_MAX = 24.0, 49.5
US_LNG_MIN, US_LNG_MAX = -125.0, -66.0


def query_osm(osm_name: str) -> list[dict]:
    query = f'[out:json][timeout:90];(node["name"~"{osm_name}",i]["shop"];way["name"~"{osm_name}",i]["shop"];);out center;'
    for url in OVERPASS_URLS:
        for attempt in range(3):
            try:
                if attempt > 0:
                    time.sleep(10 * (2 ** attempt))
                logger.info(f"  Querying {url}...")
                resp = requests.post(url, data={"data": query}, timeout=120, headers={"User-Agent": "prox-backend/1.0"})
                if resp.status_code == 200:
                    elements = resp.json().get("elements", [])
                    logger.info(f"  Got {len(elements)} OSM results for '{osm_name}'")
                    return elements
                elif resp.status_code in (429, 504):
                    logger.warning(f"  Rate limited ({resp.status_code})")
                    continue
                else:
                    logger.warning(f"  HTTP {resp.status_code}")
                    break
            except Exception as e:
                logger.warning(f"  {url} failed: {e}")
                break
        time.sleep(5)
    return []


def parse_location(el: dict) -> dict | None:
    if el["type"] == "node":
        lat, lon = el.get("lat"), el.get("lon")
    elif el["type"] == "way":
        center = el.get("center", {})
        lat, lon = center.get("lat"), center.get("lon")
    else:
        return None
    if not lat or not lon:
        return None
    if not (US_LAT_MIN <= lat <= US_LAT_MAX and US_LNG_MIN <= lon <= US_LNG_MAX):
        return None  # skip non-US entries
    tags = el.get("tags", {})
    raw_zip = tags.get("addr:postcode", "") or ""
    zip_code = raw_zip[:5]
    return {
        "lat": lat, "lon": lon,
        "name": tags.get("name", ""),
        "address": tags.get("addr:street", ""),
        "city": tags.get("addr:city", ""),
        "state": tags.get("addr:state", ""),
        "zip_code": zip_code,
        "osm_id": str(el.get("id", "")),
    }


def main():
    total_upserted = 0
    for osm_name, retailer_key, display_name in TARGETS:
        logger.info(f"\n{'='*60}")
        logger.info(f"Importing {display_name} ({retailer_key})")

        # Check current state
        existing = sb.table("store_locations").select("id, zip_code, geocode_confidence").eq("retailer_key", retailer_key).execute().data or []
        real_before = sum(1 for r in existing if r.get("geocode_confidence") not in ("zip_centroid", "zip") and r.get("geocode_confidence") is not None)
        logger.info(f"  Before: {len(existing)} total, {real_before} real GPS")

        elements = query_osm(osm_name)
        time.sleep(15)

        locations = []
        for el in elements:
            loc = parse_location(el)
            if not loc:
                continue
            if not loc["zip_code"]:
                continue  # skip entries without zip — can't upsert without conflict key
            locations.append({
                "retailer":           display_name,
                "retailer_key":       retailer_key,
                "store_name":         loc["name"],
                "address":            loc["address"],
                "city":               loc["city"],
                "state":              loc["state"],
                "zip_code":           loc["zip_code"],
                "latitude":           loc["lat"],
                "longitude":          loc["lon"],
                "osm_id":             loc["osm_id"],
                "source":             "osm",
                "geocode_source":     "osm",
                "geocode_confidence": "address",
                "show_on_map":        True,
            })

        logger.info(f"  Found {len(locations)} US locations with zip codes in OSM")

        if not locations:
            logger.warning(f"  No data found for {display_name} — skipping")
            continue

        # Upsert — upgrades centroid entries where zip_code matches
        try:
            sb.table("store_locations").upsert(locations, on_conflict="retailer_key,zip_code").execute()
            total_upserted += len(locations)
            logger.info(f"  Upserted {len(locations)} rows for {retailer_key}")
        except Exception as e:
            logger.warning(f"  Batch upsert failed: {e}, trying row by row...")
            for loc in locations:
                try:
                    sb.table("store_locations").upsert([loc], on_conflict="retailer_key,zip_code").execute()
                    total_upserted += 1
                except Exception as e2:
                    logger.warning(f"    Row failed {loc.get('zip_code')}: {e2}")

        # Verify
        after = sb.table("store_locations").select("id, geocode_confidence").eq("retailer_key", retailer_key).execute().data or []
        real_after = sum(1 for r in after if r.get("geocode_confidence") not in ("zip_centroid", "zip") and r.get("geocode_confidence") is not None)
        logger.info(f"  After: {len(after)} total, {real_after} real GPS (+{real_after - real_before})")

    print(f"\nDone. Total upserted: {total_upserted} rows.")


if __name__ == "__main__":
    main()
