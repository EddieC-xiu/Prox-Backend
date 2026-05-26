# services/cross_retailer_service.py
#
# Cross-retailer price comparison for a given product.
# Uses flyer_deals as source of truth.
#
# Key behaviors:
# - Default = exact size mode (most retailers, like-for-like)
# - PPU mode = explicit only (size='ppu') or fallback when no exact size exists
# - No-size rows excluded from exact comparisons when sized rows exist
# - Fuzzy matching uses name similarity as primary signal, not retailer count
# - Long canonical names (>80 chars) filtered as scraper artifacts

import math
import re
import statistics
from collections import defaultdict
from config.supabase import get_supabase_client
from scoring.product_normalizer import build_canonical_name

sb = get_supabase_client()

# ── Kiran's canonical name lookup ────────────────────────────────────────────
_KIRAN_LOOKUP: dict[str, str] | None = None

def _load_kiran_lookup() -> dict[str, str]:
    """Load canonical_name_test (Kiran's AI-validated canonical names) into memory."""
    lookup: dict[str, str] = {}
    offset = 0
    while True:
        try:
            batch = (
                sb.table("canonical_name_test")
                .select("normalized_signature, canonical_name")
                .eq("confidence", "high")
                .range(offset, offset + 999)
                .execute()
                .data or []
            )
        except Exception:
            break
        for row in batch:
            if row.get("normalized_signature") and row.get("canonical_name"):
                lookup[row["normalized_signature"]] = row["canonical_name"]
        if len(batch) < 1000:
            break
        offset += 1000
    return lookup

def _get_kiran_lookup() -> dict[str, str]:
    global _KIRAN_LOOKUP
    if _KIRAN_LOOKUP is None:
        _KIRAN_LOOKUP = _load_kiran_lookup()
    return _KIRAN_LOOKUP

def _kiran_canonical(product_name: str, pre_normalized: str | None = None) -> str | None:
    """Return Kiran's validated canonical name for a product, or None if not found.

    Tries two keys in order:
    1. The raw product_name normalized to lowercase alphanum+spaces (works when
       the name is already short/clean, e.g. 'Organic Lemons')
    2. pre_normalized — our own canonical output (brand-stripped, stopwords removed)
       which is closer in format to Kiran's signatures for longer product names
    """
    lookup = _get_kiran_lookup()

    def _sig(s: str) -> str:
        s = re.sub(r'[^a-z0-9\s]', ' ', s.lower())
        return re.sub(r'\s+', ' ', s).strip()

    result = lookup.get(_sig(product_name))
    if result:
        return result
    if pre_normalized:
        result = lookup.get(_sig(pre_normalized))
        if result:
            return result
    return None

