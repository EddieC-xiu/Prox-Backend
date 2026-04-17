# services/store_matching.py
import math, time, logging
from dataclasses import dataclass, field
from config.supabase import get_supabase_client
from services.address_normalizer import normalize_retailer_key, make_retailer_key
from services.geocoding_service import geocode_address, geocode_retailer

logger   = logging.getLogger(__name__)
supabase = get_supabase_client()

_match_cache:        dict[str, "MatchResult"] = {}
_zip_centroid_cache: dict[str, dict]          = {}

RETAILER_ALIASES: dict[str, str] = {
    # ── Kroger family ─────────────────────────────────────────────────────────
    "kroger": "kroger", "Kroger": "kroger", "KROGER": "kroger",
    "Kroger Delivery Now": "kroger", "kroger delivery now": "kroger",
    "QFC": "kroger", "qfc": "kroger",
    "Mariano's": "kroger", "marianos": "kroger", "Mariano's Delivery Now": "kroger",
    "FoodsCo": "kroger", "foodsco": "kroger", "FoodsCo Delivery Now": "kroger",
    "FoodMaxx": "kroger", "foodmaxx": "kroger",
    "Pay-Less Super Markets": "kroger", "pay-less super markets": "kroger",
    "Metro Market": "kroger", "metro market": "kroger",
    "Ruler Foods": "kroger", "ruler foods": "kroger",
    "City Market": "kroger", "city market": "kroger",
    "Dillons": "kroger", "dillons": "kroger",
    "Gerbes": "kroger", "gerbes": "kroger",
    # ── Ralphs ────────────────────────────────────────────────────────────────
    "Ralphs": "ralphs", "ralphs": "ralphs", "Ralph's": "ralphs",
    "Ralphs Delivery Now": "ralphs",
    # ── King Soopers ──────────────────────────────────────────────────────────
    "King Soopers": "kingsoopers", "king soopers": "kingsoopers",
    "King Soopers Delivery Now": "kingsoopers",
    # ── Fred Meyer ────────────────────────────────────────────────────────────
    "Fred Meyer": "fredmeyer", "fred meyer": "fredmeyer",
    # ── Harris Teeter ─────────────────────────────────────────────────────────
    "Harris Teeter": "harristeeter", "harris teeter": "harristeeter",
    "harristeeter": "harristeeter", "Harris Teeter Delivery Now": "harristeeter",
    # ── Smith's ───────────────────────────────────────────────────────────────
    "Smith's": "smiths", "smiths": "smiths", "Smith's Food and Drug": "smiths",
    # ── Pick 'n Save ──────────────────────────────────────────────────────────
    "Pick 'n Save": "picknsave", "pick n save": "picknsave", "picknsave": "picknsave",
    # ── Food4Less ─────────────────────────────────────────────────────────────
    "Food4Less": "food4less", "food4less": "food4less",
    "Food 4 Less": "food4less", "food 4 less": "food4less",
    "Food4Less Delivery Now": "food4less",
    # ── Jewel-Osco ────────────────────────────────────────────────────────────
    "Jewel-Osco": "jewelosco", "Jewel Osco": "jewelosco", "jewelosco": "jewelosco",
    "jewel-osco": "jewelosco", "Jewel": "jewelosco",
    # ── Albertsons ────────────────────────────────────────────────────────────
    "albertsons": "albertsons", "Albertsons": "albertsons", "ALBERTSONS": "albertsons",
    "Albertsons Market": "albertsons", "Andronico's Community Markets": "albertsons",
    "Lucky Supermarkets": "albertsons", "Amigos": "albertsons", "amigos": "albertsons",
    "Pavilions": "albertsons", "pavilions": "albertsons",
    # ── Safeway ───────────────────────────────────────────────────────────────
    "Safeway": "safeway", "safeway": "safeway", "SAFEWAY": "safeway",
    "Safeway Rapid": "safeway",
    # ── Vons ──────────────────────────────────────────────────────────────────
    "Vons": "vons", "vons": "vons", "VONS": "vons",
    # ── Acme Markets ──────────────────────────────────────────────────────────
    "Acme Markets": "acmemarkets", "ACME Markets": "acmemarkets",
    "acmemarkets": "acmemarkets", "acme markets": "acmemarkets", "Acme": "acmemarkets",
    # ── Shaw's ────────────────────────────────────────────────────────────────
    "Shaw's": "shaws", "shaws": "shaws", "Shaw's Supermarkets": "shaws",
    # ── Star Market ───────────────────────────────────────────────────────────
    "Star Market": "starmarket", "starmarket": "starmarket",
    # ── Tom Thumb ─────────────────────────────────────────────────────────────
    "Tom Thumb": "tomthumb", "tomthumb": "tomthumb",
    # ── Randalls ──────────────────────────────────────────────────────────────
    "Randalls": "randalls", "randalls": "randalls",
    # ── Haggen ────────────────────────────────────────────────────────────────
    "Haggen": "haggen", "haggen": "haggen", "Haggen Food & Pharmacy": "haggen",
    # ── Balducci's ────────────────────────────────────────────────────────────
    "Balducci's": "balduccis", "balduccis": "balduccis",
    # ── Kings Food Markets ────────────────────────────────────────────────────
    "Kings Food Markets": "kingsfoodmarkets", "King's Food Markets": "kingsfoodmarkets",
    "kingsfoodmarkets": "kingsfoodmarkets",
    # ── Carrs ─────────────────────────────────────────────────────────────────
    "Carrs Quality Centers": "carrsqc", "Carr's": "carrsqc", "Carrs": "carrsqc",
    "carrsqc": "carrsqc", "Carrs-Safeway": "carrsqc",
    # ── United Supermarkets ───────────────────────────────────────────────────
    "United Supermarkets": "shopunitedsupermarkets",
    "shopunitedsupermarkets": "shopunitedsupermarkets",
    # ── Market Street ─────────────────────────────────────────────────────────
    "Market Street": "shopmarketstreet", "shopmarketstreet": "shopmarketstreet",
    # ── Publix ────────────────────────────────────────────────────────────────
    "publix": "publix", "Publix": "publix", "PUBLIX": "publix",
    "Publix Super Markets": "publix",
    # ── Smart & Final ─────────────────────────────────────────────────────────
    "Smart & Final": "smart_and_final", "smart & final": "smart_and_final",
    "smart_final": "smart_and_final", "smart_and_final": "smart_and_final",
    "Smart & Final Express": "smart_and_final", "Smart & Final Extra!": "smart_and_final",
    "Smart and Final": "smart_and_final", "SMART & FINAL": "smart_and_final",
    # ── Walmart ───────────────────────────────────────────────────────────────
    "walmart": "walmart", "Walmart": "walmart", "WALMART": "walmart",
    "Wal-Mart": "walmart", "wal-mart": "walmart",
    "Walmart Supercenter": "walmart", "walmart supercenter": "walmart",
    "Walmart Neighborhood Market": "walmart", "walmart neighborhood market": "walmart",
    "Walmart Express": "walmart", "Walmart Pickup": "walmart",
    # ── Target ────────────────────────────────────────────────────────────────
    "target": "target", "Target": "target", "TARGET": "target",
    "Super Target": "target", "super target": "target",
    "Target Express": "target", "target express": "target",
    "Target Small Format": "target",
    # ── ALDI ──────────────────────────────────────────────────────────────────
    "aldi": "aldi", "ALDI": "aldi", "Aldi": "aldi",
    "ALDI Foods": "aldi", "aldi foods": "aldi",
    # ── Costco ────────────────────────────────────────────────────────────────
    "costco": "costco", "Costco": "costco", "COSTCO": "costco",
    "Costco Wholesale": "costco", "costco wholesale": "costco",
    "Costco Business Center": "costco", "costco business center": "costco",
    # ── Sam's Club ────────────────────────────────────────────────────────────
    "Sam's Club": "samsclub", "sam's club": "samsclub",
    "Sams Club": "samsclub", "sams club": "samsclub", "samsclub": "samsclub",
    # ── BJ's Wholesale ────────────────────────────────────────────────────────
    "BJ's Wholesale Club": "bjs", "bj's wholesale club": "bjs",
    "BJs Wholesale Club": "bjs", "BJ's": "bjs", "bjs": "bjs",
    # ── Wegmans ───────────────────────────────────────────────────────────────
    "Wegmans": "wegmans", "wegmans": "wegmans", "WEGMANS": "wegmans",
    "Wegman's": "wegmans", "wegman's": "wegmans", "Wegmans Food Markets": "wegmans",
    # ── ShopRite ──────────────────────────────────────────────────────────────
    "ShopRite": "shoprite", "shoprite": "shoprite", "Shop Rite": "shoprite",
    "shop rite": "shoprite", "ShopRite Supermarkets": "shoprite", "SHOPRITE": "shoprite",
    # ── Sprouts ───────────────────────────────────────────────────────────────
    "Sprouts Farmers Market": "sprouts", "Sprouts Farmer's Market": "sprouts",
    "Sprouts": "sprouts", "sprouts": "sprouts",
    "sprouts farmers market": "sprouts", "SPROUTS": "sprouts",
    # ── Stop & Shop ───────────────────────────────────────────────────────────
    "Stop & Shop": "stopandshop", "stop & shop": "stopandshop",
    "Stop and Shop": "stopandshop", "stop and shop": "stopandshop",
    "stopandshop": "stopandshop", "Stop & Shop Express": "stopandshop",
    # ── Food Lion ─────────────────────────────────────────────────────────────
    "Food Lion": "foodlion", "food lion": "foodlion", "foodlion": "foodlion",
    "FOOD LION": "foodlion", "Food Lion Now": "foodlion",
    # ── Food Bazaar ───────────────────────────────────────────────────────────
    "Food Bazaar": "foodbazaar", "food bazaar": "foodbazaar",
    "foodbazaar": "foodbazaar", "Food Bazaar Supermarkets": "foodbazaar",
    # ── Stater Bros ───────────────────────────────────────────────────────────
    "Stater Bros.": "staterbros", "Stater Bros": "staterbros",
    "stater bros": "staterbros", "staterbros": "staterbros",
    "Stater Brothers": "staterbros",
    # ── Winn-Dixie ────────────────────────────────────────────────────────────
    "Winn-Dixie": "winndixie", "winn-dixie": "winndixie",
    "Winn Dixie": "winndixie", "winndixie": "winndixie",
    # ── Giant Food ────────────────────────────────────────────────────────────
    "Giant Food": "giantfood", "giant food": "giantfood", "Giant": "giantfood",
    "giantfood": "giantfood", "Martin's Food Markets": "giantfood",
    "Giant Food Convenience": "giantfood", "giant food convenience": "giantfood",
    # ── Giant Eagle ───────────────────────────────────────────────────────────
    "Giant Eagle": "gianteagle", "giant eagle": "gianteagle", "gianteagle": "gianteagle",
    # ── Whole Foods ───────────────────────────────────────────────────────────
    "Whole Foods Market": "wholefoods", "Whole Foods": "wholefoods",
    "whole foods": "wholefoods", "wholefoods": "wholefoods",
    # ── Trader Joe's ──────────────────────────────────────────────────────────
    "Trader Joe's": "traderjoes", "Trader Joes": "traderjoes",
    "trader joe's": "traderjoes", "traderjoes": "traderjoes",
    # ── H-E-B ─────────────────────────────────────────────────────────────────
    "H-E-B": "heb", "H-E-B Plus!": "heb", "H-E-B Plus": "heb",
    "heb": "heb", "HEB": "heb",
    "Central Market": "centralmarket", "central market": "centralmarket",
    # ── Meijer ────────────────────────────────────────────────────────────────
    "Meijer": "meijer", "meijer": "meijer",
    # ── Gelson's ──────────────────────────────────────────────────────────────
    "Gelson's": "gelsons", "gelson's": "gelsons", "Gelsons": "gelsons",
    # ── Rouses ────────────────────────────────────────────────────────────────
    "Rouses Markets": "rouses", "rouses markets": "rouses",
    "Rouses Market": "rouses", "rouses market": "rouses", "Rouses": "rouses",
    # ── Save Mart ─────────────────────────────────────────────────────────────
    "Save Mart": "savemart", "save mart": "savemart", "Save Mart Express": "savemart",
    # ── Key Food ──────────────────────────────────────────────────────────────
    "Key Food": "keyfood", "key food": "keyfood",
    "Key Food Marketplace": "keyfood", "key food marketplace": "keyfood",
    # ── Bristol Farms ─────────────────────────────────────────────────────────
    "Bristol Farms": "bristolfarms", "bristol farms": "bristolfarms",
    # ── El Super ──────────────────────────────────────────────────────────────
    "El Super": "elsuper", "el super": "elsuper", "el-super": "elsuper",
    # ── H Mart ────────────────────────────────────────────────────────────────
    "HMart": "hmart", "hmart": "hmart", "H Mart": "hmart", "H-Mart": "hmart",
    # ── Northgate Market ──────────────────────────────────────────────────────
    "Northgate Market": "northgate", "northgate market": "northgate",
    "Northgate": "northgate",
    # ── Vallarta ──────────────────────────────────────────────────────────────
    "Vallarta Supermarkets": "vallarta", "vallarta supermarkets": "vallarta",
    "Vallarta": "vallarta",
    # ── Erewhon ───────────────────────────────────────────────────────────────
    "erewhon": "erewhon", "Erewhon": "erewhon",
    # ── Bi-Rite ───────────────────────────────────────────────────────────────
    "Bi-Rite Market": "birite", "bi-rite market": "birite", "Bi-Rite": "birite",
    # ── Rainbow Grocery ───────────────────────────────────────────────────────
    "Rainbow Grocery": "rainbowgrocery", "rainbow grocery": "rainbowgrocery",
    # ── Ideal Food Basket ─────────────────────────────────────────────────────
    "Ideal Food Basket": "idealfoodbasket", "ideal food basket": "idealfoodbasket",
    # ── Save A Lot ────────────────────────────────────────────────────────────
    "Save A Lot": "savealot", "save a lot": "savealot", "Save-A-Lot": "savealot",
    # ── Gus's Community Market ────────────────────────────────────────────────
    "Gus's Community Market": "gusmarket", "gus's community market": "gusmarket",
    # ── Mollie Stone's ────────────────────────────────────────────────────────
    "Mollie Stone's Markets": "molliestones", "Mollie Stone's": "molliestones",
    "mollie stone's markets": "molliestones",
    # ── Hubbens ───────────────────────────────────────────────────────────────
    "Hubbens Supermarket": "hubbens", "hubbens supermarket": "hubbens",
    # ── Hi Nabor ──────────────────────────────────────────────────────────────
    "Hi Nabor Supermarket": "hinabor", "hi nabor supermarket": "hinabor",
    # ── Matherne's ────────────────────────────────────────────────────────────
    "Matherne's Market": "mathernes", "matherne's market": "mathernes",
    # ── Walgreens ─────────────────────────────────────────────────────────────
    "Walgreens": "walgreens", "walgreens": "walgreens",
    "WALGREENS": "walgreens", "Walgreens Pharmacy": "walgreens",
    # ── CVS ───────────────────────────────────────────────────────────────────
    "CVS": "cvs", "cvs": "cvs", "CVS Pharmacy": "cvs",
    "CVS®": "cvs", "cvs®": "cvs", "CVS Health": "cvs",
    # ── Family Dollar ─────────────────────────────────────────────────────────
    "Family Dollar": "familydollar", "family dollar": "familydollar",
    # ── Restaurant Depot ──────────────────────────────────────────────────────
    "Restaurant Depot": "restaurantdepot", "restaurant depot": "restaurantdepot",
    "restaurantdepot": "restaurantdepot",
    # ── Super 1 Foods ─────────────────────────────────────────────────────────
    "Super 1 Foods": "super1foods", "super 1 foods": "super1foods",
    # ── Fairway ───────────────────────────────────────────────────────────────
    "Fairway": "fairway", "fairway": "fairway",
    "Fairway Market": "fairway", "Fairway Now": "fairway",
    # ── Superior Grocers ──────────────────────────────────────────────────────
    "Superior Grocers": "superiorgrocers", "superior grocers": "superiorgrocers",
    # ── Dollar stores ─────────────────────────────────────────────────────────
    "Dollar General": "dollargeneral", "dollar general": "dollargeneral",
    "Dollar Tree": "dollartree", "dollar tree": "dollartree",
}

