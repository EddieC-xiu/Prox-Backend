import os, psycopg2, time
from dotenv import load_dotenv

load_dotenv()

conn = psycopg2.connect(os.environ["DATABASE_URL"])
conn.autocommit = False
cur = conn.cursor()

# Disable statement timeout for this session only
cur.execute("SET statement_timeout = 0")
conn.commit()
print("Statement timeout disabled for this session")

# Get all distinct non-lowercase retailer names still remaining
print("Finding remaining retailer name variants to fix...")
cur.execute("""
    SELECT DISTINCT retailer, LOWER(retailer) as normalized
    FROM flyer_deals
    WHERE retailer != LOWER(retailer)
    ORDER BY retailer
""")
variants = cur.fetchall()
print(f"  → {len(variants)} variants remaining\n")

total_updated = 0
failed = []

for original, normalized in variants:
    retries = 3
    while retries > 0:
        try:
            start = time.time()
            cur.execute(
                "UPDATE flyer_deals SET retailer = %s WHERE retailer = %s",
                (normalized, original)
            )
            updated = cur.rowcount
            conn.commit()
            elapsed = time.time() - start
            print(f"  '{original}' → '{normalized}': {updated:,} rows ({elapsed:.1f}s)")
            total_updated += updated
            time.sleep(0.5)  # small pause between updates to reduce contention
            break
        except psycopg2.errors.DeadlockDetected:
            conn.rollback()
            retries -= 1
            wait = (4 - retries) * 5  # 5s, 10s, 15s backoff
            print(f"  ⚠ Deadlock on '{original}', retrying in {wait}s... ({retries} retries left)")
            time.sleep(wait)
        except Exception as e:
            conn.rollback()
            print(f"  ✗ Failed '{original}': {e}")
            failed.append(original)
            break
    else:
        print(f"  ✗ Gave up on '{original}' after 3 deadlocks")
        failed.append(original)

print(f"\nDone. Total rows normalized: {total_updated:,}")
if failed:
    print(f"Failed variants ({len(failed)}): {failed}")
else:
    print("All variants normalized successfully.")

cur.close()
conn.close()
