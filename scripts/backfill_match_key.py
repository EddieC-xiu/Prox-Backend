# scripts/backfill_match_key.py
import sys
import time
import logging
from config.supabase import get_supabase_client

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)

FETCH_BATCH = 500
MAX_RETRIES = 2

def main():
    supabase = get_supabase_client()
    offset = 0
    total_written = 0
    total_skipped = 0
    total_fetched = 0

    logger.info("Starting match_key backfill...")

    while True:
        # Fetch batch with no match_key
        for attempt in range(MAX_RETRIES):
            try:
                res = (
                    supabase.table("flyer_deals")
                    .select("id, brand, canonical_product_name, base_amount")
                    .is_("match_key", "null")
                    .not_.is_("canonical_product_name", "null")
                    .range(offset, offset + FETCH_BATCH - 1)
                    .execute()
                )
                batch = res.data or []
                break
            except Exception as e:
                logger.warning(f"Fetch failed (attempt {attempt+1}): retrying in 2s")
                time.sleep(2)
                batch = []

        if not batch:
            break

        total_fetched += len(batch)

        # Build match_key for each row
        to_write = []
        for row in batch:
            brand     = (row.get("brand") or "").strip()
            canonical = (row.get("canonical_product_name") or "").strip()
            size      = row.get("base_amount")
            size_str  = str(size) if size is not None else "no_size"
            match_key = f"{brand}|{canonical}|{size_str}"
            to_write.append({"id": row["id"], "match_key": match_key})

        # Write batch
        for attempt in range(MAX_RETRIES):
            try:
                supabase.table("flyer_deals").upsert(to_write, on_conflict="id").execute()
                total_written += len(to_write)
                break
            except Exception as e:
                logger.warning(f"Write failed (attempt {attempt+1}): retrying in 2s")
                time.sleep(2)
                if attempt == MAX_RETRIES - 1:
                    total_skipped += len(to_write)

        offset += FETCH_BATCH

        if total_fetched % 10000 == 0:
            logger.info(f"Progress: {total_fetched:,} fetched | {total_written:,} written | {total_skipped:,} skipped")

    print(f"\nDone.")
    print(f"  Fetched:  {total_fetched:,}")
    print(f"  Written:  {total_written:,}")
    print(f"  Skipped:  {total_skipped:,}")

if __name__ == "__main__":
    main()