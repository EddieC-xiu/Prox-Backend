import pgeocode
from config.supabase import supabase

def run():
    print("Fetching all distinct ZIP codes from store_locations...")

    result = supabase.table("store_locations")\
        .select("zip_code")\
        .execute().data

    all_zips = list({row["zip_code"] for row in result if row["zip_code"]})
    print(f"Found {len(all_zips)} unique ZIP codes\n")

    nomi = pgeocode.Nominatim("us")
    centroids = []
    failed = 0

    for zip_code in all_zips:
        location = nomi.query_postal_code(zip_code)
        lat = location.latitude
        lon = location.longitude

        if lat != lat or lon != lon:  # NaN check
            failed += 1
            continue

        centroids.append({
            "zip_code": zip_code,
            "latitude": float(lat),
            "longitude": float(lon)
        })

    print(f"Geocoded: {len(centroids)}")
    print(f"Failed:   {failed}")

    if centroids:
        supabase.table("zip_centroids")\
            .upsert(centroids)\
            .execute()
        print(f"Stored {len(centroids)} ZIP centroids in zip_centroids table")

if __name__ == "__main__":
    run()