# scripts/recanonicalize.py
#
# Re-runs the normalizer against ALL existing canonical names to fix
# word-order variants, leftover filler words, and price leakage.
# Only updates rows where the canonical name actually changes.
#
# Usage:
#   PYTHONUTF8=1 PYTHONPATH=. python scripts/recanonicalize.py --dry-run
#   PYTHONUTF8=1 PYTHONPATH=. python scripts/recanonicalize.py

import re
import time
import logging
import argparse
from config.supabase import get_supabase_client
from scoring.product_normalizer import build_canonical_name

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)

sb = get_supabase_client()

TABLE = "test_flyer_deals_duplicate"
BATCH = 1000

# Pattern for price-only canonical names — bad scraper data, skip them
_PRICE_ONLY_RE = re.compile(r'^\d{3,4}$')


def fetch_all() -> list[dict]:
    rows, offset = [], 0
    while True:
        res = (
            sb.table(TABLE)
            .select("id, canonical_product_name, brand")
            .not_.is_("canonical_product_name", "null")
            .not_.is_("brand", "null")
            .range(offset, offset + BATCH - 1)
            .execute()
            .data or []
        )
        rows.extend(res)
        logger.info(f"Fetched {len(rows)} rows...")
        if len(res) < BATCH:
            break
        offset += BATCH
    return rows


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if args.dry_run:
        print("[DRY RUN] Nothing will be written.\n")

    rows = fetch_all()
    logger.info(f"Total rows to check: {len(rows)}")

    updated  = 0
    unchanged = 0
    skipped  = 0
    shown    = 0

    for row in rows:
        old_canonical = row["canonical_product_name"]
        brand         = row.get("brand")

        # Skip price-only canonical names — bad scraper data
        if _PRICE_ONLY_RE.match(old_canonical.strip()):
            skipped += 1
            continue

        # Re-run normalizer against the existing canonical name
        new_canonical = build_canonical_name(old_canonical, brand)

        # Only update if something actually changed
        if new_canonical == old_canonical or not new_canonical or len(new_canonical) < 2:
            unchanged += 1
            continue

        if args.dry_run:
            if shown < 20:
                print(f"  '{old_canonical}'")
                print(f"  → '{new_canonical}'  (brand={brand})\n")
                shown += 1
            updated += 1
            continue

        try:
            sb.table(TABLE).update({
                "canonical_product_name": new_canonical,
            }).eq("id", row["id"]).execute()
            updated += 1
        except Exception as e:
            logger.error(f"Failed id={row['id']}: {e}")
        time.sleep(0.01)

        if updated % 500 == 0:
            logger.info(f"  Updated {updated} rows...")

    print(f"\nDone.")
    print(f"  Updated:   {updated}")
    print(f"  Unchanged: {unchanged}")
    print(f"  Skipped (price-only): {skipped}")


if __name__ == "__main__":
    main()