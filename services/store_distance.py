# services/store_distance.py
import time
import pgeocode
from math import radians, sin, cos, sqrt, atan2
from config.supabase import supabase

_nomi = pgeocode.Nominatim("us")

# ---------------------------------------------------------------------------
# In-memory caches
# ---------------------------------------------------------------------------

# ZIP coord cache: zip_code -> (lat, lon)
# ZIP centroids never change at runtime, so no TTL needed.
_zip_coord_cache: dict = {}

# Results cache: (zip_code, radius_miles, limit) -> (timestamp, results)
# Stores can be added/updated, so results expire after CACHE_TTL_SECONDS.
_results_cache: dict = {}

CACHE_TTL_SECONDS = 3600  # 1 hour


# ---------------------------------------------------------------------------
# Core distance math
# ---------------------------------------------------------------------------

def haversine(lat1, lon1, lat2, lon2):
    """Calculate distance in miles between two lat/lon points."""
    R = 3958.8
    lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = sin(dlat/2)**2 + cos(lat1)*cos(lat2)*sin(dlon/2)**2
    return R * 2 * atan2(sqrt(a), sqrt(1-a))


# ---------------------------------------------------------------------------
# ZIP centroid lookup (cached, permanent)
# ---------------------------------------------------------------------------

def get_lat_lon_for_zip(zip_code):
    """Look up lat/lon for a ZIP code using pgeocode (local dataset, no DB call).
    Results are cached permanently for the lifetime of the process."""
    if zip_code in _zip_coord_cache:
        return _zip_coord_cache[zip_code]

    info = _nomi.query_postal_code(zip_code)
    if info is not None and str(info.get("latitude", "nan")) != "nan":
        coords = (float(info["latitude"]), float(info["longitude"]))
        _zip_coord_cache[zip_code] = coords
        return coords

    return None, None


# ---------------------------------------------------------------------------
# Nearest-store query (bounding-box prefilter + haversine refinement)
# ---------------------------------------------------------------------------

def get_nearest_stores(user_lat, user_lon, radius_miles=25, limit=10):
    """Return nearest stores within radius_miles using bounding box prefilter.

    The bounding box is pushed down to Supabase so only a small candidate
    set is returned over the wire. Haversine then does exact filtering on
    that small set. Relies on idx_store_locations_lat_lon (migration 002).
    """
    lat_delta = radius_miles / 69.0
    lon_delta = radius_miles / (69.0 * cos(radians(user_lat)))

    stores = supabase.table("store_locations")\
        .select("id, retailer_key, address, zip_code, latitude, longitude")\
        .not_.is_("latitude", "null")\
        .not_.is_("longitude", "null")\
        .gte("latitude",  user_lat - lat_delta)\
        .lte("latitude",  user_lat + lat_delta)\
        .gte("longitude", user_lon - lon_delta)\
        .lte("longitude", user_lon + lon_delta)\
        .execute().data

    nearby = []
    for store in stores:
        dist = haversine(user_lat, user_lon, store["latitude"], store["longitude"])
        if dist <= radius_miles:
            store["distance_miles"] = round(dist, 2)
            nearby.append(store)

    return sorted(nearby, key=lambda x: x["distance_miles"])[:limit]


# ---------------------------------------------------------------------------
# ZIP-based entry point (cached, TTL-based)
# ---------------------------------------------------------------------------

def get_nearest_stores_by_zip(zip_code, radius_miles=25, limit=10):
    """Return nearest stores to a given ZIP code.

    Results are cached for CACHE_TTL_SECONDS (1 hour). The ZIP centroid
    lookup is cached permanently.
    """
    cache_key = (zip_code, radius_miles, limit)
    if cache_key in _results_cache:
        ts, cached = _results_cache[cache_key]
        if time.time() - ts < CACHE_TTL_SECONDS:
            return cached

    lat, lon = get_lat_lon_for_zip(zip_code)
    if not lat or not lon:
        print(f"ZIP {zip_code} coordinates not found")
        return []

    results = get_nearest_stores(lat, lon, radius_miles, limit)
    _results_cache[cache_key] = (time.time(), results)
    return results


# ---------------------------------------------------------------------------
# Cache utilities
# ---------------------------------------------------------------------------

def cache_stats():
    """Return a snapshot of current cache sizes."""
    now = time.time()
    live = sum(1 for ts, _ in _results_cache.values() if now - ts < CACHE_TTL_SECONDS)
    return {
        "zip_coord_cache_size": len(_zip_coord_cache),
        "results_cache_total":  len(_results_cache),
        "results_cache_live":   live,
    }

def clear_results_cache():
    """Flush the results cache (e.g. after a store data update)."""
    _results_cache.clear()


# ---------------------------------------------------------------------------
# Phase 3 addition — used by deal_location_service.py
# ---------------------------------------------------------------------------

def get_nearby_stores(
    zip_code:     str,
    radius_miles: float      = 10.0,
    retailer_key: str | None = None,
) -> list[dict]:
    """
    Return all store_locations rows within radius_miles of zip_code centroid.
    Each row is annotated with distance_miles and a store_id alias.
    Sorted nearest-first. No limit — deal_location_service handles filtering.

    Differences from get_nearest_stores_by_zip:
      - Selects name, city, state (needed by deal_location_service)
      - Supports optional retailer_key filter
      - Returns all stores in radius instead of a fixed limit
      - Adds store_id alias so deal_location_service can key its map
    """
    lat, lon = get_lat_lon_for_zip(zip_code)
    if not lat or not lon:
        print(f"[DISTANCE] ZIP {zip_code} coordinates not found")
        return []

    lat_delta = radius_miles / 69.0
    lon_delta = radius_miles / (69.0 * cos(radians(lat)))

    q = (
        supabase.table("store_locations")
        .select("id, retailer_key, store_name, address, city, state, zip_code, latitude, longitude")
        .not_.is_("latitude",  "null")
        .not_.is_("longitude", "null")
        .gte("latitude",  lat - lat_delta)
        .lte("latitude",  lat + lat_delta)
        .gte("longitude", lon - lon_delta)
        .lte("longitude", lon + lon_delta)
    )
    if retailer_key:
        q = q.eq("retailer_key", retailer_key)

    rows    = q.execute().data or []
    results = []

    for row in rows:
        dist = haversine(lat, lon, row["latitude"], row["longitude"])
        if dist <= radius_miles:
            results.append({
                **row,
                "store_id":       row["id"],   # alias used by deal_location_service
                "distance_miles": round(dist, 2),
            })

    return sorted(results, key=lambda r: r["distance_miles"])