import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config.supabase import supabase

def extract_unique_stores():
    print("Fetching unique stores from flyer_deals...")

    response = (
        supabase.table("flyer_deals")
        .select("retailer, retailer_address, zip_code, retailer_key")
        .execute()
    )

    if not response.data:
        print("No data found in flyer_deals.")
        return []

    seen = set()
    unique_stores = []

    for row in response.data:
        key = (row.get("retailer", ""), row.get("retailer_address", ""))
        if key not in seen and key[0]:
            seen.add(key)
            unique_stores.append({
                "retailer":          row.get("retailer"),
                "retailer_address":  row.get("retailer_address"),
                "zip_code":          row.get("zip_code"),
                "retailer_key":      row.get("retailer_key"),
            })

    print(f"Found {len(unique_stores)} unique stores.")

    out_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "unique_stores.json")
    with open(out_path, "w") as f:
        json.dump(unique_stores, f, indent=2)
    print(f"Saved to unique_stores.json")

    return unique_stores

if __name__ == "__main__":
    stores = extract_unique_stores()
    print("\nFirst 5 stores:")
    for s in stores[:5]:
        print(s)