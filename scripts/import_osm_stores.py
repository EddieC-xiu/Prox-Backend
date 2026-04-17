# scripts/import_osm_stores.py
# Fetches store locations from the OpenStreetMap Overpass API and upserts
# them into the store_locations table.
#
# Usage:
#   PYTHONPATH=. python scripts/import_osm_stores.py
#   PYTHONPATH=. python scripts/import_osm_stores.py --retailer walmart
#   PYTHONPATH=. python scripts/import_osm_stores.py --dry-run
#   PYTHONPATH=. python scripts/import_osm_stores.py --retailer walmart --dry-run

import argparse
import logging
import math
import time
from dataclasses import dataclass

import requests

try:
    import numpy as np
    import pgeocode as _pgeocode

    _pgeo_data: "tuple | None" = None  # (codes_array, coords_array) — loaded once

    def _fallback_zip(lat: float, lon: float) -> str | None:
        """Return the nearest US ZIP code for a coordinate pair.

        Used only when an OSM element has coordinates but no addr:postcode tag.
        pgeocode bundles the GeoNames ZCTA dataset locally (~40k ZIP centroids).
        The nearest-neighbour search is vectorised over the full table with numpy
        so each call takes < 1 ms — no network call, no API key.
        """
        global _pgeo_data
        if _pgeo_data is None:
            nomi = _pgeocode.Nominatim("us")
            df = nomi._data[["postal_code", "latitude", "longitude"]].dropna()
            _pgeo_data = (
                df["postal_code"].values,
                df[["latitude", "longitude"]].values.astype(float),
            )
        codes, coords = _pgeo_data
        diffs = coords - np.array([lat, lon])
        dists = (diffs * diffs).sum(axis=1)
        return str(codes[dists.argmin()])

except Exception:
    # pgeocode or numpy not installed — fallback silently no-ops
    def _fallback_zip(lat: float, lon: float) -> str | None:  # type: ignore[misc]
        return None

from config.supabase import supabase

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

# Multiple mirrors — tried in order, next used on failure
OVERPASS_ENDPOINTS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.openstreetmap.fr/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass.private.coffee/api/interpreter",
]

# Seconds between retailers (be a good citizen)
REQUEST_DELAY = 15

# Seconds between region sub-queries for large retailers
REGION_DELAY = 8

# Batch size for Supabase upserts
UPSERT_BATCH = 200

# Retailers with enough stores that a single US-wide query always times out.
# These are split into 6 regions instead.
LARGE_RETAILERS = {"walmart", "target", "aldi", "costco", "samsclub", "wholefoods", "traderjoes"}

# Six US sub-regions: (label, south, west, north, east)
US_REGIONS = [
    ("northeast", 37.0,  -82.0, 47.5,  -66.9),   # Maine reaches 47.5 — unchanged
    ("southeast", 24.4,  -92.0, 37.0,  -75.0),   # unchanged
    ("midwest",   36.5,  -97.5, 49.0,  -80.5),   # 49.4 → 49.0  (49th-parallel border)
    ("south",     25.8, -106.7, 36.5,  -93.5),   # unchanged
    ("mountain",  31.3, -117.0, 49.0, -103.0),   # unchanged (was already 49.0)
    ("west",      32.5, -125.0, 49.0, -114.0),   # 49.4 → 49.0  (BC border)
]

# Full contiguous US bbox for smaller retailers
US_BBOX = "24.396308,-125.000000,49.384358,-66.934570"

# Two elements within this distance (metres) are treated as the same physical
# store. 500 m covers the diagonal of a large superstore footprint plus its
# parking lot (entrance node at the kerb vs way centroid deep in the lot can
# exceed 400 m on a large Meijer/Walmart property). Two same-chain stores are
# never closer than ~3 miles, so false merges are not a concern.
COORD_DEDUP_RADIUS_M = 500


# ---------------------------------------------------------------------------
# Retailer definitions
# ---------------------------------------------------------------------------

@dataclass
class RetailerDef:
    retailer_key:          str
    brand_names:           list[str]
    wikidata_id:           str | None = None
    min_lat:               float | None = None           # drop elements south of this latitude
    allowed_zip_prefixes:  tuple[str, ...] | None = None # if set, drop any ZIP not starting with one of these
    exclude_countries:     tuple[str, ...] | None = None # if set, drop elements tagged addr:country= any of these


