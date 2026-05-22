# Faster store_id backfill for flyer_deals
# Uses ID-cursor pagination — processes each row once, skips unmatched cleanly
# Zip centroids used only for proximity math to find nearest store (not for display)

import time
import logging
from config.supabase import get_supabase_client
from services.store_matching import find_store_for_deal

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)

sb = get_supabase_client()
FETCH_BATCH = 500

def main():
    total_matched = 0
    total_unmatched = 0
    total_fetched = 0
    last_id = 0

    logger.info("Starting store_id backfill on flyer_deals (cursor-based)...")

    while True:
        res = (
            sb.table("flyer_deals")
            .select("id, retailer, zip_code")
            .is_("store_id", "null")
            .not_.is_("retailer", "null")
            .not_.is_("zip_code", "null")
            .gt("id", last_id)
            .order("id")
            .limit(FETCH_BATCH)
            .execute()
        )
        batch = res.data or []
        if not batch:
            break

        total_fetched += len(batch)
        last_id = batch[-1]["id"]

        to_update = []
        for row in batch:
            result = find_store_for_deal(
                retailer_raw=row["retailer"],
                zip_code=row["zip_code"],
            )
            if result.store_id:
                to_update.append({"id": row["id"], "store_id": str(result.store_id)})
                total_matched += 1
            else:
                total_unmatched += 1

        if to_update:
            for attempt in range(3):
                try:
                    sb.table("flyer_deals").upsert(to_update, on_conflict="id").execute()
                    break
                except Exception as e:
                    logger.warning(f"Batch write attempt {attempt+1} failed: {e}")
                    time.sleep(5 * (attempt + 1))
                    # Refresh client on connection errors
                    from config.supabase import get_supabase_client as _gsbc
                    sb = _gsbc()

        if total_fetched % 10000 == 0:
            logger.info(f"Progress: {total_fetched:,} processed | {total_matched:,} matched | {total_unmatched:,} unmatched")

    logger.info(f"\nDone. Processed: {total_fetched:,} | Matched: {total_matched:,} | Unmatched: {total_unmatched:,}")

if __name__ == "__main__":
    main()
