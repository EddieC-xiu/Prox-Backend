# scripts/direct_backfill.py
# Multi-pass store_id backfill for flyer_deals.
#
# Pass 1 — retailer_key + zip exact match
# Pass 2 — retailer display name + zip exact match
# Pass 3 — retailer_key = sl.retailer (key → display name cross-match) + zip
# Pass 4 — delivery/express suffix variants joined to sl.retailer_key
# Pass 5 — delivery/express suffix variants joined to sl.retailer (display name)
# Pass 6 — alias map: fd.retailer variant → sl.retailer_key canonical
# Pass 7 — zip-3 prefix fallback using fd.retailer_key (single-match guarantee)
# Pass 8 — alias map + zip-3 prefix fallback for rows where retailer_key IS NULL
#           (resolves fd.retailer → sl.retailer_key via alias table, then zip-3)
# Pass 9 — nearest store by zip centroid (PostGIS, ≤ 80 km cap)
#           (handles cases where fd.zip_code is a CUSTOMER/DELIVERY zip, not the
#            store's zip — so exact-zip and zip-3 passes never fire even though
#            stores exist in store_locations)
# Pass 10 — nearest store, extended 200 km cap (wholesale / sparse retailers only)
#            (restaurant_depot, gordon_food_service, chefstore, overland_foods)
#            Wholesale customers legitimately drive 100-200 km to a cash-and-carry.
#
# All passes are idempotent (check store_id IS NULL).
# Re-run freely after any new stores are loaded into store_locations.
#
# Run with: PYTHONPATH=. python scripts/direct_backfill.py

import psycopg2
import os
from dotenv import load_dotenv

load_dotenv()

conn = psycopg2.connect(os.environ["DATABASE_URL"])
conn.autocommit = False
cur  = conn.cursor()

BATCH_SIZE = 10000


# ── Pass 1: retailer_key + zip exact match ────────────────────────────────
print("Pass 1: retailer_key + zip_code exact match …")
cur.execute("""
    UPDATE flyer_deals fd
    SET
        store_id         = sl.id,
        match_confidence = 'zip_single',
        matched_by       = 'sql_backfill'
    FROM store_locations sl
    WHERE sl.retailer_key = fd.retailer_key
      AND sl.zip_code     = fd.zip_code
      AND fd.store_id IS NULL
""")
p1 = cur.rowcount
conn.commit()
print(f"  Pass 1 done — {p1:,} rows updated\n")


# ── Pass 2: retailer display name + zip exact match ───────────────────────
print("Pass 2: retailer (display name) + zip_code exact match …")
cur.execute("""
    UPDATE flyer_deals fd
    SET
        store_id         = sl.id,
        match_confidence = 'zip_retailer_name',
        matched_by       = 'sql_backfill'
    FROM store_locations sl
    WHERE sl.retailer = fd.retailer
      AND sl.zip_code = fd.zip_code
      AND fd.store_id IS NULL
""")
p2 = cur.rowcount
conn.commit()
print(f"  Pass 2 done — {p2:,} rows updated\n")


# ── Pass 3: fd.retailer_key = sl.retailer (cross-match) + zip ─────────────
print("Pass 3: fd.retailer_key = sl.retailer + zip_code …")
cur.execute("""
    UPDATE flyer_deals fd
    SET
        store_id         = sl.id,
        match_confidence = 'zip_key_to_name',
        matched_by       = 'sql_backfill'
    FROM store_locations sl
    WHERE sl.retailer = fd.retailer_key
      AND sl.zip_code = fd.zip_code
      AND fd.store_id IS NULL
""")
p3 = cur.rowcount
conn.commit()
print(f"  Pass 3 done — {p3:,} rows updated\n")


