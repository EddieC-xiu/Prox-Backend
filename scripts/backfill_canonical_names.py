# scripts/backfill_canonical_names.py
#
# Finds rows in test_flyer_deals_duplicate with no canonical_product_name
# and runs the normalizer against product_name to fill the gap.
#
# Usage:
#   PYTHONUTF8=1 PYTHONPATH=. python scripts/backfill_canonical_names.py --dry-run
#   PYTHONUTF8=1 PYTHONPATH=. python scripts/backfill_canonical_names.py

import time
import logging
import argparse
from config.supabase import get_supabase_client
from scoring.product_normalizer import extract_brand, build_canonical_name

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)

sb = get_supabase_client()

TABLE = "test_flyer_deals_duplicate"
BATCH = 500

# All grocery retailers — excludes pure non-grocery
# (Walgreens, CVS, Dollar Tree, Family Dollar, Sephora, Ulta, Sally Beauty,
#  Restaurant Depot, 7-Eleven, Petco, PetSmart, Total Wine, test_retailer)
TARGET_RETAILERS = {
    # Core grocery
    "kroger", "Kroger", "Kroger Delivery Now", "kroger delivery now",
    "target", "Target", "Target: Fast Delivery", "target: fast delivery",
    "ralphs", "Ralphs", "Ralphs Delivery Now", "ralphs delivery now",
    "smart_final", "Smart & Final",
    "food bazaar", "Food Bazaar",
    "Sprouts Farmers Market", "sprouts farmers market", "Sprouts Express",
    "Trader Joe's", "trader joe's",
    "Food4Less", "food4less",
    "Food4Less Delivery Now", "food4less delivery now",
    "food4less delivery now",
    "publix", "Publix",
    "safeway", "Safeway", "Safeway Rapid", "safeway rapid",
    "albertsons", "Albertsons",
    "vons", "Vons", "Vons Rapid", "vons rapid",
    "pavilions", "Pavilions",
    "ShopRite", "shoprite",
    "Wegmans", "wegmans",
    "Stop & Shop", "stop & shop",
    "Stop & Shop Express", "stop & shop express",
    # Warehouse / club
    "aldi", "ALDI", "ALDI Express",
    "Costco", "costco", "Costco Business Center",
    "Sam's Club", "sam's club",
    # Grocery chains
    "Food Lion", "food lion", "Food Lion Now",
    "FoodsCo", "foodsco", "FoodsCo Delivery Now",
    "FoodMaxx", "foodmaxx",
    "Giant Food", "giant food", "Giant Food Convenience", "GIANT",
    "Stater Bros.", "stater bros.", "Stater Bros. Now",
    "Rouses Markets", "rouses markets",
    "Harris Teeter", "harris teeter",
    "H-E-B", "h-e-b",
    "Meijer", "meijer",
    "Lucky Supermarkets", "lucky supermarkets",
    "Super 1 Foods", "super 1 foods",
    "Gelson's", "gelson's",
    "Key Food", "key food",
    "Key Food Marketplace", "key food marketplace",
    "Save Mart", "save mart", "Save Mart Express",
    "Bristol Farms", "bristol farms",
    "El Super", "el super",
    "Superior Grocers", "superior grocers",
    "Vallarta Supermarkets", "vallarta supermarkets",
    "H Mart", "hmart", "HMart",
    "Grocery Outlet", "grocery outlet",
    "Raley's", "raley's",
    "BJ's Wholesale Club", "bj's wholesale club",
    "Weis Markets", "weis markets",
    "The Fresh Market", "the fresh market",
    "Fairway", "fairway", "Fairway Now", "fairway now",
    "Western Beef", "western beef",
    "Gristedes", "gristedes",
    "Morton Williams Supermarket",
    "King Kullen", "king kullen",
    "Northgate Market", "northgate market",
    "Cardenas Markets", "cardenas markets",
    "Erewhon", "erewhon",
    "Bi-Rite Market",
    "Rainbow Grocery",
    "Lazy Acres",
    "Mollie Stone's Markets",
    "Plum Market",
    "Busch's Fresh Food Market",
    "Holiday Market",
    "walmart", "Walmart",
    # Small regional grocery
    "Matherne's Market",
    "Gus's Community Market",
    "Hi Nabor Supermarket",
    "Hubbens Supermarket",
    "Razco Foods Supermarket",
    "Food 4 Less Central Valley",
    "Jubilee Marketplace",
    "Ideal Market", "Ideal Food Basket",
    "Lamendola's Supermarket",
    "Pioneer Parkside Ave",
    "Andronico's Community Markets",
    "Aqui Supermarket",
    "99 Ranch Market", "99 ranch market",
    "fresco community market",
    "stew leonard's",
    "marukai wholesale mart",
    "United Markets",
    "Tower Market & Deli",
    "Save A Lot", "save a lot",
    "Detwiler's Farm Market",
    "C-Town Farmers Market - Forest Hills",
    "Pathmark",
    "Safeway", "Giant Food",
    "eataly", "Eataly",
    # Non-grocery but in-scope per Alston
"Walgreens", "walgreens",
"CVS®", "cvs®", "CVS", "cvs",
"Dollar Tree", "dollar tree",
"Family Dollar", "family dollar", "family-dollar",
"Restaurant Depot", "restaurant depot",
"Sally Beauty", "sally beauty",
"Ulta Beauty", "ulta beauty",
"Sephora", "sephora",
"7-Eleven", "7-eleven",
"Petco", "petco",
"PetSmart", "petsmart",
"Total Wine & More", "total wine & more",
"The Vitamin Shoppe®", "the vitamin shoppe",
"CHEF'STORE", "chef'store",
"Gordon Food Service Store", "gordon food service store",
"super-sal",
}


def fetch_nulls() -> list[dict]:
    rows, offset = [], 0
    while True:
        res = (
            sb.table(TABLE)
            .select("id, product_name, brand, retailer")
            .is_("canonical_product_name", "null")
            .not_.is_("product_name", "null")
            .range(offset, offset + BATCH - 1)
            .execute()
            .data or []
        )
        rows.extend(res)
        logger.info(f"Fetched {len(rows)} null canonical rows...")
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

    rows = fetch_nulls()
    logger.info(f"Total rows with no canonical name: {len(rows)}")

    updated = 0
    skipped_retailer = 0
    skipped_empty = 0

    for row in rows:
        retailer = row.get("retailer") or ""
        if retailer not in TARGET_RETAILERS:
            skipped_retailer += 1
            continue

        product_name = row.get("product_name") or ""
        existing_brand = row.get("brand")

        brand = existing_brand or extract_brand(product_name)
        canonical = build_canonical_name(product_name, brand)

        if not canonical or len(canonical) < 2:
            skipped_empty += 1
            continue

        if args.dry_run:
            if updated < 15:
                print(f"  {product_name[:70]}")
                print(f"  → brand={brand} | canonical={canonical}\n")
            updated += 1
            continue

        try:
            sb.table(TABLE).update({
                "canonical_product_name": canonical,
                "brand": brand,
            }).eq("id", row["id"]).execute()
            updated += 1
        except Exception as e:
            logger.error(f"Failed id={row['id']}: {e}")
        time.sleep(0.02)

        if updated % 500 == 0:
            logger.info(f"  Updated {updated} rows...")

    print(f"\nDone.")
    print(f"  Updated:            {updated}")
    print(f"  Skipped (retailer): {skipped_retailer}")
    print(f"  Skipped (empty):    {skipped_empty}")


if __name__ == "__main__":
    main()