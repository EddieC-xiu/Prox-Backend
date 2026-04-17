# scripts/import_osm_stores_phase5.py
# Loads phase-5 retailers into store_locations from OpenStreetMap (Overpass API).
# Targets all retailers still unmatched after phases 1-4 + backfill passes 1-9.
#
# Top unmatched after pass 9 (5 550 rows total):
#   restaurant depot  2115  (22 in SL, missing ~54 US locations + Jetro brand)
#   overland foods     315  (1 in SL, pass 9 missed — likely zip not in zips table)
#   hmart              240  (phase-4 OSM query returned 0 — broadened name list)
#   chef'store         159  (US Foods ChefStore)
#   windsor farms      110  (regional chain)
#   brooklyn fare      101  (NYC specialty)
#   pioneer            100  (NYC independent)
#   nam dae mun         98  (Atlanta-area)
#   the fresh grocer    98  (PA/NJ regional)
#   jubilee marketplace  90  (Long Island)
#   zabar's             84  (NYC Upper West Side)
#   azalea fresh mkt    80  (single store)
#   pathmark            78  (DEFUNCT — skip)
#   woods supermarket   74  (regional)
#   food way            70  (independent)
#   seasons kosher      70  (NYC/NJ kosher)
#   gordon restaurant   68  (Gordon Food Service Store — NOT same as restaurant depot)
#   country market      67  (independent)
#   dumbo market        65  (Brooklyn)
#   aron's kissena      60  (Flushing, Queens)
#
# IMPORTANT — retailer_keys must match the alias map in direct_backfill.py.
# New keys added here must also appear in ALIAS_MAP_P6 in that file.
#
# NOTE on hmart: phase 4 included H Mart but OSM returned 0 results because
# many H Mart locations are tagged with brand="H Mart" but name="H Mart [city]".
# Phase 5 adds a second OSM query strategy using brand tag only (no shop filter).
#
# Run with: PYTHONPATH=. python scripts/import_osm_stores_phase5.py

import os
import time
import psycopg2
import requests
from dotenv import load_dotenv

load_dotenv()

OVERPASS_URL            = "https://overpass-api.de/api/interpreter"
DELAY_BETWEEN_RETAILERS = 6    # seconds — be polite to Overpass
REQUEST_TIMEOUT         = 120

