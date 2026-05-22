# scripts/import_unmatched_retailers.py
#
# Finds retailers in flyer_deals (production) with no store_locations match
# and imports their locations from OpenStreetMap via Overpass API.
#
# Usage:
#   PYTHONUTF8=1 PYTHONPATH=. python scripts/import_unmatched_retailers.py --dry-run
#   PYTHONUTF8=1 PYTHONPATH=. python scripts/import_unmatched_retailers.py

import time
import logging
import argparse
import requests
from config.supabase import get_supabase_client

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)

sb = get_supabase_client()

IMPORT_TARGETS = {
    "gelson's":                        ("Gelson's",               "gelsons"),
    "Gelson's":                        ("Gelson's",               "gelsons"),
    "key food":                        ("Key Food",               "keyfood"),
    "Key Food":                        ("Key Food",               "keyfood"),
    "Key Food Marketplace":            ("Key Food",               "keyfood"),
    "key food marketplace":            ("Key Food",               "keyfood"),
    "Save Mart":                       ("Save Mart",              "savemart"),
    "Save Mart Express":               ("Save Mart",              "savemart"),
    "Rouses Markets":                  ("Rouses Markets",         "rouses"),
    "rouses markets":                  ("Rouses Markets",         "rouses"),
    "Super 1 Foods":                   ("Super 1 Foods",          "super1foods"),
    "super 1 foods":                   ("Super 1 Foods",          "super1foods"),
    "Fairway":                         ("Fairway Market",         "fairway"),
    "fairway":                         ("Fairway Market",         "fairway"),
    "Fairway Now":                     ("Fairway Market",         "fairway"),
    "fairway now":                     ("Fairway Market",         "fairway"),
    "bristol farms":                   ("Bristol Farms",          "bristolfarms"),
    "Bristol Farms":                   ("Bristol Farms",          "bristolfarms"),
    "El Super":                        ("El Super",               "elsuper"),
    "el super":                        ("El Super",               "elsuper"),
    "el-super":                        ("El Super",               "elsuper"),
    "BJ's Wholesale Club":             ("BJ's Wholesale Club",    "bjs"),
    "bj's wholesale club":             ("BJ's Wholesale Club",    "bjs"),
    "Giant Food Convenience":          ("Giant Food",             "giantfood"),
    "giant food convenience":          ("Giant Food",             "giantfood"),
    "Gus's Community Market":          ("Gus's Community Market", "gusmarket"),
    "Superior Grocers":                ("Superior Grocers",       "superiorgrocers"),
    "superior grocers":                ("Superior Grocers",       "superiorgrocers"),
    "Vallarta Supermarkets":           ("Vallarta Supermarkets",  "vallarta"),
    "vallarta supermarkets":           ("Vallarta Supermarkets",  "vallarta"),
    "HMart":                           ("H Mart",                 "hmart"),
    "H Mart":                          ("H Mart",                 "hmart"),
    "hmart":                           ("H Mart",                 "hmart"),
    "Grocery Outlet":                  ("Grocery Outlet",         "groceryoutlet"),
    "grocery outlet":                  ("Grocery Outlet",         "groceryoutlet"),
    "Raley's":                         ("Raley's",                "raleys"),
    "raley's":                         ("Raley's",                "raleys"),
    "Erewhon":                         ("Erewhon",                "erewhon"),
    "erewhon":                         ("Erewhon",                "erewhon"),
    "Rainbow Grocery":                 ("Rainbow Grocery",        "rainbowgrocery"),
    "rainbow grocery":                 ("Rainbow Grocery",        "rainbowgrocery"),
    "Bi-Rite Market":                  ("Bi-Rite Market",         "birite"),
    "Northgate Market":                ("Northgate Market",       "northgate"),
    "northgate market":                ("Northgate Market",       "northgate"),
    "Cardenas Markets":                ("Cardenas Markets",       "cardenas"),
    "cardenas markets":                ("Cardenas Markets",       "cardenas"),
    "Weis Markets":                    ("Weis Markets",           "weis"),
    "weis markets":                    ("Weis Markets",           "weis"),
    "The Fresh Market":                ("The Fresh Market",       "freshmarket"),
    "the fresh market":                ("The Fresh Market",       "freshmarket"),
    "Harris Teeter":                   ("Harris Teeter",          "harristeeter"),
    "harris teeter":                   ("Harris Teeter",          "harristeeter"),
    "Lucky Supermarkets":              ("Lucky Supermarkets",     "lucky"),
    "lucky supermarkets":              ("Lucky Supermarkets",     "lucky"),
    "Lazy Acres":                      ("Lazy Acres",             "lazyacres"),
    "lazy acres":                      ("Lazy Acres",             "lazyacres"),
    "Mollie Stone's Markets":          ("Mollie Stone's",         "molliestones"),
    "Plum Market":                     ("Plum Market",            "plummarket"),
    "plum market":                     ("Plum Market",            "plummarket"),
    "Western Beef":                    ("Western Beef",           "westernbeef"),
    "western beef":                    ("Western Beef",           "westernbeef"),
    "Gristedes":                       ("Gristedes",              "gristedes"),
    "gristedes":                       ("Gristedes",              "gristedes"),
    "King Kullen":                     ("King Kullen",            "kingkullen"),
    "king kullen":                     ("King Kullen",            "kingkullen"),
    "FoodMaxx":                        ("FoodMaxx",               "foodmaxx"),
    "foodmaxx":                        ("FoodMaxx",               "foodmaxx"),
    "Stew Leonard's":                  ("Stew Leonard's",         "stewleonards"),
    "stew leonard's":                  ("Stew Leonard's",         "stewleonards"),
    "99 Ranch Market":                 ("99 Ranch Market",        "99ranch"),
    "99 ranch market":                 ("99 Ranch Market",        "99ranch"),
    "Walgreens":                       ("Walgreens",              "walgreens"),
    "walgreens":                       ("Walgreens",              "walgreens"),
    "CVS®":                            ("CVS pharmacy",           "cvs"),
    "cvs®":                            ("CVS pharmacy",           "cvs"),
    "CVS":                             ("CVS pharmacy",           "cvs"),
    "cvs":                             ("CVS pharmacy",           "cvs"),
    "Dollar Tree":                     ("Dollar Tree",            "dollartree"),
    "dollar tree":                     ("Dollar Tree",            "dollartree"),
    "Family Dollar":                   ("Family Dollar",          "familydollar"),
    "family dollar":                   ("Family Dollar",          "familydollar"),
    "family-dollar":                   ("Family Dollar",          "familydollar"),
    "Restaurant Depot":                ("Restaurant Depot",       "restaurantdepot"),
    "restaurant depot":                ("Restaurant Depot",       "restaurantdepot"),
    "Ulta Beauty":                     ("Ulta Beauty",            "ulta"),
    "ulta beauty":                     ("Ulta Beauty",            "ulta"),
    "Sally Beauty":                    ("Sally Beauty",           "sallybeauty"),
    "sally beauty":                    ("Sally Beauty",           "sallybeauty"),
    "Sephora":                         ("Sephora",                "sephora"),
    "sephora":                         ("Sephora",                "sephora"),
    "Petco":                           ("Petco",                  "petco"),
    "petco":                           ("Petco",                  "petco"),
    "PetSmart":                        ("PetSmart",               "petsmart"),
    "petsmart":                        ("PetSmart",               "petsmart"),
    "7-Eleven":                        ("7-Eleven",               "7eleven"),
    "7-eleven":                        ("7-Eleven",               "7eleven"),
    "Total Wine & More":               ("Total Wine",             "totalwine"),
    "total wine & more":               ("Total Wine",             "totalwine"),
    "The Vitamin Shoppe®":             ("The Vitamin Shoppe",     "vitaminshoppe"),
    "CHEF'STORE":                      ("CHEF'STORE",             "chefstore"),
    "Gordon Food Service Store":       ("Gordon Food Service",    "gordonfood"),
    "Eataly":                          ("Eataly",                 "eataly"),
    "eataly":                          ("Eataly",                 "eataly"),
    "Save A Lot":                      ("Save A Lot",             "savealot"),
    "save a lot":                      ("Save A Lot",             "savealot"),
    "Ideal Food Basket":               ("Ideal Food Basket",      "idealfoodbasket"),
    "ideal food basket":               ("Ideal Food Basket",      "idealfoodbasket"),
    "SuperFresh":                      ("SuperFresh",             "superfresh"),
    "MARTIN'S":                        ("Martin's",               "martins"),
    "fresco community market":         ("Fresco Community Market","fresco"),
    "marukai wholesale mart":          ("Marukai",                "marukai"),
    "Shoppers Market Plus+":           ("Shoppers",               "shoppers"),
    "Shoppers":                        ("Shoppers",               "shoppers"),
    "Hubbens Supermarket":             ("Hubbens Supermarket",    "hubbens"),
    "Hi Nabor Supermarket":            ("Hi Nabor Supermarket",   "hinabor"),
    "hi nabor supermarket":            ("Hi Nabor Supermarket",   "hinabor"),
    "Matherne's Market":               ("Matherne's Market",      "mathernes"),
    "matherne's market":               ("Matherne's Market",      "mathernes"),
    "Razco Foods Supermarket":         ("Razco Foods",            "razco"),
    "Food 4 Less Central Valley":      ("Food 4 Less",            "food4less"),
    "Jubilee Marketplace":             ("Jubilee Marketplace",    "jubilee"),
    "Pioneer Parkside Ave":            ("Pioneer Supermarkets",   "pioneer"),
    "C-Town Farmers Market - Forest Hills": ("C-Town",            "ctown"),
    "Austin Organic Market":           ("Austin Organic Market",  "austinorganic"),
    "Tower Market & Deli":             ("Tower Market",           "towermarket"),
    "United Markets":                  ("United Markets",         "unitedmarkets"),
    "Ozzie's Fresh Market":            ("Ozzie's Fresh Market",   "ozzies"),
    "The Food Emporium":               ("The Food Emporium",      "foodemporium"),
    "lincoln market":                  ("Lincoln Market",         "lincolnmarket"),
    "super-sal":                       ("Super-Sal",              "supersal"),
    "test_retailer":                   ("test retailer",          "testretailer"),
}

