"""Restore the Kroger CA entries that were incorrectly neutralized."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from config.supabase import get_supabase_client
sb = get_supabase_client()

# Restore the original lat/lng/confidence from the audit output
restorations = [
    {"id": 4618, "latitude": 34.1440673,  "longitude": -118.4131366, "geocode_confidence": "high"},  # Studio City CA
    {"id": 4639, "latitude": 33.8300147,  "longitude": -118.3109876, "geocode_confidence": "high"},  # Torrance CA
    {"id": 4699, "latitude": 34.0350253,  "longitude": -118.4492796, "geocode_confidence": "high"},  # Los Angeles CA
    {"id": 4608, "latitude": 34.2580358,  "longitude": -119.208935,  "geocode_confidence": "high"},  # Ventura CA
]

for r in restorations:
    result = (
        sb.table("store_locations")
        .update({"latitude": r["latitude"], "longitude": r["longitude"], "geocode_confidence": r["geocode_confidence"]})
        .eq("id", r["id"])
        .execute()
    )
    print(f"Restored id={r['id']}: lat={r['latitude']}, lng={r['longitude']}")

# Verify
check = (
    sb.table("store_locations")
    .select("id, zip_code, city, state, latitude, longitude, geocode_confidence")
    .in_("id", [4618, 4639, 4699, 4608])
    .execute()
    .data or []
)
print("\nRestored entries:")
for r in check:
    print(f"  id={r['id']} zip={r.get('zip_code')} {r.get('city')},{r.get('state')} lat={r.get('latitude')},{r.get('longitude')} conf={r.get('geocode_confidence')}")
