"""
Delete ZIP-centroid and non-store rows from store_locations using direct SQL.
Much faster than REST API because it runs in one transaction.
"""
import os, re
import psycopg2
from dotenv import load_dotenv
load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise ValueError("DATABASE_URL not set")

conn = psycopg2.connect(DATABASE_URL)
conn.autocommit = False
cur = conn.cursor()

print("Connected to Postgres directly.")

# Step 1: Find ZIP-centroid IDs
# = null address + same rounded lat/lng shared by 2+ different retailer_keys
cur.execute("""
    SELECT id FROM store_locations sl
    WHERE sl.full_address IS NULL
      AND EXISTS (
          SELECT 1 FROM store_locations sl2
          WHERE sl2.id <> sl.id
            AND sl2.full_address IS NULL
            AND ROUND(sl2.latitude::numeric, 4) = ROUND(sl.latitude::numeric, 4)
            AND ROUND(sl2.longitude::numeric, 4) = ROUND(sl.longitude::numeric, 4)
            AND sl2.retailer_key <> sl.retailer_key
      )
""")
zip_centroid_ids = [r[0] for r in cur.fetchall()]
print(f"ZIP-centroid rows: {len(zip_centroid_ids)}")

# Step 2: Find non-store variant IDs
NON_STORE_PATTERNS = [
    '%fuel station%', '%gas station%', '% pharmacy%', '% optical%',
    '%tire center%', '% parking%', '%distribution center%', '%corporate%',
    '%vision center%', '%auto care%', '%garden center%', '%under construction%',
]
placeholders = " OR ".join(f"lower(retailer) LIKE %s" for _ in NON_STORE_PATTERNS)
cur.execute(f"SELECT id FROM store_locations WHERE {placeholders}", NON_STORE_PATTERNS)
non_store_ids = [r[0] for r in cur.fetchall()]
print(f"Non-store variant rows: {len(non_store_ids)}")

all_ids = list(set(zip_centroid_ids + non_store_ids))
print(f"Total to delete: {len(all_ids)}")

if not all_ids:
    print("Nothing to delete.")
    conn.close()
    exit(0)

# Step 3: Null out flyer_deals.store_id references (one efficient query)
print("Nulling flyer_deals.store_id references...")
cur.execute(
    "UPDATE flyer_deals SET store_id = NULL WHERE store_id = ANY(%s)",
    (all_ids,)
)
print(f"  Nulled {cur.rowcount} flyer_deals rows")

# Step 4: Delete the bad store_locations rows
print("Deleting bad store_locations rows...")
cur.execute(
    "DELETE FROM store_locations WHERE id = ANY(%s)",
    (all_ids,)
)
print(f"  Deleted {cur.rowcount} store_locations rows")

conn.commit()
print("Done.")
conn.close()