_NO_MATCH_RETAILERS: set[str] = {
    "picknsave", "centralmarket",
    "stew_leonards", "the_fresh_market", "morton_williams",
    "natural_grocers", "metropolitan_market", "pcc", "grocery_outlet",
    "fresh_thyme", "cardenas", "western_beef", "bravo", "gordon_food_service",
    "dollartree", "dollargeneral",
    "petsmart", "petco", "ulta_beauty", "sephora", "sally_beauty", "7_eleven",
}

_LOADED_RETAILERS: set[str] = {
    # ── Albertsons/Kroger family ──────────────────────────────────────────────
    "kroger", "publix", "safeway", "albertsons",
    "jewelosco", "shaws", "starmarket", "tomthumb",
    "randalls", "haggen", "balduccis", "kingsfoodmarkets",
    "carrsqc", "shopunitedsupermarkets", "shopmarketstreet", "smart_and_final",
    # ── OSM imported ──────────────────────────────────────────────────────────
    "walmart", "target", "aldi", "costco", "samsclub", "bjs",
    "wegmans", "shoprite", "sprouts", "stopandshop",
    "foodlion", "vons", "food4less", "staterbros", "foodbazaar",
    "wholefoods", "traderjoes", "heb", "meijer",
    "gianteagle", "giantfood", "winndixie",
    "harristeeter", "fredmeyer", "kingsoopers", "smiths", "ralphs",
    # ── Regional grocers ──────────────────────────────────────────────────────
    "gelsons", "keyfood", "savemart", "rouses",
    "bristolfarms", "elsuper",
    "super1foods", "fairway", "superiorgrocers",
    "hmart", "northgate", "vallarta", "erewhon",
    "birite", "rainbowgrocery", "idealfoodbasket", "savealot",
    "gusmarket", "molliestones", "hubbens", "hinabor", "mathernes",
    # ── Pharmacy / dollar / other ─────────────────────────────────────────────
    "walgreens", "cvs", "familydollar", "restaurantdepot",
}