RETAILER_ALIASES = {
    "walmart":                    "Walmart",              "Walmart":                    "Walmart",
    "target":                     "Target",               "Target":                     "Target",
    "aldi":                       "ALDI",                 "ALDI":                       "ALDI",
    "aldi express":               "ALDI Express",         "ALDI Express":               "ALDI Express",
    "kroger":                     "Kroger",               "Kroger":                     "Kroger",
    "publix":                     "Publix",               "Publix":                     "Publix",
    "ralphs":                     "Ralphs",               "Ralphs":                     "Ralphs",
    "ralphs delivery now":        "Ralphs",               "Ralphs Delivery Now":        "Ralphs",
    "kroger delivery now":        "Kroger",               "Kroger Delivery Now":        "Kroger",
    "food4less delivery now":     "Food4Less",            "Food4Less Delivery Now":     "Food4Less",
    "foodsco delivery now":       "FoodsCo",              "FoodsCo Delivery Now":       "FoodsCo",
    "albertsons rapid":           "Albertsons",           "Albertsons Rapid":           "Albertsons",
    "safeway rapid":              "Safeway",              "Safeway Rapid":              "Safeway",
    "vons rapid":                 "Vons",                 "Vons Rapid":                 "Vons",
    "food lion now":              "Food Lion",            "Food Lion Now":              "Food Lion",
    "sprouts express":            "Sprouts",              "Sprouts Express":            "Sprouts",
    "sprouts-express":            "Sprouts",
    "save mart express":          "Save Mart",            "Save Mart Express":          "Save Mart",
    "stater bros. now":           "Stater Bros.",         "Stater Bros. Now":           "Stater Bros.",
    "meijer express delivery":    "Meijer",               "Meijer Express Delivery":    "Meijer",
    "target: fast delivery":      "Target",               "Target: Fast Delivery":      "Target",
    "target-fast-delivery":       "Target",
    "costco":                     "Costco",               "Costco":                     "Costco",
    "costco business center":     "Costco Business Center", "Costco Business Center":   "Costco Business Center",
    "smart_final":                "Smart & Final",        "Smart & Final":              "Smart & Final",
    "shoprite":                   "ShopRite",             "ShopRite":                   "ShopRite",
    "wegmans":                    "Wegmans",              "Wegmans":                    "Wegmans",
    "sprouts farmers market":     "Sprouts",              "Sprouts Farmers Market":     "Sprouts",
    "sprouts":                    "Sprouts",              "Sprouts":                    "Sprouts",
    "vons":                       "Vons",                 "Vons":                       "Vons",
    "albertsons":                 "Albertsons",           "Albertsons":                 "Albertsons",
    "safeway":                    "Safeway",              "Safeway":                    "Safeway",
    "food bazaar":                "Food Bazaar",          "Food Bazaar":                "Food Bazaar",
    "stop & shop":                "Stop & Shop",          "Stop & Shop":                "Stop & Shop",
    "stop & shop express":        "Stop & Shop",          "Stop & Shop Express":        "Stop & Shop",
    "bristol farms":              "Bristol Farms",        "Bristol Farms":              "Bristol Farms",
    "gelson's":                   "Gelson's",             "Gelson's":                   "Gelson's",
    "gelsons":                    "Gelson's",
    "walgreens":                  "Walgreens",            "Walgreens":                  "Walgreens",
    "cvs":                        "CVS",                  "CVS":                        "CVS",
    "cvs®":                       "CVS",                  "CVS®":                       "CVS",
    "food4less":                  "Food4Less",            "Food4Less":                  "Food4Less",
    "foodsco":                    "FoodsCo",              "FoodsCo":                    "FoodsCo",
    "foodmaxx":                   "FoodMaxx",             "FoodMaxx":                   "FoodMaxx",
    "lazy acres":                 "Lazy Acres",           "Lazy Acres":                 "Lazy Acres",
    "bj's wholesale club":        "BJ's Wholesale Club",  "BJ's Wholesale Club":        "BJ's Wholesale Club",
    "dollar tree":                "Dollar Tree",          "Dollar Tree":                "Dollar Tree",
    "eataly":                     "Eataly",               "Eataly":                     "Eataly",
    "el super":                   "El Super",             "El Super":                   "El Super",
    "fairway now":                "Fairway Now",          "Fairway Now":                "Fairway Now",
    "family dollar":              "Family Dollar",        "Family Dollar":              "Family Dollar",
    "hmart":                      "H Mart",               "HMart":                      "H Mart",
    "h mart":                     "H Mart",               "H Mart":                     "H Mart",
    "ideal food basket":          "Ideal Food Basket",    "Ideal Food Basket":          "Ideal Food Basket",
    "99 ranch market":            "99 Ranch Market",      "99 Ranch Market":            "99 Ranch Market",
    "western beef":               "Western Beef",         "Western Beef":               "Western Beef",
    "key food":                   "Key Food",             "Key Food":                   "Key Food",
    "key food marketplace":       "Key Food Marketplace", "Key Food Marketplace":       "Key Food Marketplace",
    "lincoln market":             "Lincoln Market",       "Lincoln Market":             "Lincoln Market",
    "northgate market":           "Northgate Market",     "Northgate Market":           "Northgate Market",
    "petco":                      "Petco",                "Petco":                      "Petco",
    "petsmart":                   "PetSmart",             "PetSmart":                   "PetSmart",
    "restaurant depot":           "Restaurant Depot",     "Restaurant Depot":           "Restaurant Depot",
    "sam's club":                 "Sam's Club",           "Sam's Club":                 "Sam's Club",
    "superior grocers":           "Superior Grocers",     "Superior Grocers":           "Superior Grocers",
    "the fresh grocer":           "The Fresh Grocer",     "The Fresh Grocer":           "The Fresh Grocer",
    "pavilions":                  "Pavilions",            "Pavilions":                  "Pavilions",
    "lucky supermarkets":         "Lucky Supermarkets",   "Lucky Supermarkets":         "Lucky Supermarkets",
}

_UNIT_TO_OZ = {
    "oz": 1.0, "fl oz": 1.0, "fl-oz": 1.0, "floz": 1.0,
    "lb": 16.0, "lbs": 16.0, "pound": 16.0, "pounds": 16.0,
    "g": 0.035274, "gram": 0.035274, "grams": 0.035274,
    "ml": 0.033814, "liter": 33.814, "l": 33.814,
}

_MAX_NAME_LENGTH = 80


def normalize_retailer(raw: str) -> str:
    return RETAILER_ALIASES.get(raw, raw)


def _word_sort_key(name: str) -> str:
    words = name.split()
    if len(words) <= 4:
        return " ".join(sorted(words))
    return name