# ── Pass 4: delivery/express suffix variants via sl.retailer_key ──────────
# fd.retailer has a suffix variant; join to the base retailer_key in SL.
SUFFIX_MAP_P4 = {
    # Kroger family
    'kroger delivery now':                'kroger',
    'kroger marketplace':                 'kroger',
    'ralphs delivery now':                'ralphs',
    'king soopers delivery now':          'kingsoopers',
    'fred meyer delivery now':            'fredmeyer',
    'harris teeter delivery now':         'harristeeter',
    'smith\'s delivery now':              'smiths',
    'pick \'n save delivery now':         'picknsave',
    'food4less delivery now':             'food4less',
    'qfc delivery now':                   'kroger',

    # Albertsons family
    'safeway delivery now':               'safeway',
    'safeway rapid':                      'safeway',
    'albertsons delivery now':            'albertsons',
    'vons delivery now':                  'vons',
    'jewel-osco delivery now':            'jewelosco',
    'acme markets delivery now':          'acmemarkets',
    'shaw\'s delivery now':               'shaws',
    'star market delivery now':           'starmarket',
    'tom thumb delivery now':             'tomthumb',
    'randalls delivery now':              'randalls',
    'haggen delivery now':                'haggen',

    # Big box
    'walmart delivery now':               'walmart',
    'walmart express':                    'walmart',
    'walmart supercenter':                'walmart',
    'walmart neighborhood market':        'walmart',
    'wal-mart':                           'walmart',
    'target express':                     'target',
    'super target':                       'target',
    'costco delivery now':                'costco',
    'costco business center':             'costco',
    'costco wholesale':                   'costco',
    'sam\'s club delivery now':           'samsclub',

    # Other major chains
    'whole foods delivery now':           'wholefoods',
    'whole foods market':                 'wholefoods',
    'trader joe\'s delivery now':         'traderjoes',
    'sprouts delivery now':               'sprouts',
    'aldi delivery now':                  'aldi',
    'meijer delivery now':                'meijer',
    'h-e-b delivery now':                 'heb',
    'h-e-b plus':                         'heb',
    'h-e-b plus!':                        'heb',
    'winn-dixie delivery now':            'winndixie',
    'giant eagle delivery now':           'gianteagle',
    'publix delivery now':                'publix',
    'wegmans delivery now':               'wegmans',
    'shoprite delivery now':              'shoprite',
    'stop & shop delivery now':           'stopandshop',
    'food lion delivery now':             'foodlion',
    'smart & final delivery now':         'smart_and_final',
    'smart & final express':              'smart_and_final',
    'smart & final extra!':               'smart_and_final',
    'stater bros delivery now':           'staterbros',
    'giant food delivery now':            'giantfood',
    'harris teeter express lane':         'harristeeter',

    # Phase-2 retailers (loaded by import_osm_stores_phase2.py)
    'the fresh market delivery now':      'the_fresh_market',
    'grocery outlet delivery now':        'grocery_outlet',
    'natural grocers delivery now':       'natural_grocers',
    'fresh thyme delivery now':           'fresh_thyme',
    'bj\'s delivery now':                 'bjs',
    'save-a-lot delivery now':            'save_a_lot',
    'save mart delivery now':             'save_mart',
    'rouses delivery now':                'rouses',
}

print("Pass 4: suffix variants via sl.retailer_key (batched) …")
total_p4 = 0

for variant, base_key in SUFFIX_MAP_P4.items():
    variant_total = 0
    while True:
        cur.execute("""
            SELECT fd.id
            FROM flyer_deals fd
            JOIN store_locations sl
              ON sl.retailer_key = %s
             AND sl.zip_code     = fd.zip_code
            WHERE fd.retailer  = %s
              AND fd.store_id IS NULL
            LIMIT %s
        """, (base_key, variant, BATCH_SIZE))
        ids = [row[0] for row in cur.fetchall()]
        if not ids:
            break
        cur.execute("""
            UPDATE flyer_deals fd
            SET
                store_id         = sl.id,
                match_confidence = 'zip_retailer_suffix_variant',
                matched_by       = 'sql_backfill'
            FROM store_locations sl
            WHERE sl.retailer_key = %s
              AND sl.zip_code     = fd.zip_code
              AND fd.id           = ANY(%s)
        """, (base_key, ids))
        updated = cur.rowcount
        conn.commit()
        variant_total += updated
        total_p4    += updated
    if variant_total > 0:
        print(f"  [{variant}] → {variant_total:,} rows")

print(f"  Pass 4 done — {total_p4:,} rows updated\n")


# ── Pass 5: suffix variants via sl.retailer (display name) ────────────────
SUFFIX_MAP_P5 = {
    'stop & shop express':       'stop & shop',
    'king soopers delivery now': 'king soopers',
    'giant food convenience':    'giant food',
    'food lion now':             'food lion',
    'fairway now':               'fairway market',
    'tfm express':               'the fresh market',
    'pavilions rapid':           'pavilions',
}