_DELIVERY_SUFFIXES = (
    " Delivery Now", " Express", " Rapid", " Now",
    ": Fast Delivery", " Fast Delivery",
)

@dataclass
class MatchResult:
    store_id:              str | None
    match_confidence:      str
    candidate_store_count: int
    matched_by:            str
    candidate_store_ids:   list[str] = field(default_factory=list)


def _resolve_retailer_key(retailer_raw: str) -> str | None:
    if not retailer_raw:
        return None
    if retailer_raw in RETAILER_ALIASES:
        return RETAILER_ALIASES[retailer_raw]
    lower = retailer_raw.strip().lower()
    for k, v in RETAILER_ALIASES.items():
        if k.lower() == lower:
            return v
    stripped = retailer_raw
    for suffix in _DELIVERY_SUFFIXES:
        if retailer_raw.endswith(suffix):
            stripped = retailer_raw[: -len(suffix)].strip()
            break
    if stripped != retailer_raw:
        if stripped in RETAILER_ALIASES:
            return RETAILER_ALIASES[stripped]
        stripped_lower = stripped.lower()
        for k, v in RETAILER_ALIASES.items():
            if k.lower() == stripped_lower:
                return v
    return normalize_retailer_key(retailer_raw) or make_retailer_key(retailer_raw)