# ── Phase-5 retailer definitions ───────────────────────────────────────────
# (retailer_key, display_name_lowercase, [osm_brand_or_name_values_to_search])
PHASE_5_RETAILERS = [

    # ── Foodservice / Wholesale ────────────────────────────────────────────
    # Restaurant Depot: already 22 stores in SL from earlier phases, but the
    # full US footprint is ~76 locations.  Also absorbs Jetro Cash & Carry
    # (a Restaurant Depot brand) under the same retailer_key.
    ("restaurant_depot",    "restaurant depot",
     ["Restaurant Depot", "Jetro Cash & Carry", "Jetro",
      "Jetro Restaurant Depot"]),

    # Gordon Food Service Store is a SEPARATE company from Restaurant Depot.
    # Previously mis-aliased to restaurant_depot — corrected in direct_backfill.py.
    ("gordon_food_service",  "gordon food service store",
     ["Gordon Food Service Store", "Gordon Food Service",
      "Gordon Restaurant Market"]),

    # US Foods ChefStore (formerly Cash & Carry)
    ("chefstore",           "chef'store",
     ["Chef'Store", "US Foods Chef'Store", "US Foods ChefStore",
      "ChefStore", "Cash & Carry"]),

    # ── Asian / specialty grocery ──────────────────────────────────────────
    # H Mart: phase-4 query returned 0 results.  OSM tags these locations
    # with brand="H Mart" but name varies.  New strategy: query brand tag
    # directly without restricting to shop=* nodes.
    ("hmart",               "h mart",
     ["H Mart", "H-Mart", "Hmart",
      "H Mart Korean Supermarket", "H Mart Supermarket",
      "H Mart Korean Grocery Store"]),

    # Marukai / Tokyo Central (acquired, rebranded stores exist under both names)
    ("marukai",             "marukai",
     ["Marukai", "Marukai Market", "Marukai Wholesale Mart",
      "Tokyo Central", "Marukai Corporation"]),

    # ── Mid-Atlantic / Northeast regional ─────────────────────────────────
    ("fresh_grocer",        "the fresh grocer",
     ["The Fresh Grocer", "Fresh Grocer"]),

    ("price_rite",          "price rite",
     ["Price Rite", "Price Rite Marketplace", "PriceRite"]),

    # Village Super Market (NJ ShopRite licensee — stores branded "ShopRite"
    # but the company running them is Village)
    ("village_supermarket", "village supermarket",
     ["Village Super Market", "Village Supermarket"]),

    ("uncle_giuseppes",     "uncle giuseppe's marketplace",
     ["Uncle Giuseppe's Marketplace", "Uncle Giuseppe's"]),

    ("gristedes",           "gristedes",
     ["Gristedes", "Gristede's", "Gristede's Foods"]),

    # ── Southeast / Carolinas ──────────────────────────────────────────────
    ("lowes_foods",         "lowes foods",
     ["Lowes Foods", "Lowe's Foods"]),

    ("ingles",              "ingles",
     ["Ingles", "Ingles Markets", "Ingles Market"]),

    # ── NYC specialty / gourmet ────────────────────────────────────────────
    ("zabars",              "zabar's",
     ["Zabar's", "Zabars"]),

    ("brooklyn_fare",       "brooklyn fare",
     ["Brooklyn Fare", "Brooklyn Fare Market"]),

    ("eataly",              "eataly",
     ["Eataly", "Eataly NYC", "Eataly Chicago", "Eataly Los Angeles"]),

    # ── NYC kosher ────────────────────────────────────────────────────────
    ("seasons_kosher",      "seasons kosher supermarket",
     ["Seasons Kosher Supermarket", "Seasons Kosher", "Seasons"]),

    ("pomegranate_mkt",     "pomegranate supermarket",
     ["Pomegranate Supermarket", "Pomegranate"]),

    # ── National pet / specialty ───────────────────────────────────────────
    ("pet_supplies_plus",   "pet supplies plus",
     ["Pet Supplies Plus"]),

    ("wild_fork",           "wild fork",
     ["Wild Fork", "Wild Fork Foods"]),

    # ── Natural / wellness ─────────────────────────────────────────────────
    ("mothers_market",      "mother's market",
     ["Mother's Market", "Mother's Market & Kitchen"]),

    # ── Mountain West ─────────────────────────────────────────────────────
    ("ridleys",             "ridley's",
     ["Ridley's Family Market", "Ridley's", "Ridleys",
      "Ridley's Family Markets"]),

    # ── Southeast (Atlanta area) ──────────────────────────────────────────
    ("nam_dae_mun",         "nam dae mun farmers market",
     ["Nam Dae Mun Farmers Market", "Nam Dae Mun"]),

    # ── NYC / Long Island indie ───────────────────────────────────────────
    ("jubilee_marketplace", "jubilee marketplace",
     ["Jubilee Marketplace"]),

    ("americas_food_basket", "america's food basket",
     ["America's Food Basket", "Americas Food Basket"]),

    # ── Liquor / specialty ────────────────────────────────────────────────
    # 'ladd liquor' and 'odyssey liquor' are independent stores — unlikely
    # to be in OSM with enough tagging.  Skipped intentionally; see
    # scripts/seed_local_stores.py for manual inserts.
]


# ── OSM query builder ──────────────────────────────────────────────────────

def _build_query(brand_names: list[str]) -> str:
    """
    Overpass QL: query by brand= AND name= tags for all provided names, US only.
    Also queries brand= tag without shop= restriction to catch retailers that
    OSM has tagged inconsistently (e.g. H Mart nodes without a shop tag).
    """
    parts = []
    for name in brand_names:
        esc = name.replace('"', '\\"')
        # Standard shop nodes/ways
        parts.append(f'  node["brand"="{esc}"](area.us);')
        parts.append(f'  way["brand"="{esc}"](area.us);')
        parts.append(f'  node["name"="{esc}"]["shop"](area.us);')
        parts.append(f'  way["name"="{esc}"]["shop"](area.us);')
        # Broader: brand tag only (no shop filter) — catches H Mart etc.
        parts.append(f'  node["brand"="{esc}"]["addr:postcode"](area.us);')
        parts.append(f'  way["brand"="{esc}"]["addr:postcode"](area.us);')
    return (
        "[out:json][timeout:90];\n"
        'area["ISO3166-1:alpha2"="US"]->.us;\n'
        "(\n"
        + "\n".join(parts) +
        "\n);\n"
        "out center tags;\n"
    )


def _fetch(brand_names: list[str], retries: int = 3) -> list[dict]:
    query = _build_query(brand_names)
    for attempt in range(1, retries + 1):
        try:
            resp = requests.post(
                OVERPASS_URL,
                data={"data": query},
                timeout=REQUEST_TIMEOUT,
            )
            resp.raise_for_status()
            return resp.json().get("elements", [])
        except Exception as exc:
            print(f"    ⚠️  attempt {attempt}/{retries} failed: {exc}")
            if attempt < retries:
                time.sleep(15 * attempt)
    return []


# ── Row extractor ──────────────────────────────────────────────────────────

