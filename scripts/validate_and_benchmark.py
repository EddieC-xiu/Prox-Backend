import time
from config.supabase import supabase
from services.store_distance import get_nearest_stores

def fetch_all(table, columns):
    """Paginate through all rows — Supabase caps at 1000 per request."""
    all_rows = []
    page_size = 1000
    offset = 0
    while True:
        batch = supabase.table(table)\
            .select(columns)\
            .range(offset, offset + page_size - 1)\
            .execute().data
        all_rows.extend(batch)
        if len(batch) < page_size:
            break
        offset += page_size
    return all_rows

def run_validation():
    print("=== Address Coverage Report ===\n")

    stores = fetch_all("store_locations", "retailer_key, geocode_source, geocode_confidence, address")

    total = len(stores)
    real = sum(1 for s in stores if s["geocode_source"] not in ("zip_centroid", "pgeocode", None))
    zip_only = sum(1 for s in stores if s["geocode_source"] == "zip_centroid")
    pgeocode_count = sum(1 for s in stores if s["geocode_source"] == "pgeocode")
    no_address = sum(1 for s in stores if not s["address"])
    missing_source = sum(1 for s in stores if not s["geocode_source"])

    print(f"Total stores:              {total}")
    print(f"Real geocoded (nominatim/api/overpass): {real} ({round(real/total*100)}%)")
    print(f"ZIP centroid only:         {zip_only} ({round(zip_only/total*100)}%)")
    print(f"pgeocode (ZIP-level):      {pgeocode_count} ({round(pgeocode_count/total*100)}%)")
    print(f"No street address:         {no_address}")
    print(f"Missing geocode source:    {missing_source}")

    print("\n--- By Retailer ---")
    by_retailer = {}
    for s in stores:
        key = s["retailer_key"]
        if key not in by_retailer:
            by_retailer[key] = {"total": 0, "zip_centroid": 0, "real": 0}
        by_retailer[key]["total"] += 1
        if s["geocode_source"] == "zip_centroid":
            by_retailer[key]["zip_centroid"] += 1
        elif s["geocode_source"] in ("nominatim", "api", "overpass"):
            by_retailer[key]["real"] += 1

    for retailer, counts in sorted(by_retailer.items()):
        pct = round(counts["real"] / counts["total"] * 100)
        print(f"  {retailer:<30} total: {counts['total']:<6} real: {counts['real']:<6} zip_centroid: {counts['zip_centroid']:<6} ({pct}% real)")

def run_benchmark():
    print("\n=== Performance Benchmark ===\n")

    test_cases = [
        ("New York, NY",     40.7128, -74.0060),
        ("Los Angeles, CA",  34.0522, -118.2437),
        ("Chicago, IL",      41.8781, -87.6298),
        ("Houston, TX",      29.7604, -95.3698),
        ("Phoenix, AZ",      33.4484, -112.0740),
    ]

    for name, lat, lon in test_cases:
        start = time.time()
        stores = get_nearest_stores(lat, lon, radius_miles=25)
        elapsed = (time.time() - start) * 1000
        status = "✓" if elapsed < 500 else "✗"
        print(f"  {status} {name:<20} {len(stores)} stores found in {elapsed:.1f}ms")

if __name__ == "__main__":
    run_validation()
    run_benchmark()