print("Pass 5: suffix variants via sl.retailer (display name, batched) …")
total_p5 = 0

for variant, base in SUFFIX_MAP_P5.items():
    variant_total = 0
    while True:
        cur.execute("""
            SELECT fd.id
            FROM flyer_deals fd
            JOIN store_locations sl
              ON sl.retailer = %s
             AND sl.zip_code = fd.zip_code
            WHERE fd.retailer  = %s
              AND fd.store_id IS NULL
            LIMIT %s
        """, (base, variant, BATCH_SIZE))
        ids = [row[0] for row in cur.fetchall()]
        if not ids:
            break
        cur.execute("""
            UPDATE flyer_deals fd
            SET
                store_id         = sl.id,
                match_confidence = 'zip_retailer_suffix_variant',
                matched_by       = 'sql_backfill'
            FROM store_locations sl
            WHERE sl.retailer = %s
              AND sl.zip_code  = fd.zip_code
              AND fd.id        = ANY(%s)
        """, (base, ids))
        updated = cur.rowcount
        conn.commit()
        variant_total += updated
        total_p5    += updated
    if variant_total > 0:
        print(f"  [{variant}] → {variant_total:,} rows")

print(f"  Pass 5 done — {total_p5:,} rows updated\n")


# ── Pass 6: alias map — fd.retailer variant → sl.retailer_key canonical ──
# Covers cases not handled by passes 1-5:
#   - Display name aliases that differ from the retailer_key
#   - Retailer family variants
#   - Phase-2/3/4 retailers once loaded by their import scripts
ALIAS_MAP_P6 = {
    # ── Costco ────────────────────────────────────────────────────────────
    'costco business center':             'costco',
    'costco wholesale':                   'costco',

    # ── Whole Foods ───────────────────────────────────────────────────────
    'whole foods market':                 'wholefoods',
    'whole foods':                        'wholefoods',

    # ── Trader Joe's ──────────────────────────────────────────────────────
    "trader joe's":                       'traderjoes',
    'trader joes':                        'traderjoes',

    # ── H-E-B ─────────────────────────────────────────────────────────────
    'h-e-b plus':                         'heb',
    'h-e-b plus!':                        'heb',
    'h-e-b':                              'heb',

    # ── Walmart ───────────────────────────────────────────────────────────
    'walmart supercenter':                'walmart',
    'walmart neighborhood market':        'walmart',
    'walmart express':                    'walmart',
    'wal-mart':                           'walmart',
    'wal-mart supercenter':               'walmart',

    # ── Target ────────────────────────────────────────────────────────────
    'super target':                       'target',
    'target small format':                'target',
    'target express':                     'target',

    # ── Sam's Club ────────────────────────────────────────────────────────
    "sam's club":                         'samsclub',
    'sams club':                          'samsclub',

    # ── CVS ───────────────────────────────────────────────────────────────
    'cvs®':                               'cvs',
    'cvs pharmacy':                       'cvs',

    # ── Walgreens ─────────────────────────────────────────────────────────
    'walgreens pharmacy':                 'walgreens',
    'walgreens boots alliance':           'walgreens',

    # ── Kroger family ─────────────────────────────────────────────────────
    'kroger marketplace':                 'kroger',
    'kroger fresh fare':                  'kroger',
    'qfc':                                'kroger',
    'marianos':                           'kroger',
    "mariano's":                          'kroger',
    'foodsco':                            'kroger',
    'foodmaxx':                           'kroger',
    'city market':                        'kroger',
    'dillons':                            'kroger',
    'gerbes':                             'kroger',
    'ruler foods':                        'kroger',
    'metro market':                       'kroger',
    'king soopers':                       'kingsoopers',
    'fred meyer':                         'fredmeyer',
    "smith's":                            'smiths',
    "smith's food and drug":              'smiths',
    "pick 'n save":                       'picknsave',
    'pick n save':                        'picknsave',
    'food 4 less':                        'food4less',

    # ── Albertsons family ─────────────────────────────────────────────────
    'albertsons market':                  'albertsons',
    "andronico's community markets":      'albertsons',
    'lucky supermarkets':                 'albertsons',
    'amigos':                             'albertsons',
    'pavilions':                          'albertsons',

    # ─ Safeway ───────────────────────────────────────────────────────────
    'safeway rapid':                      'safeway',

    # ── Jewel-Osco ────────────────────────────────────────────────────────
    'jewel-osco':                         'jewelosco',
    'jewel osco':                         'jewelosco',
    'jewel':                              'jewelosco',

    # ── Giant Food ────────────────────────────────────────────────────────
    "martin's food markets":              'giantfood',
    "martin's":                           'giantfood',
    'giant food convenience':             'giantfood',

    # ── Harris Teeter ─────────────────────────────────────────────────────
    'harris teeter':                      'harristeeter',

    # ── Stop & Shop ───────────────────────────────────────────────────────
    'stop and shop':                      'stopandshop',
    'stop & shop express':                'stopandshop',

    # ── Smart & Final ─────────────────────────────────────────────────────
    'smart & final extra!':               'smart_and_final',
    'smart & final express':              'smart_and_final',
    'smart and final':                    'smart_and_final',
    'smart_final':                        'smart_and_final',

    # ── Winn-Dixie ────────────────────────────────────────────────────────
    'winn dixie':                         'winndixie',
    'winn-dixie':                         'winndixie',

    # ── Acme Markets ──────────────────────────────────────────────────────
    'acme markets':                       'acmemarkets',
    'acme':                               'acmemarkets',

    # ── Giant Eagle ───────────────────────────────────────────────────────
    'giant eagle getgo':                  'gianteagle',

    # ── Phase-2 retailers (populated by import_osm_stores_phase2.py) ──────
    'the fresh market':                   'the_fresh_market',
    'tfm':                                'the_fresh_market',
    'natural grocers':                    'natural_grocers',
    'natural grocers by vitamin cottage': 'natural_grocers',
    'grocery outlet':                     'grocery_outlet',
    'grocery outlet bargain market':      'grocery_outlet',
    'fresh thyme':                        'fresh_thyme',
    'fresh thyme market':                 'fresh_thyme',
    'fresh thyme farmers market':         'fresh_thyme',
    'h mart':                             'hmart',
    'h-mart':                             'hmart',
    'save-a-lot':                         'save_a_lot',
    'save a lot':                         'save_a_lot',
    'pcc community markets':              'pcc',
    'pcc natural markets':                'pcc',
    'metropolitan market':                'metropolitan_market',
    'bristol farms':                      'bristol_farms',
    "gelson's":                           'gelsons',
    "gelson's markets":                   'gelsons',
    "stew leonard's":                     'stew_leonards',
    'stew leonards':                      'stew_leonards',
    'key food':                           'key_food',
    'key food stores':                    'key_food',
    'key food marketplace':               'key_food',
    'key food urban marketplace':         'key_food',
    'fairway market':                     'fairway',
    'fairway now':                        'fairway',
    'morton williams':                    'morton_williams',
    'morton williams supermarkets':       'morton_williams',
    'vallarta supermarkets':              'vallarta',
    'cardenas markets':                   'cardenas',
    'cárdenas markets':                   'cardenas',
    'northgate market':                   'northgate',
    'northgate gonzález market':          'northgate',
    'superior grocers':                   'superior_grocers',
    'western beef':                       'western_beef',
    'bravo supermarkets':                 'bravo',
    "rouse's market":                     'rouses',
    "rouse's":                            'rouses',
    'rouses market':                      'rouses',
    'save mart':                          'save_mart',
    'save mart supermarkets':             'save_mart',
    'central market':                     'centralmarket',
    "bj's wholesale club":                'bjs',
    "bj's":                               'bjs',
    'el super':                           'el_super',

    # ── Phase-3 retailers (populated by import_osm_stores_phase3.py) ──────
    'restaurant depot':                   'restaurant_depot',
    'family dollar':                      'family_dollar',
    'dollar tree':                        'dollar_tree',
    'ulta beauty':                        'ulta_beauty',
    "lucky's market":                     'lucky_market',
    'luckys market':                      'lucky_market',
    "chef'store":                         'chefstore',
    'us foods chefstore':                 'chefstore',
    'us foods chef store':                'chefstore',
    "us foods chef'store":                'chefstore',
    'cash & carry':                       'chefstore',
    'weis markets':                       'weis_markets',
    '7-eleven':                           'seven_eleven',
    'seven eleven':                       'seven_eleven',
    'sally beauty':                       'sally_beauty',
    'sally beauty supply':                'sally_beauty',
    'best buy':                           'best_buy',
    'ideal food basket':                  'ideal_food_basket',
    'overland foods':                     'overland_foods',
    "lassen's natural foods & vitamins":  'lassens',
    "lassen's natural foods":             'lassens',
    "lassen's":                           'lassens',
    'lassens natural foods & vitamins':   'lassens',
    'foodtown':                           'foodtown',
    'shoppers':                           'shoppers',
    'shoppers food & pharmacy':           'shoppers',
    'ctown supermarkets':                 'ctown',
    'c-town supermarkets':                'ctown',
    'king kullen':                        'king_kullen',
    'cardenas':                           'cardenas',
    'northgate gonzalez market':          'northgate',
    'giant':                              'giantfood',
    # NOTE: gordon restaurant market is Gordon Food Service — NOT Restaurant Depot.
    # These are two entirely separate companies.
    'gordon restaurant market':           'gordon_food_service',
    'gordon food service store':          'gordon_food_service',
    'gordon food service':                'gordon_food_service',
    'jetro':                              'restaurant_depot',
    'jetro cash & carry':                 'restaurant_depot',

    # ── Phase-4 retailers (populated by import_osm_stores_phase4.py) ──────
    'lincoln market':                     'lincoln_market',
    'north shore farms':                  'north_shore_farms',
    'citarella':                          'citarella',
    'windsor farms':                      'windsor_farms',
    'shamrock foods':                     'shamrock_foods',
    'shamrock foodservice warehouse':     'shamrock_foods',

    # ── Phase-5 retailers (populated by import_osm_stores_phase5.py) ──────
    'the fresh grocer':                   'fresh_grocer',
    'fresh grocer':                       'fresh_grocer',
    'price rite':                         'price_rite',
    'price rite marketplace':             'price_rite',
    'pricerite':                          'price_rite',
    'village supermarket':                'village_supermarket',
    'village super market':               'village_supermarket',
    "uncle giuseppe's marketplace":       'uncle_giuseppes',
    "uncle giuseppe's":                   'uncle_giuseppes',
    'gristedes':                          'gristedes',
    "gristede's":                         'gristedes',
    "gristede's foods":                   'gristedes',
    'lowes foods':                        'lowes_foods',
    "lowe's foods":                       'lowes_foods',
    'ingles':                             'ingles',
    'ingles markets':                     'ingles',
    'ingles market':                      'ingles',
    "zabar's":                            'zabars',
    'zabars':                             'zabars',
    'brooklyn fare':                      'brooklyn_fare',
    'brooklyn fare market':               'brooklyn_fare',
    'eataly':                             'eataly',
    'pet supplies plus':                  'pet_supplies_plus',
    'wild fork':                          'wild_fork',
    'wild fork foods':                    'wild_fork',
    "mother's market":                    'mothers_market',
    "mother's market & kitchen":          'mothers_market',
    "ridley's":                           'ridleys',
    "ridley's family market":             'ridleys',
    "ridley's family markets":            'ridleys',
    'ridleys':                            'ridleys',
    'nam dae mun farmers market':         'nam_dae_mun',
    'nam dae mun':                        'nam_dae_mun',
    'jubilee marketplace':                'jubilee_marketplace',
    "america's food basket":              'americas_food_basket',
    'americas food basket':               'americas_food_basket',
    'marukai':                            'marukai',
    'marukai market':                     'marukai',
    'marukai wholesale mart':             'marukai',
    'tokyo central':                      'marukai',
    'seasons kosher supermarket':         'seasons_kosher',
    'seasons kosher':                     'seasons_kosher',
    'pomegranate supermarket':            'pomegranate_mkt',
    'pomegranate':                        'pomegranate_mkt',
    "moisha's kosher supermarket":        'moishas_kosher',
    'westside market':                    'westside_market',
    'trade fair supermarket':             'trade_fair',
    'compare foods of morrisania':        'compare_foods',
    'compare foods':                      'compare_foods',
    'met food on white plains road':      'met_food',
    'shop fair supermarket':              'shop_fair',
    'pioneer supermarket':                'pioneer_supermarket',
    'pioneer parkside ave':               'pioneer_parkside',
    "la capital supermarket":             'la_capital_supermarket',
    'maspeth marketplace':                'maspeth_marketplace',
    'astoria marketplace':                'astoria_marketplace',
    'brooklyn harvest':                   'brooklyn_harvest',
    "aron's kissena farms":               'arons_kissena',
    'golden mango':                       'golden_mango',
    'm mart international grocery market': 'm_mart_intl',
    "giunta's meat farms":                'giuntas_meat_farms',
    'larkfield iga':                      'larkfield_iga',
    "uncle giuseppe's marketplace":       'uncle_giuseppes',
    'woods supermarket':                  'woods_supermarket',
    'wayfield foods':                     'wayfield_foods',
    'azalea fresh market':                'azalea_fresh_market',
    'marczyk fine foods':                 'marczyk_fine_foods',
    'nam dae mun farmers market':         'nam_dae_mun',
    "morton williams supermarket":        'morton_williams',
    'tfm express':                        'the_fresh_market',
    'pavilions rapid':                    'albertsons',
}