def _name_similarity(query: str, candidate: str) -> float:
    query     = query.lower().strip()
    candidate = candidate.lower().strip()
    if query == candidate:
        return 1.0
    if candidate.startswith(query + " ") or candidate.endswith(" " + query):
        return 0.9
    query_words    = set(query.split())
    candidate_words = set(candidate.split())
    overlap        = len(query_words & candidate_words)
    overlap_score  = overlap / len(query_words) if query_words else 0
    len_ratio      = len(query.split()) / max(len(candidate.split()), 1)
    length_penalty = min(len_ratio, 1.0)
    return round(overlap_score * length_penalty, 3)


def _filter_price_outliers(prices: list[float]) -> list[float]:
    if len(prices) < 3:
        return prices
    med      = statistics.median(prices)
    filtered = [p for p in prices if p <= med * 2]
    return filtered if filtered else prices


def _haversine_miles(lat1, lon1, lat2, lon2):
    R = 3958.8
    lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
    return R * 2 * math.asin(math.sqrt(a))


def _get_user_latlon(zip_code: str) -> tuple[float, float] | None:
    try:
        res = sb.table("zip_centroids").select("latitude, longitude").eq("zip_code", zip_code).limit(1).execute()
        if res.data:
            return float(res.data[0]["latitude"]), float(res.data[0]["longitude"])
    except Exception:
        pass
    return None


def _load_store_locations() -> dict:
    try:
        rows, offset = [], 0
        while True:
            batch = (
                sb.table("store_locations")
                .select("retailer_key, retailer, zip_code, latitude, longitude, full_address, geocode_confidence")
                .not_.is_("latitude", "null")
                .not_.is_("longitude", "null")
                .range(offset, offset + 999)
                .execute()
                .data or []
            )
            rows.extend(batch)
            if len(batch) < 1000:
                break
            offset += 1000
        result = {}
        for r in rows:
            zip_code = (r["zip_code"] or "").strip()
            data = {
                "lat": float(r["latitude"]),
                "lng": float(r["longitude"]),
                "address": r.get("full_address") or None,
                "confidence": r.get("geocode_confidence") or "zip",
            }
            # Index by retailer_key (standardized, e.g. "elsuper") — primary key
            result[(r["retailer_key"], zip_code)] = data
            # Also index by display name (e.g. "el super") in case lookup uses it
            display_key = r["retailer"].lower().strip()
            if (display_key, zip_code) not in result:
                result[(display_key, zip_code)] = data
        return result
    except Exception:
        return {}


_STORE_LOCATION_CACHE: dict | None = None


def _get_store_locations() -> dict:
    global _STORE_LOCATION_CACHE
    if _STORE_LOCATION_CACHE is None:
        _STORE_LOCATION_CACHE = _load_store_locations()
    return _STORE_LOCATION_CACHE


def _get_store_info(retailer, zip_code, store_locations):
    """Returns store dict with lat, lng, address, confidence — or None."""
    display_key = retailer.lower().strip()
    # Derive retailer_key by stripping spaces/punctuation (e.g. "el super" → "elsuper")
    retailer_key = re.sub(r"[^a-z0-9]", "", display_key)
    zip_key = (zip_code or "").strip()

    # Exact match — try both retailer_key and display name
    exact = store_locations.get((retailer_key, zip_key)) or store_locations.get((display_key, zip_key))
    if exact and exact.get("confidence") != "zip":
        if exact.get("address"):
            return exact  # best: exact zip + address

    # Same zip prefix (first 2 digits) — finds stores in same metro area
    # Prefer entries with a full address; accept coordinate-only as fallback
    zip_prefix = zip_key[:2]
    prefix_coords_only = None
    for (r, z), info in store_locations.items():
        if r in (retailer_key, display_key) and info.get("confidence") != "zip":
            if z.startswith(zip_prefix):
                if info.get("address"):
                    return info  # best: same metro + address
                elif prefix_coords_only is None:
                    prefix_coords_only = info  # acceptable: same metro, coords only

    if prefix_coords_only:
        return prefix_coords_only

    # Last resort: exact zip match even without address (lat/lng still useful)
    return exact


def _normalize_size_key(base_amount, base_unit):
    if not base_amount or not base_unit:
        return None
    try:
        amount = float(base_amount)
    except (ValueError, TypeError):
        return None
    unit = base_unit.strip().lower()
    if unit in ("ct", "count", "pk", "pack") and 1 < amount <= 5:
        return None
    rounded = round(amount * 2) / 2
    return f"{rounded}_{unit}"


def _size_key_to_display(size_key: str) -> str:
    parts = size_key.split("_", 1)
    return f"{parts[0]} {parts[1]}" if len(parts) == 2 else size_key


