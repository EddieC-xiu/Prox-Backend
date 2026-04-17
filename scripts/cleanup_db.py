import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.supabase import supabase

# Delete junk retailers one at a time to avoid timeout
junk_retailers = [
    "smart_final", "kroger", "walmart", "target", "aldi",
    "Walmart", "Target", "Aldi", "ALDI"
]

total_deleted = 0
for retailer in junk_retailers:
    try:
        result = supabase.table("store_locations") \
                         .delete() \
                         .eq("retailer", retailer) \
                         .execute()
        count = len(result.data)
        if count > 0:
            print(f"  Deleted {count} rows for '{retailer}'")
            total_deleted += count
    except Exception as e:
        print(f"  Error deleting '{retailer}': {e}")

print(f"\nTotal deleted: {total_deleted}")

# Verify what's left
rows = supabase.table("store_locations").select("retailer").execute()
from collections import Counter
counts = Counter(r["retailer"] for r in rows.data)
print("\nRemaining rows:")
for retailer, count in sorted(counts.items(), key=lambda x: -x[1]):
    print(f"  {retailer:<30} {count}")