print("Pass 6: alias map — fd.retailer variant → sl.retailer_key (batched) …")
total_p6 = 0

for variant, base_key in ALIAS_MAP_P6.items():
    variant_total = 0
    while True:
        cur.execute("""
            SELECT fd.id
            FROM flyer_deals fd
            JOIN store_locations sl
              ON sl.retailer_key = %s
             AND sl.zip_code     = fd.zip_code
            WHERE fd.retailer  = %s
              AND fd.store_id IS NULL
            LIMIT %s
        """, (base_key, variant, BATCH_SIZE))
        ids = [row[0] for row in cur.fetchall()]
        if not ids:
            break
        cur.execute("""
            UPDATE flyer_deals fd
            SET
                store_id         = sl.id,
                match_confidence = 'zip_alias_map',
                matched_by       = 'sql_backfill'
            FROM store_locations sl
            WHERE sl.retailer_key = %s
              AND sl.zip_code     = fd.zip_code
              AND fd.id           = ANY(%s)
        """, (base_key, ids))
        updated = cur.rowcount
        conn.commit()
        variant_total += updated
        total_p6    += updated
    if variant_total > 0:
        print(f"  [{variant}] → {variant_total:,} rows")

print(f"  Pass 6 done — {total_p6:,} rows updated\n")