def _calc_price_per_oz(price, base_amount, base_unit):
    if not base_amount or not base_unit:
        return None
    try:
        amount = float(base_amount)
        if amount <= 0:
            return None
    except (ValueError, TypeError):
        return None
    unit       = base_unit.strip().lower().replace(" ", "").replace("-", "").replace(".", "")
    multiplier = _UNIT_TO_OZ.get(unit)
    if not multiplier:
        return None
    oz = amount * multiplier
    return round(price / oz, 4) if oz > 0 else None


def _build_size_tiers(rows):
    tiers = defaultdict(list)
    for row in rows:
        key = _normalize_size_key(row.get("base_amount"), row.get("base_unit"))
        tiers[key if key else "unknown"].append(row)
    return tiers


def _make_deal_reason(r, rank, total_retailers, avg_price, avg_ppu, use_ppu, size_display):
    price = r["price"]
    ppu   = r.get("price_per_oz")
    size  = r.get("size") or size_display

    if rank == 0:
        if total_retailers <= 1:
            return "Only retailer found for this product"
        if use_ppu and ppu and avg_ppu:
            savings_pct = round((avg_ppu - ppu) / avg_ppu * 100)
            return f"Best value — {savings_pct}% below average price per oz across {total_retailers} retailers"
        else:
            savings = round(avg_price - price, 2)
            return f"Lowest price — ${savings:.2f} below average across {total_retailers} retailers"

    if use_ppu and ppu and avg_ppu:
        diff = round(ppu - avg_ppu, 4)
        if diff < 0:
            return f"${abs(diff):.4f}/oz below average — good value on {size}" if size else f"${abs(diff):.4f}/oz below average"
        elif diff == 0:
            return f"Average value at ${ppu:.4f}/oz"
        else:
            return f"${diff:.4f}/oz above average — better value in a different size"
    else:
        diff     = round(price - avg_price, 2)
        size_str = f" ({size})" if size else ""
        if diff < 0:
            return f"${abs(diff):.2f} below average{size_str}"
        elif diff == 0:
            return f"At average price{size_str}"
        else:
            return f"${diff:.2f} above average{size_str}"


def _build_retailer_list(rows, avg_price, use_ppu=False, size_display=None):
    seen = {}
    for row in rows:
        retailer = normalize_retailer(row.get("retailer") or "")
        price    = float(row["product_price"])
        zip_code = (row.get("zip_code") or "").strip()
        ppu      = _calc_price_per_oz(price, row.get("base_amount"), row.get("base_unit"))
        size_str = f'{row.get("base_amount")} {row.get("base_unit")}' if row.get("base_amount") else None

        if retailer not in seen:
            seen[retailer] = {"retailer": retailer, "price": price, "zip_code": zip_code,
                              "store_id": row.get("store_id"), "size": size_str, "price_per_oz": ppu}
        else:
            if use_ppu and ppu is not None:
                if seen[retailer].get("price_per_oz") is None or ppu < seen[retailer]["price_per_oz"]:
                    seen[retailer] = {"retailer": retailer, "price": price, "zip_code": zip_code,
                                      "store_id": row.get("store_id"), "size": size_str, "price_per_oz": ppu}
            elif price < seen[retailer]["price"]:
                seen[retailer].update({"price": price, "zip_code": zip_code,
                                       "store_id": row.get("store_id"), "size": size_str, "price_per_oz": ppu})

    retailers = sorted(seen.values(),
                       key=lambda r: (r.get("price_per_oz") or 999999) if use_ppu else r["price"])

    # Enrich with real store address + coordinates (OSM-geocoded, not centroids)
    store_locs = _get_store_locations()
    for r in retailers:
        info = _get_store_info(r["retailer"], r.get("zip_code") or "", store_locs)
        if info and info.get("confidence") != "zip":
            r["store_address"] = info.get("address") or None
            r["store_lat"] = info.get("lat")
            r["store_lng"] = info.get("lng")
        else:
            r["store_address"] = None
            r["store_lat"] = None
            r["store_lng"] = None

    if use_ppu:
        ppus_all = [r["price_per_oz"] for r in retailers if r.get("price_per_oz")]
        if len(ppus_all) >= 3:
            filtered_ppus = _filter_price_outliers(ppus_all)
            filtered_set  = set(filtered_ppus)
            retailers     = [r for r in retailers if r.get("price_per_oz") is None or r["price_per_oz"] in filtered_set]
    else:
        all_prices   = [r["price"] for r in retailers]
        filtered     = _filter_price_outliers(all_prices)
        filtered_set = set(filtered)
        retailers    = [r for r in retailers if r["price"] in filtered_set]

    prices          = [r["price"] for r in retailers]
    avg_price       = round(sum(prices) / len(prices), 2) if prices else avg_price
    total_retailers = len(retailers)

    if use_ppu:
        ppus    = [r["price_per_oz"] for r in retailers if r.get("price_per_oz")]
        avg_ppu = round(sum(ppus) / len(ppus), 4) if ppus else None
        for i, r in enumerate(retailers):
            if total_retailers <= 1:
                r["vs_avg"] = None
                r["vs_avg_pct"] = None
                r["deal_quality"] = None
                r["deal_reason"] = _make_deal_reason(r, i, total_retailers, avg_price, avg_ppu,
                                                       use_ppu=True, size_display=size_display)
                continue
            ppu = r.get("price_per_oz")
            if ppu is not None and avg_ppu:
                r["vs_avg"]     = round(r["price"] - avg_price, 2)
                r["vs_avg_pct"] = round((ppu - avg_ppu) / avg_ppu * 100, 1)
                r["vs_avg_ppu"] = round(ppu - avg_ppu, 4)
            else:
                vs_avg          = round(r["price"] - avg_price, 2)
                r["vs_avg"]     = vs_avg
                r["vs_avg_pct"] = round((vs_avg / avg_price) * 100, 1) if avg_price else 0
            pct = r["vs_avg_pct"]
            r["deal_quality"] = "great" if pct <= -15 else "good" if pct <= -5 else "fair" if pct <= 5 else "expensive"
            r["deal_reason"]  = _make_deal_reason(r, i, total_retailers, avg_price, avg_ppu,
                                                   use_ppu=True, size_display=size_display)
    else:
        for i, r in enumerate(retailers):
            if total_retailers <= 1:
                r["vs_avg"] = None
                r["vs_avg_pct"] = None
                r["deal_quality"] = None
                r["deal_reason"] = _make_deal_reason(r, i, total_retailers, avg_price, avg_ppu=None,
                                                       use_ppu=False, size_display=size_display)
                continue
            vs_avg          = round(r["price"] - avg_price, 2)
            vs_avg_pct      = round((vs_avg / avg_price) * 100, 1) if avg_price else 0
            r["vs_avg"]     = vs_avg
            r["vs_avg_pct"] = vs_avg_pct
            r["deal_quality"] = "great" if vs_avg_pct <= -15 else "good" if vs_avg_pct <= -5 else "fair" if vs_avg_pct <= 5 else "expensive"
            r["deal_reason"]  = _make_deal_reason(r, i, total_retailers, avg_price, avg_ppu=None,
                                                   use_ppu=False, size_display=size_display)
    return retailers