def find_store_for_deal(
    retailer_raw: str, zip_code: str,
    city: str | None = None, state: str | None = None,
    address: str | None = None,
    deal_lat: float | None = None, deal_lng: float | None = None,
) -> MatchResult:
    retailer_key = _resolve_retailer_key(retailer_raw)
    if not retailer_key:
        return MatchResult(None, "none", 0, "none")
    cache_key = f"{retailer_key}|{zip_code}"
    if cache_key in _match_cache:
        return _match_cache[cache_key]
    if retailer_key in _NO_MATCH_RETAILERS:
        result = MatchResult(None, "none", 0, "not_loaded")
        _match_cache[cache_key] = result
        return result
    if retailer_key not in _LOADED_RETAILERS:
        result = MatchResult(None, "none", 0, "not_loaded")
        _match_cache[cache_key] = result
        return result
    result = (
        _match_by_zip(retailer_key, zip_code, deal_lat, deal_lng)
        or _match_by_city_state(retailer_key, city, state)
        or _create_store(retailer_key, retailer_raw, zip_code, address)
    )
    _match_cache[cache_key] = result
    logger.info(f"[MATCH] {retailer_key}/{zip_code} → {result.store_id} confidence={result.match_confidence} by={result.matched_by}")
    return result


def _match_by_zip(retailer_key, zip_code, deal_lat, deal_lng):
    if not zip_code:
        return None
    res = supabase.table("store_locations").select("id, latitude, longitude").eq("retailer_key", retailer_key).eq("zip_code", zip_code).execute()
    stores = res.data or []
    count  = len(stores)
    if count == 0:
        return None
    if count == 1:
        return MatchResult(stores[0]["id"], "zip_single", 1, "zip_code", [])
    all_ids = [s["id"] for s in stores]
    ref_lat, ref_lng = deal_lat, deal_lng
    if ref_lat is None or ref_lng is None:
        centroid = _get_zip_centroid(zip_code)
        if centroid:
            ref_lat, ref_lng = centroid["latitude"], centroid["longitude"]
    best_id = stores[0]["id"]
    if ref_lat is not None and ref_lng is not None:
        with_coords = [s for s in stores if s.get("latitude") and s.get("longitude")]
        if with_coords:
            best_id = min(with_coords, key=lambda s: _haversine(ref_lat, ref_lng, s["latitude"], s["longitude"]))["id"]
    return MatchResult(best_id, "zip_multi", count, "zip_code", all_ids)