# Wikidata IDs kept only for chains where the ID has been manually verified
# in the OSM wiki (https://wiki.openstreetmap.org/wiki/Tag:brand:wikidata=*).
# All others use brand= / name= tag matching only to avoid cross-contamination
# (e.g. Q672170 was pulling Publix nodes instead of Meijer).
RETAILERS: list[RetailerDef] = [
    # ── Verified wikidata IDs ───────────────────────────────────────────────
    RetailerDef("walmart",      ["Walmart", "Walmart Supercenter", "Walmart Neighborhood Market"],
                "Q483551",
                exclude_countries=("CA", "MX")),
    RetailerDef("target",       ["Target", "Super Target"],
                "Q1046951"),
    RetailerDef("aldi",         ["ALDI", "Aldi"],
                "Q41187"),
    RetailerDef("costco",       ["Costco", "Costco Wholesale", "Costco Business Center"],
                "Q715583",
                exclude_countries=("CA", "MX")),
    RetailerDef("samsclub",     ["Sam's Club"],
                "Q1972120"),
    RetailerDef("wholefoods",   ["Whole Foods Market", "Whole Foods"],
                "Q1101859",
                exclude_countries=("CA", "MX")),
    RetailerDef("traderjoes",   ["Trader Joe's"],
                "Q688934"),
    RetailerDef("heb",          ["H-E-B", "H-E-B Plus!"],
                "Q1095857",
                min_lat=26.5,
                allowed_zip_prefixes=("75", "76", "77", "78", "79", "87", "88")),

    # ── Brand / name tag matching only (wikidata IDs removed) ──────────────
    RetailerDef("wegmans",      ["Wegmans", "Wegmans Food Markets"]),
    RetailerDef("ralphs",       ["Ralphs", "Ralph's"]),
    RetailerDef("shoprite",     ["ShopRite"]),
    RetailerDef("sprouts",      ["Sprouts Farmers Market", "Sprouts"]),
    RetailerDef("stopandshop",  ["Stop & Shop", "Stop and Shop"]),
    RetailerDef("foodlion",     ["Food Lion"]),
    RetailerDef("vons",         ["Vons"]),
    RetailerDef("food4less",    ["Food 4 Less", "Food4Less"]),
    RetailerDef("staterbros",   ["Stater Bros.", "Stater Bros"]),
    RetailerDef("meijer",       ["Meijer"]),
    RetailerDef("gianteagle",   ["Giant Eagle"]),
    RetailerDef("giantfood",    ["Giant Food", "Giant Food Stores"]),
    RetailerDef("winndixie",    ["Winn-Dixie"]),
    RetailerDef("harristeeter", ["Harris Teeter"]),
    RetailerDef("fredmeyer",    ["Fred Meyer"]),
    RetailerDef("kingsoopers",  ["King Soopers", "King Soopers Marketplace"],
                "Q931455"),
    RetailerDef("smiths",       ["Smith's Food and Drug", "Smith's"]),
    RetailerDef("foodbazaar",   ["Food Bazaar"]),
]

RETAILER_MAP: dict[str, RetailerDef] = {r.retailer_key: r for r in RETAILERS}


# ---------------------------------------------------------------------------
# Overpass query builder
# ---------------------------------------------------------------------------

def _build_query(retailer: RetailerDef, bbox: str, timeout: int = 300) -> str:
    union_parts = []

    # Wikidata match (most precise) — only used when ID is verified
    if retailer.wikidata_id:
        f = f'["brand:wikidata"="{retailer.wikidata_id}"]'
        union_parts.append(f"  node{f}({bbox});")
        union_parts.append(f"  way{f}({bbox});")

    # brand= and name= matching for all retailers.
    # OSM contributors tag chains inconsistently — some nodes only have name=,
    # others only brand=, so we need both to avoid zero-result retailers.
    for name in retailer.brand_names:
        escaped = name.replace('"', '\\"')
        for tag in ("brand", "name"):
            f = f'["{tag}"="{escaped}"]'
            union_parts.append(f"  node{f}({bbox});")
            union_parts.append(f"  way{f}({bbox});")

    return (
        f"[out:json][timeout:{timeout}];\n(\n"
        + "\n".join(union_parts)
        + "\n);\nout center tags;"
    )


