"""
Usage:
    PYTHONPATH=. python scripts/backfill_price_history.py --dry-run
    PYTHONPATH=. python scripts/backfill_price_history.py
"""
import logging
import sys
import time
from datetime import datetime, timezone
from scoring.product_normalizer import normalize_size_oz
from services.price_history_service import upsert_price_history
from config.supabase import get_supabase_client

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

SOURCE_TABLE = "flyer_deals"
FETCH_BATCH  = 500
MAX_RETRIES  = 2
DRY_RUN      = "--dry-run" in sys.argv
MAX_PRICE    = 999999.0  # sanity cap — skip bulk/case pricing and data errors


def build_match_key(brand, canonical, size_oz) -> str | None:
    if brand and canonical and size_oz:
        return f"{brand}|{canonical}|{size_oz}"
    if brand and canonical:
        return f"{brand}|{canonical}|no_size"
    return None


def fetch_batch(client, offset: int) -> list[dict]:
    for attempt in range(MAX_RETRIES):
        try:
            res = (
                client.table(SOURCE_TABLE)
                .select("id, brand, canonical_product_name, product_price, base_amount, base_unit, store_id")
                .not_.is_("brand", "null")
                .not_.is_("canonical_product_name", "null")
                .not_.is_("product_price", "null")
                .range(offset, offset + FETCH_BATCH - 1)
                .execute()
            )
            return res.data or []
        except Exception as e:
            logger.warning(f"Fetch failed at offset {offset} (attempt {attempt+1}): retrying in 2s")
            time.sleep(2)
    logger.error(f"Fetch permanently failed at offset {offset} — skipping")
    return None


def main():
    client = get_supabase_client()
    now    = datetime.now(timezone.utc).isoformat()

    offset        = 0
    total_fetched = 0
    total_written = 0
    total_skipped = 0

    logger.info(f"Starting {'DRY RUN ' if DRY_RUN else ''}price_history backfill from {SOURCE_TABLE}...")

    while True:
        batch = fetch_batch(client, offset)

        if batch is None:
            offset += FETCH_BATCH
            continue

        if not batch:
            break

        total_fetched += len(batch)

        # Build price_history rows
        to_write = []
        seen     = {}
        for row in batch:
            brand     = row.get("brand")
            canonical = row.get("canonical_product_name")
            size_oz   = normalize_size_oz(row.get("base_amount"), row.get("base_unit"), canonical or "")
            match_key = build_match_key(brand, canonical, size_oz)

            if not match_key:
                total_skipped += 1
                continue

            # Price sanity check
            price = float(row.get("product_price") or 0)
            if price <= 0 or price > MAX_PRICE:
                logger.debug(f"Skipping bad price ${price} for {canonical}")
                total_skipped += 1
                continue

            record = {
                "match_key":              match_key,
                "store_id":               row.get("store_id"),
                "brand":                  brand,
                "canonical_product_name": canonical,
                "size_oz":                size_oz,
                "product_price":          price,
                "observed_at":            now,
                "observed_date":          datetime.now(timezone.utc).date().isoformat(),
            }

            # Deduplicate within batch
            dedup_key = (match_key, row.get("store_id"))
            seen[dedup_key] = record

        to_write = list(seen.values())

        if not to_write:
            offset += FETCH_BATCH
            continue

        if DRY_RUN:
            total_written += len(to_write)
        else:
            for attempt in range(MAX_RETRIES):
                try:
                    written = upsert_price_history(to_write)
                    total_written += written
                    break
                except Exception as e:
                    logger.warning(f"Write failed at offset {offset} (attempt {attempt+1}): retrying in 2s")
                    time.sleep(2)
                    if attempt == MAX_RETRIES - 1:
                        logger.error(f"Write permanently failed at offset {offset} — skipping {len(to_write)} rows")
                        total_skipped += len(to_write)

        offset += FETCH_BATCH

        if total_fetched % 10000 == 0:
            logger.info(f"Progress: {total_fetched:,} fetched | {total_written:,} written | {total_skipped:,} skipped")

    # Cleanup duplicates
    if not DRY_RUN:
        logger.info("Running duplicate cleanup...")
        try:
            client.rpc("cleanup_price_history_dupes", {}).execute()
            logger.info("Duplicate cleanup complete.")
        except Exception as e:
            logger.warning(f"Cleanup step failed (non-critical): {e}")

    print(f"\nDone.")
    print(f"  Fetched:  {total_fetched:,}")
    print(f"  Written:  {total_written:,}")
    print(f"  Skipped:  {total_skipped:,}")
    if DRY_RUN:
        print("\n[DRY RUN] Nothing was written.")


if __name__ == "__main__":
    main()