def _match_by_city_state(retailer_key, city, state):
    return None


def _create_store(retailer_key, retailer_raw, zip_code, address):
    time.sleep(1.1)
    coords = geocode_retailer(retailer_key, zip_code)
    if not coords and address:
        coords = geocode_address(address, zip_code)
    row = {
        "retailer_key": retailer_key, "retailer": retailer_raw.strip().lower(),
        "zip_code": zip_code, "address": address, "full_address": address,
        "latitude": coords["lat"] if coords else None,
        "longitude": coords["lng"] if coords else None,
        "geocode_source": "nominatim" if coords else "pending",
        "geocode_confidence": "zip" if coords else None,
    }
    try:
        result = supabase.table("store_locations").upsert(row, on_conflict="retailer_key,zip_code").execute()
        if result.data:
            store_id = result.data[0]["id"]
            return MatchResult(store_id, "created", 0, "created", [])
    except Exception as e:
        logger.error(f"[STORE CREATE FAILED] {retailer_key}/{zip_code}: {e}")
    return MatchResult(None, "none", 0, "none")


def _get_zip_centroid(zip_code):
    if zip_code in _zip_centroid_cache:
        return _zip_centroid_cache[zip_code]
    res = supabase.table("zip_centroids").select("latitude, longitude").eq("zip_code", zip_code).single().execute()
    if res.data:
        _zip_centroid_cache[zip_code] = res.data
        return res.data
    return None


def _haversine(lat1, lon1, lat2, lon2):
    R = 3958.8
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = math.radians(lat2-lat1), math.radians(lon2-lon1)
    a = math.sin(dp/2)**2 + math.cos(p1)*math.cos(p2)*math.sin(dl/2)**2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))


def get_match_cache_stats():
    total = len(_match_cache)
    matched = sum(1 for v in _match_cache.values() if v.store_id is not None)
    by_conf: dict[str, int] = {}
    for v in _match_cache.values():
        by_conf[v.match_confidence] = by_conf.get(v.match_confidence, 0) + 1
    return {"cached_pairs": total, "matched": matched, "by_confidence": by_conf}