# ── Pass 7: zip-3 prefix fallback using fd.retailer_key ───────────────────
# For deals where the exact zip isn't in store_locations, try the first 3
# digits of the zip.  Only fires when exactly 1 store exists for that
# retailer with that zip-3 prefix — safe, no ambiguity.
# NOTE: only fires when fd.retailer_key IS NOT NULL. Rows with null
# retailer_key are handled by Pass 8.
print("Pass 7: zip-3 prefix fallback (fd.retailer_key, single-match guarantee) …")

cur.execute("""
    UPDATE flyer_deals fd
    SET
        store_id         = sl.id,
        match_confidence = 'zip3_fallback',
        matched_by       = 'sql_backfill'
    FROM store_locations sl
    JOIN (
        SELECT retailer_key, LEFT(zip_code, 3) AS zip3
        FROM   store_locations
        GROUP  BY retailer_key, LEFT(zip_code, 3)
        HAVING COUNT(*) = 1
    ) singles
      ON  singles.retailer_key = sl.retailer_key
      AND singles.zip3         = LEFT(sl.zip_code, 3)
    WHERE fd.store_id    IS NULL
      AND fd.zip_code    IS NOT NULL
      AND fd.zip_code    != ''
      AND fd.retailer_key = sl.retailer_key
      AND LEFT(fd.zip_code, 3) = LEFT(sl.zip_code, 3)
""")
p7 = cur.rowcount
conn.commit()
print(f"  Pass 7 done — {p7:,} rows updated\n")


