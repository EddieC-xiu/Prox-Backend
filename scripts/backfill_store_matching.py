# scripts/backfill_store_matching.py
import time
import logging
import argparse
from config.supabase import get_supabase_client
from services.store_matching import find_store_for_deal

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)

sb = get_supabase_client()

TABLE      = "test_flyer_deals_duplicate"
BATCH_SIZE = 500
RATE_LIMIT = 0.05

def fetch_all_rows() -> list[dict]:
    rows, offset = [], 0
    while True:
        res = (
            sb.table(TABLE)
            .select("id, retailer, zip_code")
            .is_("store_id", "null")
            .order("id")
            .range(offset, offset + BATCH_SIZE - 1)
            .execute()
        )
        batch = res.data or []
        rows.extend(batch)
        logger.info(f"Fetched {len(rows)} rows...")
        if len(batch) < BATCH_SIZE:
            break
        offset += BATCH_SIZE
    return rows

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args()

    if args.dry_run:
        print("[DRY RUN] Nothing will be written.\n")

    rows = fetch_all_rows()
    if args.limit:
        rows = rows[:args.limit]

    logger.info(f"Total rows to process: {len(rows)}")

    matched   = 0
    unmatched = 0

    for i, row in enumerate(rows):
        retailer = row.get("retailer") or ""
        zip_code = row.get("zip_code") or ""

        result = find_store_for_deal(
            retailer_raw=retailer,
            zip_code=zip_code,
        )

        if result.store_id:
            matched += 1
            if not args.dry_run:
                try:
                    sb.table(TABLE).update({
                        "store_id": str(result.store_id),
                    }).eq("id", row["id"]).execute()
                except Exception as e:
                    logger.error(f"Failed to update id={row['id']}: {e}")
        else:
            unmatched += 1

        if (i + 1) % 500 == 0:
            logger.info(f"  Progress: {i+1}/{len(rows)} | matched={matched} unmatched={unmatched}")

        time.sleep(RATE_LIMIT)

    print(f"\nDone. {matched} rows matched, {unmatched} unmatched.")

if __name__ == "__main__":
    main()