def _to_row(el: dict, retailer_key: str, display_name: str) -> dict | None:
    tags = el.get("tags", {})

    zip_code = (tags.get("addr:postcode") or "").strip()
    if not zip_code:
        return None
    zip_code = zip_code.split("-")[0].strip()
    if len(zip_code) != 5 or not zip_code.isdigit():
        return None

    if el["type"] == "node":
        lat, lon = el.get("lat"), el.get("lon")
    else:
        c = el.get("center", {})
        lat, lon = c.get("lat"), c.get("lon")

    num    = tags.get("addr:housenumber", "")
    street = tags.get("addr:street", "")
    city   = tags.get("addr:city", "")
    state  = tags.get("addr:state", "")
    parts  = " ".join(p for p in [num, street] if p)
    if parts and city:
        parts = f"{parts}, {city}, {state}".strip(", ")
    address = parts or None

    return {
        "retailer_key":       retailer_key,
        "retailer":           display_name,
        "zip_code":           zip_code,
        "address":            address,
        "full_address":       address,
        "latitude":           lat,
        "longitude":          lon,
        "geocode_source":     "osm",
        "geocode_confidence": "exact" if (lat and lon) else "zip",
    }


# ── DB upsert ──────────────────────────────────────────────────────────────

def _upsert(cur, rows: list[dict]) -> int:
    count = 0
    for row in rows:
        cur.execute("""
            INSERT INTO store_locations
                (retailer_key, retailer, zip_code, address, full_address,
                 latitude, longitude, geocode_source, geocode_confidence)
            VALUES
                (%(retailer_key)s, %(retailer)s, %(zip_code)s, %(address)s,
                 %(full_address)s, %(latitude)s, %(longitude)s,
                 %(geocode_source)s, %(geocode_confidence)s)
            ON CONFLICT (retailer_key, zip_code)
            DO UPDATE SET
                latitude           = COALESCE(EXCLUDED.latitude,  store_locations.latitude),
                longitude          = COALESCE(EXCLUDED.longitude, store_locations.longitude),
                geocode_source     = EXCLUDED.geocode_source,
                geocode_confidence = EXCLUDED.geocode_confidence,
                address            = COALESCE(EXCLUDED.address,   store_locations.address)
        """, row)
        count += cur.rowcount
    return count


# ── Main ───────────────────────────────────────────────────────────────────

def main():
    conn = psycopg2.connect(os.environ["DATABASE_URL"])
    conn.autocommit = False
    cur  = conn.cursor()

    grand_total = 0
    grand_nozip = 0

    for retailer_key, display_name, brand_names in PHASE_5_RETAILERS:
        print(f"\n[{retailer_key}]  searching: {brand_names}")

        elements = _fetch(brand_names)
        print(f"  OSM elements returned: {len(elements)}")

        rows   = [_to_row(el, retailer_key, display_name) for el in elements]
        rows   = [r for r in rows if r]
        no_zip = len(elements) - len(rows)

        # Deduplicate by both (retailer_key, zip_code) AND (retailer_key, address)
        seen_zip, seen_addr, deduped = set(), set(), []
        for r in rows:
            k_zip  = (r["retailer_key"], r["zip_code"])
            k_addr = (r["retailer_key"], r["address"]) if r["address"] else None
            if k_zip in seen_zip:
                continue
            if k_addr and k_addr in seen_addr:
                continue
            seen_zip.add(k_zip)
            if k_addr:
                seen_addr.add(k_addr)
            deduped.append(r)

        print(f"  Valid rows: {len(deduped)}  (dropped {no_zip} no-zip, "
              f"{len(rows) - len(deduped)} dup-zip/addr)")

        if deduped:
            n = _upsert(cur, deduped)
            conn.commit()
            grand_total += n
            grand_nozip += no_zip
            print(f"  ✅ {n} rows upserted")
        else:
            print(f"  ⚠️  nothing to insert for {retailer_key}")

        time.sleep(DELAY_BETWEEN_RETAILERS)

    # ── Summary ────────────────────────────────────────────────────────────
    print("\n── Phase-5 import complete ──────────────────────────────────────────────")
    print(f"  Total rows upserted : {grand_total:,}")
    print(f"  Total skipped no-zip: {grand_nozip:,}")

    print("\n── Store counts per retailer (after import) ─────────────────────────────")
    cur.execute("""
        SELECT retailer_key, COUNT(*) AS cnt
        FROM store_locations
        WHERE retailer_key = ANY(%s)
        GROUP BY retailer_key
        ORDER BY cnt DESC
    """, ([rk for rk, _, _ in PHASE_5_RETAILERS],))
    for rk, cnt in cur.fetchall():
        print(f"  {rk:<40}  {cnt:>5} stores")

    cur.close()
    conn.close()
    print("\nNext steps:")
    print("  1. PYTHONPATH=. python scripts/seed_local_stores.py")
    print("  2. PYTHONPATH=. python scripts/direct_backfill.py")


if __name__ == "__main__":
    main()