def _build_result(
    canonical_product_name: str,
    brand: str | None,
    rows: list[dict],
    user_lat: float | None = None,
    user_lon: float | None = None,
    radius_miles: float | None = None,
    selected_size: str | None = None,
) -> dict:
    store_locations = _get_store_locations() if user_lat is not None else {}

    # Step 1: Location filter
    location_filtered = []
    for row in rows:
        zip_code     = (row.get("zip_code") or "").strip()
        retailer_raw = row.get("retailer") or ""
        if user_lat is not None and radius_miles is not None:
            store_latlon = _get_store_info(retailer_raw, zip_code, store_locations)
            if store_latlon:
                dist = _haversine_miles(user_lat, user_lon, store_latlon["lat"], store_latlon["lng"])
                if dist > radius_miles:
                    continue
        location_filtered.append(row)

    if not location_filtered:
        return {"product": canonical_product_name, "brand": brand, "retailers": []}

    # Step 2: Build size tiers
    tiers = _build_size_tiers(location_filtered)

    # Step 3: Valid size tiers (2+ distinct retailers)
    valid_tiers = {
        k: v for k, v in tiers.items()
        if k != "unknown" and len(set(r.get("retailer") for r in v)) >= 2
    }

    # Step 4: Determine mode
    # ─────────────────────────────────────────────────────────────────
    # DEFAULT = exact size (Alston: always like-for-like first)
    # PPU activates ONLY when:
    #   a) user explicitly passes size='ppu'
    #   b) no valid exact size tier exists at all (fallback)
    # Size tabs in UI let users switch to other sizes or PPU explicitly.
    # ─────────────────────────────────────────────────────────────────
    explicit_ppu = selected_size == "ppu"
    use_ppu_mode = False

    # Step 5: Pick active rows
    if explicit_ppu:
        # User explicitly requested PPU comparison
        ppu_units = {
            size_key.split("_", 1)[1]
            for size_key in valid_tiers
            if "_" in size_key and size_key.split("_", 1)[1] in _UNIT_TO_OZ
        }
        if valid_tiers and ppu_units:
            use_ppu_mode    = True
            active_rows     = [r for tier in valid_tiers.values() for r in tier]
            active_size_key = None
        else:
            # No convertible sizes to do PPU — fall back to largest tier
            active_size_key = max(valid_tiers, key=lambda k: len(set(r.get("retailer") for r in valid_tiers[k]))) if valid_tiers else None
            active_rows     = valid_tiers[active_size_key] if active_size_key else location_filtered

    elif selected_size and selected_size in valid_tiers:
        # User selected a specific size tab
        active_size_key = selected_size
        active_rows     = valid_tiers[active_size_key]

    elif valid_tiers:
        # DEFAULT: pick the size tier with the most retailers — exact like-for-like
        active_size_key = max(valid_tiers, key=lambda k: len(set(r.get("retailer") for r in valid_tiers[k])))
        active_rows     = valid_tiers[active_size_key]

    else:
        # No valid multi-retailer size tiers — fallback path
        active_size_key = None
        sized_rows      = [r for r in location_filtered if r.get("base_amount")]
        sized_retailers = len(set(r.get("retailer") for r in sized_rows))

        if sized_retailers >= 2:
            unit_groups: dict[str, list] = defaultdict(list)
            for r in sized_rows:
                unit = (r.get("base_unit") or "").strip().lower()
                unit_groups[unit].append(r)

            convertible_groups = {
                unit: rows for unit, rows in unit_groups.items()
                if unit.replace(" ", "").replace("-", "").replace(".", "") in _UNIT_TO_OZ
            }

            if convertible_groups:
                all_conv_rows    = [r for rows in convertible_groups.values() for r in rows]
                distinct_amounts = set(r.get("base_amount") for r in all_conv_rows if r.get("base_amount"))
                distinct_conv_r  = len(set(r.get("retailer") for r in all_conv_rows))

                if len(distinct_amounts) > 1 and distinct_conv_r >= 2:
                    # Only use PPU in fallback when no exact size exists at all
                    use_ppu_mode = True
                    active_rows  = all_conv_rows
                else:
                    best_unit   = max(unit_groups, key=lambda u: len(set(r.get("retailer") for r in unit_groups[u])))
                    best_rows   = unit_groups[best_unit]
                    active_rows = best_rows if len(set(r.get("retailer") for r in best_rows)) >= 2 else sized_rows
            else:
                best_unit   = max(unit_groups, key=lambda u: len(set(r.get("retailer") for r in unit_groups[u])))
                active_rows = unit_groups[best_unit]
        else:
            active_rows = location_filtered

    if not active_rows:
        return {"product": canonical_product_name, "brand": brand, "retailers": []}

    prices_for_avg = [float(r["product_price"]) for r in active_rows if r.get("product_price")]
    avg_price      = round(sum(prices_for_avg) / len(prices_for_avg), 2) if prices_for_avg else 0
    size_display   = _size_key_to_display(active_size_key) if active_size_key and not use_ppu_mode else None

    retailers = _build_retailer_list(active_rows, avg_price, use_ppu=use_ppu_mode, size_display=size_display)

    if not retailers:
        return {"product": canonical_product_name, "brand": brand, "retailers": []}

    prices      = [r["price"] for r in retailers]
    min_price   = min(prices)
    max_price   = max(prices)
    avg_price   = round(sum(prices) / len(prices), 2)
    savings_abs = round(max_price - min_price, 2)
    savings_pct = round(((max_price - min_price) / max_price) * 100, 1) if max_price else 0

    # Step 6: Available sizes
    # Always show all valid size tiers as tabs so user can switch
    # Add a "Compare by $/oz" tab when multiple convertible sizes exist
    available_sizes = []
    has_ppu_option  = False

    if valid_tiers:
        ppu_units = {
            size_key.split("_", 1)[1]
            for size_key in valid_tiers
            if "_" in size_key and size_key.split("_", 1)[1] in _UNIT_TO_OZ
        }
        has_ppu_option = len(valid_tiers) > 1 and len(ppu_units) >= 1

        for size_key, tier_rows in sorted(valid_tiers.items()):
            tier_prices = [float(r["product_price"]) for r in tier_rows if r.get("product_price")]
            if not tier_prices:
                continue
            available_sizes.append({
                "size":           _size_key_to_display(size_key),
                "size_key":       size_key,
                "retailer_count": len(set(r.get("retailer") for r in tier_rows)),
                "min_price":      min(tier_prices),
                "max_price":      max(tier_prices),
                "is_selected":    (size_key == active_size_key and not use_ppu_mode),
            })

        # Add PPU tab when multiple convertible sizes exist
        if has_ppu_option:
            available_sizes.append({
                "size":           "Compare by $/oz",
                "size_key":       "ppu",
                "retailer_count": len(set(r.get("retailer") for tier in valid_tiers.values() for r in tier)),
                "min_price":      None,
                "max_price":      None,
                "is_selected":    use_ppu_mode,
            })

    elif use_ppu_mode and active_rows:
        fallback_tiers: dict[str, list] = defaultdict(list)
        for r in active_rows:
            key = _normalize_size_key(r.get("base_amount"), r.get("base_unit"))
            if key:
                fallback_tiers[key].append(r)
        for size_key, tier_rows in sorted(fallback_tiers.items()):
            tier_prices = [float(r["product_price"]) for r in tier_rows if r.get("product_price")]
            if not tier_prices:
                continue
            available_sizes.append({
                "size":           _size_key_to_display(size_key),
                "size_key":       size_key,
                "retailer_count": len(set(r.get("retailer") for r in tier_rows)),
                "min_price":      min(tier_prices),
                "max_price":      max(tier_prices),
                "is_selected":    False,
            })

    ppus     = [r["price_per_oz"] for r in retailers if r.get("price_per_oz")]
    best_ppu = round(min(ppus), 4) if ppus else None

    if use_ppu_mode and best_ppu and len(ppus) >= 2:
        worst_ppu   = max(ppus)
        ppu_savings = round(((worst_ppu - best_ppu) / worst_ppu) * 100, 1) if worst_ppu else 0
        compare_summary = (
            f"Comparing {len(retailers)} retailers across {len([s for s in available_sizes if s['size_key'] != 'ppu'])} size options by $/oz. "
            f"Best value is ${best_ppu:.4f}/oz at {retailers[0]['retailer']}. "
            f"You could save up to {ppu_savings}% by choosing the right retailer."
        )
    elif len(retailers) <= 1:
        compare_summary = (
            f"Found at {retailers[0]['retailer']} for ${min_price:.2f}"
            + (f" ({size_display})" if size_display else "") + "."
        )
    else:
        compare_summary = (
            f"Comparing {len(retailers)} retailers"
            + (f" for {size_display}" if size_display else "") +
            f". Best price is ${min_price:.2f} at {retailers[0]['retailer']}, "
            f"saving ${savings_abs:.2f} vs the highest price."
        )

    return {
        "product":            canonical_product_name,
        "brand":              brand,
        "size":               size_display,
        "compare_mode":       "price_per_oz" if use_ppu_mode else "exact_size",
        "compare_summary":    compare_summary,
        "available_sizes":    available_sizes,
        "best_price_per_oz":  best_ppu,
        "retailer_count":     len(retailers),
        "min_price":          min_price,
        "max_price":          max_price,
        "avg_price":          avg_price,
        "savings_vs_max":     savings_abs,
        "savings_pct_vs_max": ppu_savings if (use_ppu_mode and best_ppu and len(ppus) >= 2) else savings_pct,
        "best_retailer":      retailers[0]["retailer"],
        "retailers":          retailers,
    }