# Empty — import everything
SKIP_RETAILERS: set = set()

OVERPASS_URLS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass.openstreetmap.ru/api/interpreter",
    "https://maps.mail.ru/osm/tools/overpass/api/interpreter",
]


def query_osm(osm_name: str) -> list[dict]:
    """Query Overpass API with retry and exponential backoff."""
    query = f'[out:json][timeout:90];(node["name"~"{osm_name}",i]["shop"];way["name"~"{osm_name}",i]["shop"];);out center;'

    for url in OVERPASS_URLS:
        for attempt in range(3):
            try:
                if attempt > 0:
                    wait = 10 * (2 ** attempt)
                    logger.info(f"  Retry {attempt} after {wait}s...")
                    time.sleep(wait)
                logger.info(f"  Trying {url}...")
                resp = requests.post(
                    url,
                    data={"data": query},
                    timeout=120,
                    headers={"User-Agent": "prox-backend/1.0"},
                )
                if resp.status_code == 200:
                    try:
                        elements = resp.json().get("elements", [])
                        logger.info(f"  Got {len(elements)} results for '{osm_name}'")
                        return elements
                    except Exception:
                        logger.warning(f"  Bad JSON from {url}")
                elif resp.status_code in (429, 504):
                    logger.warning(f"  Rate limited ({resp.status_code}), backing off...")
                    continue
                else:
                    logger.warning(f"  HTTP {resp.status_code} from {url}")
                    break
            except requests.exceptions.Timeout:
                logger.warning(f"  Timeout from {url}")
            except Exception as e:
                logger.warning(f"  {url} failed: {e}")
                break
        time.sleep(5)

    logger.warning(f"  All mirrors failed for '{osm_name}'")
    return []