# ── Pass 8: alias map + zip-3 prefix fallback (for retailer_key IS NULL) ──
# Many unmatched rows have fd.retailer_key = NULL, so passes 1/3/4/7 never
# fire for them.  This pass:
#   1. Builds a temp alias table from ALIAS_MAP_P6 (fd.retailer → sl.retailer_key)
#      plus direct retailer→retailer_key mappings from store_locations itself.
#   2. Resolves the canonical retailer_key for each unmatched fd.retailer.
#   3. Applies the same zip-3 single-match guarantee as Pass 7.
# This catches chains like walgreens/cvs/family_dollar at zips not in
# store_locations but within the same 3-digit postal area as a known store.
print("Pass 8: alias map + zip-3 name fallback (retailer_key IS NULL rows) …")

cur.execute("""
    CREATE TEMP TABLE IF NOT EXISTS p8_alias (
        fd_retailer  TEXT PRIMARY KEY,
        sl_key       TEXT NOT NULL
    )
""")

# Load alias map
cur.executemany(
    "INSERT INTO p8_alias (fd_retailer, sl_key) VALUES (%s, %s) ON CONFLICT DO NOTHING",
    list(ALIAS_MAP_P6.items()),
)

# Also add direct retailer → retailer_key mappings from store_locations
# (covers any retailer whose display name exactly matches sl.retailer)
cur.execute("""
    INSERT INTO p8_alias (fd_retailer, sl_key)
    SELECT DISTINCT retailer, retailer_key
    FROM   store_locations
    ON CONFLICT DO NOTHING
""")
conn.commit()

