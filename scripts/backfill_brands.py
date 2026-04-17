# scripts/backfill_brands.py
#
# Finds rows with no brand but a product_name and tries to detect the brand.
# Only updates rows where a brand is successfully detected.
#
# Usage:
#   PYTHONUTF8=1 PYTHONPATH=. python scripts/backfill_brands.py --dry-run
#   PYTHONUTF8=1 PYTHONPATH=. python scripts/backfill_brands.py

import time
import logging
import argparse
from config.supabase import get_supabase_client
from scoring.product_normalizer import extract_brand, build_canonical_name

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)

sb = get_supabase_client()

TABLE = "test_flyer_deals_duplicate"
BATCH = 1000


def fetch_null_brands() -> list[dict]:
    rows, offset = [], 0
    while True:
        res = (
            sb.table(TABLE)
            .select("id, product_name, canonical_product_name")
            .is_("brand", "null")
            .not_.is_("product_name", "null")
            .range(offset, offset + BATCH - 1)
            .execute()
            .data or []
        )
        rows.extend(res)
        logger.info(f"Fetched {len(rows)} null-brand rows...")
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

    rows = fetch_null_brands()
    logger.info(f"Total null-brand rows: {len(rows)}")

    updated  = 0
    no_brand = 0
    shown    = 0

    for row in rows:
        product_name  = row.get("product_name") or ""
        old_canonical = row.get("canonical_product_name") or ""

        brand = extract_brand(product_name)
        if not brand:
            no_brand += 1
            continue

        # Rebuild canonical with the newly detected brand
        new_canonical = build_canonical_name(product_name, brand)
        if not new_canonical:
            new_canonical = old_canonical  # keep existing if rebuild fails

        if args.dry_run:
            if shown < 20:
                print(f"  {product_name[:60]}")
                print(f"  → brand={brand} | canonical={new_canonical}\n")
                shown += 1
            updated += 1
            continue

        try:
            update = {"brand": brand}
            if new_canonical and new_canonical != old_canonical:
                update["canonical_product_name"] = new_canonical
            sb.table(TABLE).update(update).eq("id", row["id"]).execute()
            updated += 1
        except Exception as e:
            logger.error(f"Failed id={row['id']}: {e}")
        time.sleep(0.01)

        if updated % 500 == 0:
            logger.info(f"  Updated {updated} rows...")

    print(f"\nDone.")
    print(f"  Updated (brand detected): {updated}")
    print(f"  Skipped (no brand found): {no_brand}")


if __name__ == "__main__":
    main()