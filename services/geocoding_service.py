# services/geocoding_service.py
import time
import math
import pgeocode
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut, GeocoderServiceError

geolocator = Nominatim(user_agent="prox-backend-sai")
_pgeocode_nomi = pgeocode.Nominatim('us')  # loaded once, reused for every lookup

# US bounding box
US_LAT_MIN, US_LAT_MAX = 24.0, 49.5
US_LNG_MIN, US_LNG_MAX = -125.0, -66.0


def is_us_coordinate(lat, lng):
    return (
        lat is not None and lng is not None
        and US_LAT_MIN <= lat <= US_LAT_MAX
        and US_LNG_MIN <= lng <= US_LNG_MAX
    )


def geocode_store(retailer: str, zip_code: str, address: str = None):
    """
    Returns (latitude, longitude, geocode_confidence) or (None, None, 'failed').

    Priority:
      1. Full address            → confidence = 'high'
      2. Zip code + USA          → confidence = 'zip_only'
      3. pgeocode centroid       → confidence = 'zip_centroid'
      4. Failed                  → confidence = 'failed'
    """
    attempts = []

    if address:
        attempts.append((f"{address}, USA", "high"))

    if zip_code:
        attempts.append((f"{zip_code}, USA", "zip_only"))

    for query, confidence in attempts:
        try:
            time.sleep(1)
            location = geolocator.geocode(query, timeout=10)
            if location and is_us_coordinate(location.latitude, location.longitude):
                return location.latitude, location.longitude, confidence
        except (GeocoderTimedOut, GeocoderServiceError) as e:
            print(f"  Geocoder error for '{query}': {e}")
            continue

    lat, lng = get_zip_centroid(zip_code)
    if lat and lng:
        print(f"  ⚠ Using pgeocode centroid for {zip_code}")
        return lat, lng, "zip_centroid"

    print(f"  ✗ All geocoding attempts failed for {retailer} / {zip_code}")
    return None, None, "failed"


def get_zip_centroid(zip_code: str):
    """Dynamically looks up any US zip centroid using pgeocode (offline, no API key)."""
    try:
        result = _pgeocode_nomi.query_postal_code(zip_code)
        lat = result.latitude
        lng = result.longitude
        if lat and lng and not math.isnan(lat) and not math.isnan(lng):
            return float(lat), float(lng)
    except Exception as e:
        print(f"  pgeocode lookup failed for {zip_code}: {e}")
    return None, None


# ── Phase 3 additions ─────────────────────────────────────────────────────────
# These wrap the existing geocode_store function and return the dict format
# that store_matching.py expects: {'lat': ..., 'lng': ...} or None.

def geocode_address(
    address:  str,
    zip_code: str | None = None,
    city:     str | None = None,
    state:    str | None = None,
) -> dict | None:
    """
    Called by store_matching._create_store when a full address is available.
    Wraps geocode_store and returns {'lat': ..., 'lng': ...} or None.
    """
    location_str = ", ".join(p for p in [address, city, state, zip_code] if p)
    lat, lng, _ = geocode_store(
        retailer="",
        zip_code=zip_code or "",
        address=location_str,
    )
    if lat and lng:
        return {"lat": lat, "lng": lng}
    return None


def geocode_retailer(
    retailer_key: str,
    zip_code:     str | None = None,
    city:         str | None = None,
    state:        str | None = None,
) -> dict | None:
    """
    Called by store_matching._create_store when no address is available.
    Wraps geocode_store using retailer name + location as the query.
    Returns {'lat': ..., 'lng': ...} or None.
    """
    name = retailer_key.replace("_", " ").title()
    lat, lng, _ = geocode_store(
        retailer=name,
        zip_code=zip_code or "",
        address=None,
    )
    if lat and lng:
        return {"lat": lat, "lng": lng}
    return None