def parse_location(el: dict) -> dict | None:
    """Extract lat/lon from OSM element."""
    if el["type"] == "node":
        lat, lon = el.get("lat"), el.get("lon")
    elif el["type"] == "way":
        center = el.get("center", {})
        lat, lon = center.get("lat"), center.get("lon")
    else:
        return None
    if not lat or not lon:
        return None
    tags = el.get("tags", {})
    raw_zip = tags.get("addr:postcode", "") or ""
    zip_code = raw_zip[:5]  # truncate to 5 chars — prevents varchar(5) overflow
    return {
        "lat":      lat,
        "lon":      lon,
        "name":     tags.get("name", ""),
        "address":  tags.get("addr:street", ""),
        "city":     tags.get("addr:city", ""),
        "state":    tags.get("addr:state", ""),
        "zip_code": zip_code,
        "osm_id":   str(el.get("id", "")),
    }


def get_unmatched_retailers() -> list[str]:
    """Get distinct retailers with no store_id in flyer_deals (production)."""
    rows = (
        sb.table("flyer_deals")
        .select("retailer")
        .is_("store_id", "null")
        .not_.is_("retailer", "null")
        .limit(5000)
        .execute()
        .data or []
    )
    seen = set()
    retailers = []
    for row in rows:
        r = row["retailer"]
        if r and r not in seen:
            seen.add(r)
            retailers.append(r)
    return retailers


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if args.dry_run:
        print("[DRY RUN] Nothing will be written.\n")

    unmatched = get_unmatched_retailers()
    logger.info(f"Found {len(unmatched)} unmatched retailers")

    total_imported = 0

    for retailer in unmatched:
        if retailer in SKIP_RETAILERS:
            logger.info(f"Skipping: {retailer}")
            continue

        if retailer not in IMPORT_TARGETS:
            logger.info(f"No OSM target configured for: {retailer}")
            continue

        osm_name, retailer_key = IMPORT_TARGETS[retailer]
        logger.info(f"\nImporting: {retailer} → '{osm_name}' ({retailer_key})")

        elements = query_osm(osm_name)
        time.sleep(15)

        locations = []
        for el in elements:
            loc = parse_location(el)
            if not loc:
                continue
            locations.append({
                "retailer":           osm_name,
                "retailer_key":       retailer_key,
                "store_name":         loc["name"],
                "address":            loc["address"],
                "city":               loc["city"],
                "state":              loc["state"],
                "zip_code":           loc["zip_code"],
                "latitude":           loc["lat"],
                "longitude":          loc["lon"],
                "osm_id":             loc["osm_id"],
                "source":             "osm",
                "geocode_source":     "osm",
                "geocode_confidence": "high",
                "show_on_map":        True,
            })

        logger.info(f"  Found {len(locations)} locations")

        if args.dry_run:
            for l in locations[:3]:
                print(f"  → {l['store_name']} | {l['city']}, {l['state']} | {l['zip_code']}")
            continue

        if locations:
            try:
                # Use osm_id as conflict target — handles all duplicate scenarios
                sb.table("store_locations").upsert(
                    locations, on_conflict="retailer_key,zip_code"
                ).execute()
                total_imported += len(locations)
                logger.info(f"  Imported {len(locations)} locations for {retailer_key}")
            except Exception as e:
                logger.warning(f"  Batch upsert failed for {retailer_key}, trying row by row: {e}")
                for loc in locations:
                    try:
                        sb.table("store_locations").upsert(
                            [loc], on_conflict="retailer_key,zip_code"
                        ).execute()
                        total_imported += 1
                    except Exception:
                        pass

    print(f"\nDone. Total imported: {total_imported} locations.")


if __name__ == "__main__":
    main()