def compare_product_across_retailers(
    canonical_product_name: str,
    brand: str | None = None,
    limit: int = 50,
    zip_code: str | None = None,
    radius_miles: float = 25.0,
    size: str | None = None,
) -> dict:
    # Use Kiran's AI-validated canonical name if available — more accurate than ours
    # canonical_product_name is already our normalized output, so pass as pre_normalized too
    kiran_name = _kiran_canonical(canonical_product_name, pre_normalized=canonical_product_name)
    if kiran_name:
        canonical_product_name = kiran_name

    user_lat, user_lon = None, None
    if zip_code:
        latlon = _get_user_latlon(zip_code)
        if latlon:
            user_lat, user_lon = latlon

    def _fetch_exact(name: str) -> list[dict]:
        q = (
            sb.table("flyer_deals")
            .select("retailer, product_price, zip_code, store_id, canonical_product_name, brand, base_amount, base_unit")
            .eq("canonical_product_name", name)
            .not_.is_("product_price", "null")
            .limit(limit)
        )
        if brand:
            q = q.eq("brand", brand)
        return q.execute().data or []

    rows = _fetch_exact(canonical_product_name)

    if not rows or len(set(r.get("retailer") for r in rows)) <= 1:
        sorted_name = _word_sort_key(canonical_product_name)
        if sorted_name != canonical_product_name:
            alt_rows = _fetch_exact(sorted_name)
            if len(set(r.get("retailer") for r in alt_rows)) > len(set(r.get("retailer") for r in rows)):
                rows = alt_rows

    if not rows or len(set(r.get("retailer") for r in rows)) <= 1:
        q = (
            sb.table("flyer_deals")
            .select("retailer, product_price, zip_code, store_id, canonical_product_name, brand, base_amount, base_unit")
            .ilike("canonical_product_name", f"%{canonical_product_name}%")
            .not_.is_("product_price", "null")
            .limit(500)
        )
        if brand:
            q = q.eq("brand", brand)
        fuzzy_rows = q.execute().data or []

        if fuzzy_rows:
            groups: dict[str, list] = defaultdict(list)
            for r in fuzzy_rows:
                name = r["canonical_product_name"] or ""
                if len(name) <= _MAX_NAME_LENGTH:
                    groups[name].append(r)

            if groups:
                def _candidate_score(name: str) -> float:
                    sim            = _name_similarity(canonical_product_name, name)
                    retailer_count = len(set(r.get("retailer") for r in groups[name]))
                    return sim * 10 + retailer_count * 0.1

                best_name = max(groups, key=_candidate_score)
                best_rows = groups[best_name]
                if len(set(r.get("retailer") for r in best_rows)) >= len(set(r.get("retailer") for r in rows)):
                    rows                   = best_rows
                    canonical_product_name = best_name

    # If still no rows, try progressively shorter versions of the name
    # e.g. "crunch berries cereal" → "crunch berries" → "crunch"
    if not rows:
        words = canonical_product_name.split()
        for n in range(len(words) - 1, 0, -1):
            shorter = " ".join(words[:n])
            q = (
                sb.table("flyer_deals")
                .select("retailer, product_price, zip_code, store_id, canonical_product_name, brand, base_amount, base_unit")
                .ilike("canonical_product_name", f"%{shorter}%")
                .not_.is_("product_price", "null")
                .limit(200)
            )
            if brand:
                q = q.eq("brand", brand)
            shorter_rows = q.execute().data or []
            if shorter_rows:
                rows = shorter_rows
                canonical_product_name = shorter
                break

    if not rows:
        return {"product": canonical_product_name, "brand": brand, "retailers": []}

    result = _build_result(
        canonical_product_name, brand, rows,
        user_lat=user_lat, user_lon=user_lon,
        radius_miles=radius_miles if zip_code else None,
        selected_size=size,
    )

    # If geographic filter left us with 0 retailers, retry nationally so
    # users always see pricing context even when local data is sparse
    if zip_code and len(result.get("retailers", [])) == 0:
        result = _build_result(
            canonical_product_name, brand, rows,
            user_lat=None, user_lon=None,
            radius_miles=None,
            selected_size=size,
        )
        if result.get("retailers"):
            result["compare_summary"] = (
                result.get("compare_summary", "")
                + " (National pricing — no nearby stores found.)"
            )

    return result