# ---------------------------------------------------------------------------
# Overpass fetch — tries each mirror, retries once on timeout
# ---------------------------------------------------------------------------

def _post_overpass(query: str) -> list[dict] | None:
    """Try each mirror in order. Returns elements list or None on total failure."""
    for endpoint in OVERPASS_ENDPOINTS:
        for attempt in (1, 2):
            try:
                logger.debug(f"[OSM] POST {endpoint} (attempt {attempt})")
                resp = requests.post(
                    endpoint,
                    data={"data": query},
                    timeout=330,
                    headers={"User-Agent": "prox-backend-sai/1.0 (grocery deal finder)"},
                )
                resp.raise_for_status()
                return resp.json().get("elements", [])
            except requests.exceptions.Timeout:
                logger.warning(f"[OSM] Timeout on {endpoint} attempt {attempt}")
                if attempt == 1:
                    time.sleep(5)
            except requests.exceptions.HTTPError as e:
                logger.warning(f"[OSM] HTTP error on {endpoint}: {e}")
                break   # try next mirror
            except Exception as e:
                logger.warning(f"[OSM] Error on {endpoint}: {e}")
                break

    return None


def _fetch_osm_bbox(retailer: RetailerDef, bbox: str, label: str) -> list[dict]:
    query = _build_query(retailer, bbox)
    logger.info(f"[OSM] '{retailer.retailer_key}' region={label}")
    result = _post_overpass(query)
    if result is None:
        logger.error(f"[OSM] All mirrors failed for '{retailer.retailer_key}' region={label}")
        return []
    logger.info(f"[OSM] '{retailer.retailer_key}' region={label} → {len(result)} elements")
    return result


# ---------------------------------------------------------------------------
# Coordinate helpers
# ---------------------------------------------------------------------------

def _get_coords(el: dict) -> tuple[float, float] | None:
    """Return (lat, lon) for a node or way-with-center element, or None."""
    if el.get("type") == "node":
        lat, lon = el.get("lat"), el.get("lon")
    else:
        c = el.get("center", {})
        lat, lon = c.get("lat"), c.get("lon")
    if lat is not None and lon is not None:
        return float(lat), float(lon)
    return None