cur.execute("""
    UPDATE flyer_deals fd
    SET
        store_id         = sl.id,
        match_confidence = 'zip3_name_fallback',
        matched_by       = 'sql_backfill'
    FROM p8_alias al
    JOIN store_locations sl
      ON sl.retailer_key = al.sl_key
    JOIN (
        SELECT retailer_key, LEFT(zip_code, 3) AS zip3
        FROM   store_locations
        GROUP  BY retailer_key, LEFT(zip_code, 3)
        HAVING COUNT(*) = 1
    ) singles
      ON  singles.retailer_key = sl.retailer_key
      AND singles.zip3         = LEFT(sl.zip_code, 3)
    WHERE fd.retailer          = al.fd_retailer
      AND fd.store_id         IS NULL
      AND fd.zip_code         IS NOT NULL
      AND fd.zip_code         != ''
      AND LEFT(fd.zip_code, 3) = LEFT(sl.zip_code, 3)
""")
p8 = cur.rowcount
conn.commit()
print(f"  Pass 8 done — {p8:,} rows updated\n")


# ── Pass 9: nearest store by zip centroid (PostGIS, ≤ 80 km cap) ──────────
# Handles the case where fd.zip_code is a CUSTOMER/DELIVERY zip, not the
# store's zip — so exact-zip and zip-3 passes never fire even though stores
# exist in store_locations.
#
# Algorithm:
#   1. Resolve fd.retailer → sl.retailer_key via p8_alias (built in Pass 8).
#   2. For each unmatched deal, find the single closest store for that
#      retailer_key within 80 km using the PostGIS geom on the zips table.
#   3. DISTINCT ON (fd.id) + ORDER BY distance guarantees one match per deal.
#
# Catches: bj's (252 stores, 1717 unmatched), gelson's (14/735),
#          the fresh market (84/294), western beef (7/321),
#          restaurant depot (22/2115), family dollar (1856/552),
#          walgreens (3534/332), dollar tree (2438/295), petco (1030/222) …
#
# NOTE: p8_alias temp table is reused from Pass 8 (same session).
print("Pass 9: nearest store by zip centroid (PostGIS ≤ 80 km) …")

cur.execute("""
    UPDATE flyer_deals fd
    SET
        store_id         = closest.store_id,
        match_confidence = 'nearest_store_80km',
        matched_by       = 'sql_backfill'
    FROM (
        SELECT DISTINCT ON (fd2.id)
            fd2.id  AS fd_id,
            sl.id   AS store_id
        FROM flyer_deals fd2
        JOIN p8_alias al
          ON al.fd_retailer = fd2.retailer
        JOIN store_locations sl
          ON sl.retailer_key = al.sl_key
        JOIN zips z_fd
          ON z_fd.zip = fd2.zip_code
        JOIN zips z_sl
          ON z_sl.zip = sl.zip_code
        WHERE fd2.store_id IS NULL
          AND fd2.zip_code IS NOT NULL
          AND fd2.zip_code != ''
          AND ST_DWithin(
                z_fd.geom::geography,
                z_sl.geom::geography,
                80000          -- 80 000 m = 80 km ≈ 50 miles
              )
        ORDER BY
            fd2.id,
            z_fd.geom::geography <-> z_sl.geom::geography
    ) closest
    WHERE fd.id = closest.fd_id
""")
p9 = cur.rowcount
conn.commit()
print(f"  Pass 9 done — {p9:,} rows updated\n")


