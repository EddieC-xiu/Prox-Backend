# scripts/populate_match_key.py
import time
import logging
from config.supabase import get_supabase_client

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)

sb = get_supabase_client()

def main():
    updated = 0
    errors = 0
    offset = 0
    batch_size = 500

    while True:
        # Fetch rows that have canonical but no match_key
        rows = (
            sb.table("flyer_deals")
            .select("id, brand, canonical_product_name, base_amount")
            .not_.is_("canonical_product_name", "null")
            .is_("match_key", "null")
            .range(offset, offset + batch_size - 1)
            .execute()
            .data
        )

        if not rows:
            break

        # Build update payloads
        payloads = []
        for row in rows:
            mk = "{}|{}|{}".format(
                row.get("brand") or "",
                row.get("canonical_product_name") or "",
                row.get("base_amount") or ""
            )
            payloads.append({"id": row["id"], "match_key": mk})

        # Write in sub-batches of 100
        for i in range(0, len(payloads), 100):
            sub = payloads[i:i + 100]
            try:
                sb.table("flyer_deals").upsert(sub, on_conflict="id").execute()
                updated += len(sub)
            except Exception as e:
                errors += len(sub)
                logger.error(f"Sub-batch failed: {e}")

        logger.info(f"Updated {updated} rows so far...")
        offset += batch_size
        time.sleep(0.2)

    print(f"\nDone. {updated} rows updated, {errors} errors.")

if __name__ == "__main__":
    main()