def _haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance in metres between two lat/lon points."""
    R = 6_371_000.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2) ** 2
    return R * 2 * math.asin(math.sqrt(a))


# ---------------------------------------------------------------------------
# Dedup
# ---------------------------------------------------------------------------

def _dedup_elements(elements: list[dict]) -> list[dict]:
    """Remove node/way duplicates for the same physical store.

    Pass 1 — prefer ways over nodes: drop any node that shares a
    (zip, housenumber, street) key with a way.

    Pass 2 — same-type address dedup: drop any element whose full address key
    (zip + housenumber + street) has already been seen, regardless of type.

    Pass 3 — ZIP-mismatch address dedup: drop any element whose
    (housenumber, street) has already been seen, even if the ZIP differs.
    This catches the common OSM pattern where the same store has one node
    tagged with the correct ZIP and another with an adjacent ZIP code.

    Pass 4 — coordinate proximity dedup: drop any element whose coordinates
    fall within COORD_DEDUP_RADIUS_M metres of an already-accepted element.
    This catches the remaining cases where house numbers differ slightly
    between the main-entrance node, the building polygon centroid, the
    pharmacy entrance, etc.

    Elements with no address key / no coordinates are always kept.
    """
    def _full_addr_key(el: dict) -> tuple | None:
        """(zip, housenumber, street) — requires all three fields."""
        tags = el.get("tags", {})
        zip_code = tags.get("addr:postcode", "").strip()[:5]
        number   = tags.get("addr:housenumber", "").strip()
        street   = tags.get("addr:street", "").split(";")[0].strip()
        if zip_code and number and street:
            return (zip_code, number.lower(), street.lower())
        return None

    def _addr_only_key(el: dict) -> tuple | None:
        """(housenumber, street) without ZIP — for ZIP-mismatch dedup."""
        tags = el.get("tags", {})
        number = tags.get("addr:housenumber", "").strip()
        street = tags.get("addr:street", "").split(";")[0].strip()
        if number and street:
            return (number.lower(), street.lower())
        return None

    # ------------------------------------------------------------------
    # Pass 1: collect way address keys, drop nodes shadowed by a way
    # ------------------------------------------------------------------
    way_keys: set[tuple] = set()
    ways:  list[dict] = []
    nodes: list[dict] = []

    for el in elements:
        if el.get("type") == "way":
            ways.append(el)
            key = _full_addr_key(el)
            if key:
                way_keys.add(key)
        else:
            nodes.append(el)

    deduped_nodes = [
        el for el in nodes
        if (k := _full_addr_key(el)) is None or k not in way_keys
    ]
    dropped_pass1 = len(nodes) - len(deduped_nodes)

    # ------------------------------------------------------------------
    # Pass 2: full address-key dedup (zip + number + street)
    # ------------------------------------------------------------------
    seen_full: set[tuple] = set()
    after_pass2: list[dict] = []
    for el in ways + deduped_nodes:
        key = _full_addr_key(el)
        if key is None or key not in seen_full:
            after_pass2.append(el)
            if key:
                seen_full.add(key)
    dropped_pass2 = (len(ways) + len(deduped_nodes)) - len(after_pass2)

    # ------------------------------------------------------------------
    # Pass 3: ZIP-mismatch dedup — same (number, street), different ZIP.
    # Keeps the first element seen for each address, regardless of ZIP.
    # ------------------------------------------------------------------
    seen_addr: set[tuple] = set()
    after_pass3: list[dict] = []
    for el in after_pass2:
        key = _addr_only_key(el)
        if key is None or key not in seen_addr:
            after_pass3.append(el)
            if key:
                seen_addr.add(key)
    dropped_pass3 = len(after_pass2) - len(after_pass3)

    # ------------------------------------------------------------------
    # Pass 4: coordinate proximity dedup — drop any element within
    # COORD_DEDUP_RADIUS_M metres of an already-accepted element.
    # Handles OSM stores with multiple entrance/corner nodes that have
    # slightly different house numbers and therefore survive address dedup.
    # ------------------------------------------------------------------
    accepted_coords: list[tuple[float, float]] = []
    after_pass4: list[dict] = []
    for el in after_pass3:
        coords = _get_coords(el)
        if coords is None:
            # No coordinates — keep unconditionally
            after_pass4.append(el)
            continue
        lat, lon = coords
        too_close = any(
            _haversine_m(lat, lon, alat, alon) < COORD_DEDUP_RADIUS_M
            for alat, alon in accepted_coords
        )
        if not too_close:
            after_pass4.append(el)
            accepted_coords.append((lat, lon))
    dropped_pass4 = len(after_pass3) - len(after_pass4)

    total_dropped = dropped_pass1 + dropped_pass2 + dropped_pass3 + dropped_pass4
    if total_dropped:
        logger.debug(
            f"[OSM] dedup: pass1={dropped_pass1} (node shadowed by way), "
            f"pass2={dropped_pass2} (same full address), "
            f"pass3={dropped_pass3} (same address/different ZIP), "
            f"pass4={dropped_pass4} (within {COORD_DEDUP_RADIUS_M}m)"
        )

    return after_pass4


def _fetch_osm(retailer: RetailerDef) -> list[dict]:
    """Fetch all US elements, splitting into regions for large retailers."""
    if retailer.retailer_key in LARGE_RETAILERS:
        all_elements: list[dict] = []
        seen_ids: set[int] = set()
        for label, south, west, north, east in US_REGIONS:
            bbox = f"{south},{west},{north},{east}"
            elements = _fetch_osm_bbox(retailer, bbox, label)
            for el in elements:
                if el["id"] not in seen_ids:
                    seen_ids.add(el["id"])
                    all_elements.append(el)
            if label != US_REGIONS[-1][0]:
                time.sleep(REGION_DELAY)
        logger.info(
            f"[OSM] '{retailer.retailer_key}' total unique elements: {len(all_elements)}"
        )
        return _dedup_elements(all_elements)
    else:
        return _dedup_elements(_fetch_osm_bbox(retailer, US_BBOX, "us"))


# ---------------------------------------------------------------------------
# Element → store_locations row
# ---------------------------------------------------------------------------

def _element_to_row(element: dict, retailer_key: str) -> dict | None:
    tags = element.get("tags", {})

    coords = _get_coords(element)
    if coords is None:
        return None
    lat, lon = coords

    # ── Fix: latitude guard (e.g. blocks H-E-B Mexico stores) ──────────────
    retailer_def = RETAILER_MAP.get(retailer_key)
    if retailer_def and retailer_def.min_lat is not None and lat < retailer_def.min_lat:
        return None

    # ── Fix: country exclusion (e.g. blocks Costco/WholeFoods/Walmart Canada & Mexico stores) ─
    # Catches elements explicitly tagged addr:country=CA / MX in OSM.
    # Complements the tightened US_REGIONS bboxes (now capped at 49.0°N) which
    # handle stores above the 49th parallel that lack a country tag entirely.
    if retailer_def and retailer_def.exclude_countries:
        country = tags.get("addr:country", "").strip().upper()
        if country and country in {c.upper() for c in retailer_def.exclude_countries}:
            return None

    zip_code = (tags.get("addr:postcode") or tags.get("postal_code") or "").strip()[:5]
    # ── Fix: reject non-US postal codes (e.g. Canadian "H3W 2") ────────────
    # A valid US ZIP is exactly 5 ASCII digits. Anything else (alphanumeric
    # Canadian/Mexican codes) must be discarded so pgeocode can assign the
    # nearest real US ZIP from coordinates instead of storing garbage.
    if zip_code and not zip_code.isdigit():
        zip_code = ""
    if not zip_code or len(zip_code) < 5:
        zip_code = _fallback_zip(lat, lon) or ""
    if not zip_code or len(zip_code) < 5:
        return None

    # ── Fix: ZIP-prefix allowlist (e.g. H-E-B TX/NM only) ──────────────────
    if retailer_def and retailer_def.allowed_zip_prefixes:
        if not any(zip_code.startswith(p) for p in retailer_def.allowed_zip_prefixes):
            return None

    house_number = tags.get("addr:housenumber", "").strip()
    # OSM sometimes stores multiple values separated by ";" — take the first
    street       = tags.get("addr:street", "").split(";")[0].strip()
    address      = f"{house_number} {street}".strip() or None
    city         = tags.get("addr:city") or None
    state        = tags.get("addr:state") or None
    full_address = (
        f"{address}, {city or ''}, {state or ''} {zip_code}".strip(", ")
        if address else None
    )
    name = (
        tags.get("name") or
        tags.get("brand") or
        retailer_key.replace("_", " ").title()
    )

    return {
        "retailer_key":       retailer_key,
        "retailer":           name,
        "store_name":         name,
        "address":            address,
        "full_address":       full_address,
        "city":               city,
        "state":              state,
        "zip_code":           zip_code,
        "latitude":           lat,
        "longitude":          lon,
        "geocode_source":     "osm",
        "geocode_confidence": "address",
        "source":             "osm",
        "osm_id":             str(element.get("id")),
    }


# ---------------------------------------------------------------------------
# Upsert
# ---------------------------------------------------------------------------

def _upsert_batch(rows: list[dict], dry_run: bool) -> tuple[int, int]:
    if dry_run:
        for row in rows:
            logger.info(
                f"[DRY-RUN] {row['retailer_key']} | {row['zip_code']} | "
                f"{row.get('city')} | {row.get('address')}"
            )
        return len(rows), 0
    try:
        # Use retailer_key,zip_code as the conflict target to match the
        # store_locations unique constraint (store_locations_retailer_key_zip_code_key).
        # One store per retailer per ZIP — consistent with how _create_store works
        # in store_matching.py.
        supabase.table("store_locations").upsert(
            rows, on_conflict="retailer_key,zip_code"
        ).execute()
        return len(rows), 0
    except Exception as e:
        logger.error(f"[OSM] Upsert failed: {e}")
        return 0, len(rows)


def import_retailer(retailer: RetailerDef, dry_run: bool) -> dict:
    stats = {"fetched": 0, "valid": 0, "upserted": 0, "skipped": 0}

    elements = _fetch_osm(retailer)
    stats["fetched"] = len(elements)

    rows = [r for el in elements if (r := _element_to_row(el, retailer.retailer_key))]

    # Pass 5 — drop ZIP-only rows (no address) when the same ZIP already has
    # at least one fully-addressed row.  These are phantom OSM nodes (old
    # entrances, pharmacy sub-nodes, parking-lot pins) whose coordinates
    # happened to be >500 m from the main store node and therefore survived
    # coord dedup, but whose pgeocode-assigned ZIP collides with a real entry.
    # We keep a ZIP-only row only when it's the *sole* representative of that
    # ZIP — i.e. it is genuinely filling a coverage gap, not doubling up.
    zips_with_address: set[str] = {
        r["zip_code"] for r in rows if r.get("address")
    }
    before_pass5 = len(rows)
    rows = [
        r for r in rows
        if r.get("address") or r["zip_code"] not in zips_with_address
    ]
    dropped_pass5 = before_pass5 - len(rows)
    if dropped_pass5:
        logger.info(
            f"[OSM] '{retailer.retailer_key}' pass5: dropped {dropped_pass5} "
            f"ZIP-only phantom rows (ZIP already covered by addressed entry)"
        )

    # Pass 6 — intra-batch ZIP dedup: keep only one row per zip_code.
    # ON CONFLICT DO UPDATE fails at the Postgres level if two rows in the
    # same upsert batch share the same conflict key (retailer_key, zip_code).
    # This happens in dense markets where two stores of the same chain operate
    # in the same ZIP (e.g. two Whole Foods in ZIP 10001). Both survive coord
    # dedup (they are >500 m apart) but the DB only stores one per ZIP.
    # Preference: keep the row with a full address; if tied, keep last seen.
    seen_zips: dict[str, dict] = {}
    for r in rows:
        existing = seen_zips.get(r["zip_code"])
        if existing is None:
            seen_zips[r["zip_code"]] = r
        elif not existing.get("address") and r.get("address"):
            # Upgrade to the addressed version
            seen_zips[r["zip_code"]] = r
    rows = list(seen_zips.values())
    dropped_pass6 = before_pass5 - dropped_pass5 - len(rows)
    if dropped_pass6:
        logger.info(
            f"[OSM] '{retailer.retailer_key}' pass6: dropped {dropped_pass6} "
            f"intra-batch ZIP duplicates (kept one row per ZIP)"
        )

    stats["valid"] = len(rows)

    logger.info(
        f"[OSM] '{retailer.retailer_key}': {stats['fetched']} elements → "
        f"{stats['valid']} valid (dropped {stats['fetched'] - stats['valid']} without ZIP/coords)"
    )

    for i in range(0, len(rows), UPSERT_BATCH):
        ins, skp = _upsert_batch(rows[i : i + UPSERT_BATCH], dry_run)
        stats["upserted"] += ins
        stats["skipped"]  += skp

    return stats


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Import store locations from OpenStreetMap")
    parser.add_argument(
        "--retailer", default=None,
        help=f"One retailer_key to import. Available: {', '.join(RETAILER_MAP)}",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Print rows without writing to DB",
    )
    args = parser.parse_args()

    if args.retailer:
        if args.retailer not in RETAILER_MAP:
            logger.error(
                f"Unknown retailer '{args.retailer}'. "
                f"Available: {', '.join(RETAILER_MAP)}"
            )
            return
        targets = [RETAILER_MAP[args.retailer]]
    else:
        targets = RETAILERS

    total = {"fetched": 0, "valid": 0, "upserted": 0, "skipped": 0}

    for i, retailer in enumerate(targets):
        stats = import_retailer(retailer, args.dry_run)
        for k in total:
            total[k] += stats[k]
        logger.info(f"[OSM] '{retailer.retailer_key}' done: {stats}")
        if i < len(targets) - 1:
            logger.info(f"[OSM] Waiting {REQUEST_DELAY}s before next retailer ...")
            time.sleep(REQUEST_DELAY)

    logger.info(f"[OSM] All done: {total}")


if __name__ == "__main__":
    main()