# ── Pass 10: nearest store, 200 km cap (wholesale / sparse retailers) ──────
# Wholesale retailers (restaurant depot, gordon food service, chefstore) have
# sparse store footprints and customers who legitimately travel 100-200 km.
# Also catches overland_foods (1 store in Boise) and other sparse chains where
# the 80 km cap in Pass 9 was too tight.
#
# Scoped to a specific allow-list of retailer_keys to prevent over-reaching
# for dense chains (walgreens, family dollar, etc.) where 200 km would
# produce meaningless matches.
#
# NOTE: p8_alias temp table is reused from Pass 8 (same session).
SPARSE_WHOLESALE_KEYS = [
    'restaurant_depot',
    'gordon_food_service',
    'chefstore',
    'overland_foods',
    'fresh_grocer',
    'jubilee_marketplace',
    'nam_dae_mun',
    'woods_supermarket',
    'wayfield_foods',
    'heritage_market',
    'ridleys',
    'lowes_foods',
    'ingles',
    'marukai',
]

print("Pass 10: nearest store 200 km (wholesale/sparse retailers) …")
print(f"  Scoped to: {SPARSE_WHOLESALE_KEYS}")

cur.execute("""
    UPDATE flyer_deals fd
    SET
        store_id         = closest.store_id,
        match_confidence = 'nearest_store_200km',
        matched_by       = 'sql_backfill'
    FROM (
        SELECT DISTINCT ON (fd2.id)
            fd2.id  AS fd_id,
            sl.id   AS store_id
        FROM flyer_deals fd2
        JOIN p8_alias al
          ON al.fd_retailer = fd2.retailer
        JOIN store_locations sl
          ON sl.retailer_key = al.sl_key
         AND sl.retailer_key = ANY(%s)
        JOIN zips z_fd
          ON z_fd.zip = fd2.zip_code
        JOIN zips z_sl
          ON z_sl.zip = sl.zip_code
        WHERE fd2.store_id IS NULL
          AND fd2.zip_code IS NOT NULL
          AND fd2.zip_code != ''
          AND ST_DWithin(
                z_fd.geom::geography,
                z_sl.geom::geography,
                200000         -- 200 000 m = 200 km ≈ 124 miles
              )
        ORDER BY
            fd2.id,
            z_fd.geom::geography <-> z_sl.geom::geography
    ) closest
    WHERE fd.id = closest.fd_id
""", (SPARSE_WHOLESALE_KEYS,))
p10 = cur.rowcount
conn.commit()
print(f"  Pass 10 done — {p10:,} rows updated\n")


# ── Verification ───────────────────────────────────────────────────────────
cur.execute("""
    SELECT COUNT(*), COUNT(store_id),
           ROUND(COUNT(store_id)::numeric / COUNT(*) * 100, 2)
    FROM flyer_deals
""")
total, matched, pct = cur.fetchone()
unmatched = total - matched

print("── Verification ─────────────────────────────────────────────────────────────")
print(f"  Matched:   {matched:>10,} / {total:,}  ({pct}%)")
print(f"  Unmatched: {unmatched:>10,}")
print()
print("  Pass breakdown:")
print(f"    Pass 1  key+zip exact:           {p1:>8,}")
print(f"    Pass 2  name+zip exact:          {p2:>8,}")
print(f"    Pass 3  key→name+zip:            {p3:>8,}")
print(f"    Pass 4  suffix/key:              {total_p4:>8,}")
print(f"    Pass 5  suffix/name:             {total_p5:>8,}")
print(f"    Pass 6  alias map:               {total_p6:>8,}")
print(f"    Pass 7  zip-3 fallback:          {p7:>8,}")
print(f"    Pass 8  zip-3 name fallback:     {p8:>8,}")
print(f"    Pass 9  nearest store  80km:     {p9:>8,}")
print(f"    Pass 10 nearest store 200km:     {p10:>8,}")
print(f"    ─────────────────────────────────────")
this_run = p1 + p2 + p3 + total_p4 + total_p5 + total_p6 + p7 + p8 + p9 + p10
print(f"    This run total:                 {this_run:>8,}")

cur.close()
conn.close()