def search_products(
    query: str,
    limit: int = 10,
    zip_code: str | None = None,
    radius_miles: float = 25.0,
) -> list[dict]:
    user_lat, user_lon = None, None
    if zip_code:
        latlon = _get_user_latlon(zip_code)
        if latlon:
            user_lat, user_lon = latlon

    store_locations = _get_store_locations() if user_lat is not None else {}

    rows = (
        sb.table("flyer_deals")
        .select("canonical_product_name, brand, product_price, retailer, zip_code, match_key, image_link")
        .ilike("canonical_product_name", f"%{query}%")
        .not_.is_("product_price", "null")
        .not_.is_("canonical_product_name", "null")
        .limit(500)
        .execute()
        .data or []
    )

    seen: dict[tuple, dict] = {}

    for row in rows:
        row_zip       = (row.get("zip_code") or "").strip()
        retailer_raw  = row.get("retailer") or ""
        raw_canonical = row["canonical_product_name"] or ""

        if len(raw_canonical) > _MAX_NAME_LENGTH:
            continue

        if user_lat is not None:
            store_info = _get_store_info(retailer_raw, row_zip, store_locations)
            if store_info:
                dist = _haversine_miles(user_lat, user_lon, store_info["lat"], store_info["lng"])
                if dist > radius_miles:
                    continue

        brand      = (row.get("brand") or "").lower().strip() or None
        normalized = build_canonical_name(raw_canonical, brand)
        key        = (normalized, brand)

        if key not in seen:
            seen[key] = {"retailers": set(), "prices": [], "match_key": None, "image_link": None}
        seen[key]["retailers"].add(normalize_retailer(retailer_raw))
        seen[key]["prices"].append(float(row["product_price"]))
        # Prefer non-null match_key and image_link
        if not seen[key]["match_key"] and row.get("match_key"):
            seen[key]["match_key"] = row["match_key"]
        if not seen[key]["image_link"] and row.get("image_link"):
            seen[key]["image_link"] = row["image_link"]

    results = []
    for (normalized_name, brand), data in seen.items():
        prices = [p for p in data["prices"] if p > 0]
        if not prices:
            continue
        results.append({
            "canonical_product_name": normalized_name,
            "brand":                  brand,
            "retailer_count":         len(data["retailers"]),
            "min_price":              min(prices),
            "max_price":              max(prices),
            "avg_price":              round(sum(prices) / len(prices), 2),
            "match_key":              data.get("match_key"),
            "image_link":             data.get("image_link"),
        })

    return sorted(results, key=lambda x: x["retailer_count"], reverse=True)[:limit]