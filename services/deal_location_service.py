# services/deal_location_service.py
#
# Query-time layer — enriches deals with store data and distance.
#
# zip_multi re-resolution rule:
#   match_confidence == 'zip_multi' AND user_lat/user_lng provided
#     → pick closest store from candidate_store_ids
#   Otherwise fall back to stored store_id silently.

import math
import logging
from config.supabase import get_supabase_client
from services.store_distance import get_nearby_stores

logger   = logging.getLogger(__name__)
supabase = get_supabase_client()

_store_cache: dict[str, dict] = {}


def _haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R  = 3958.8
    p1 = math.radians(lat1)
    p2 = math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a  = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _fetch_store(store_id: str) -> dict | None:
    if store_id in _store_cache:
        return _store_cache[store_id]
    res = (
        supabase.table("store_locations")
        .select("id, retailer_key, store_name, address, city, state, zip_code, latitude, longitude")
        .eq("id", store_id)
        .single()
        .execute()
    )
    if res.data:
        _store_cache[store_id] = res.data
        return res.data
    return None


def _fetch_stores_bulk(store_ids: list[str]) -> dict[str, dict]:
    missing = [sid for sid in store_ids if sid not in _store_cache]
    if missing:
        res = (
            supabase.table("store_locations")
            .select("id, retailer_key, store_name, address, city, state, zip_code, latitude, longitude")
            .in_("id", missing)
            .execute()
        )
        for row in res.data or []:
            _store_cache[row["id"]] = row
    return {sid: _store_cache[sid] for sid in store_ids if sid in _store_cache}


def _resolve_store(
    deal:       dict,
    user_lat:   float | None,
    user_lng:   float | None,
    nearby_map: dict[str, dict],
) -> dict | None:
    confidence    = deal.get("match_confidence")
    candidate_ids = deal.get("candidate_store_ids") or []
    assigned_id   = deal.get("store_id")

    # zip_multi + user coords → re-resolve from candidate_store_ids
    if (
        confidence == "zip_multi"
        and candidate_ids
        and user_lat is not None
        and user_lng is not None
    ):
        candidate_stores = _fetch_stores_bulk(candidate_ids)
        best_store = None
        best_dist  = float("inf")

        for store in candidate_stores.values():
            lat = store.get("latitude")
            lng = store.get("longitude")
            if lat is None or lng is None:
                continue
            dist = _haversine(user_lat, user_lng, lat, lng)
            if dist < best_dist:
                best_dist  = dist
                best_store = store

        if best_store:
            return {
                **best_store,
                "distance_miles":    round(best_dist, 2),
                "resolved_at_query": True,
            }

    # Fallback: hard-assigned store_id
    if not assigned_id:
        return None

    if assigned_id in nearby_map:
        s = nearby_map[assigned_id]
        return {
            "id":                assigned_id,
            "retailer_key":      s.get("retailer_key"),
            "store_name":        s.get("store_name"),
            "address":           s.get("address"),
            "city":              s.get("city"),
            "state":             s.get("state"),
            "zip_code":          s.get("zip_code"),
            "latitude":          s.get("latitude"),
            "longitude":         s.get("longitude"),
            "distance_miles":    s.get("distance_miles"),
            "resolved_at_query": False,
        }

    store = _fetch_store(assigned_id)
    if store:
        dist = None
        if user_lat and user_lng and store.get("latitude") and store.get("longitude"):
            dist = round(
                _haversine(user_lat, user_lng, store["latitude"], store["longitude"]), 2
            )
        return {**store, "distance_miles": dist, "resolved_at_query": False}

    return None


def get_deals_near_zip(
    zip_code:     str,
    radius_miles: float        = 10.0,
    retailer_key: str | None   = None,
    category:     str | None   = None,
    limit:        int          = 100,
    user_lat:     float | None = None,
    user_lng:     float | None = None,
) -> list[dict]:
    """
    Active deals within radius_miles of zip_code.
    Pass user_lat + user_lng for zip_multi re-resolution to nearest store.
    """
    nearby = get_nearby_stores(zip_code, radius_miles, retailer_key)
    if not nearby:
        return []

    nearby_map = {s["store_id"]: s for s in nearby}

    q = (
        supabase.table("flyer_deals")
        .select(
            "id, product_name, product_price, category, image_link, "
            "retailer_key, retailer, match_key, canonical_product_name, "
            "coupon_detail, display_size, brand, "
            "store_id, match_confidence, candidate_store_count, matched_by, "
            "candidate_store_ids"
        )
        .in_("store_id", list(nearby_map.keys()))
        .not_.is_("product_price", "null")
        .order("product_price", desc=False)
        .limit(limit)
    )
    if category:
        q = q.eq("category", category)

    deals    = q.execute().data or []
    enriched = []

    for deal in deals:
        store = _resolve_store(deal, user_lat, user_lng, nearby_map)
        if not store:
            continue
        enriched.append({
            **deal,
            "store_name":        store.get("store_name"),
            "store_address":     store.get("address"),
            "city":              store.get("city"),
            "state":             store.get("state"),
            "latitude":          store.get("latitude"),
            "longitude":         store.get("longitude"),
            "distance_miles":    store.get("distance_miles"),
            "resolved_at_query": store.get("resolved_at_query", False),
        })

    enriched.sort(
        key=lambda d: (d.get("distance_miles") or 999, -(d.get("discount_pct") or 0))
    )
    return enriched


def get_map_pins_near_zip(
    zip_code:     str,
    radius_miles: float        = 10.0,
    user_lat:     float | None = None,
    user_lng:     float | None = None,
) -> list[dict]:
    """One map pin per resolved store with deal count and best deal price."""
    deals = get_deals_near_zip(zip_code, radius_miles, user_lat=user_lat, user_lng=user_lng)
    pins: dict[str, dict] = {}

    for deal in deals:
        pin_key = f"{deal.get('latitude')}|{deal.get('longitude')}"
        if pin_key not in pins:
            pins[pin_key] = {
                "store_id":       deal["store_id"],
                "retailer_key":   deal["retailer_key"],
                "store_name":     deal.get("store_name"),
                "address":        deal.get("store_address"),
                "city":           deal.get("city"),
                "state":          deal.get("state"),
                "latitude":       deal.get("latitude"),
                "longitude":      deal.get("longitude"),
                "distance_miles": deal.get("distance_miles"),
                "deal_count":     0,
                "best_price":     None,
                "best_product":   None,
            }
        pins[pin_key]["deal_count"] += 1
        p = deal.get("product_price")
        if p is not None and (
            pins[pin_key]["best_price"] is None or p < pins[pin_key]["best_price"]
        ):
            pins[pin_key]["best_price"]   = p
            pins[pin_key]["best_product"] = deal["product_name"]

    return sorted(pins.values(), key=lambda p: p.get("distance_miles") or 999)


def get_cart_optimizer_stores(
    zip_code:      str,
    product_names: list[str],
    radius_miles:  float        = 10.0,
    user_lat:      float | None = None,
    user_lng:      float | None = None,
) -> list[dict]:
    """Rank stores by total cart price + small distance penalty."""
    deals = get_deals_near_zip(zip_code, radius_miles, user_lat=user_lat, user_lng=user_lng)
    carts: dict[str, dict] = {}

    for deal in deals:
        name = (deal.get("product_name") or "").lower()
        if not any(p.lower() in name for p in product_names):
            continue

        pin_key = f"{deal.get('latitude')}|{deal.get('longitude')}"
        if pin_key not in carts:
            carts[pin_key] = {
                "store_id":       deal["store_id"],
                "retailer_key":   deal["retailer_key"],
                "store_name":     deal.get("store_name"),
                "address":        deal.get("store_address"),
                "city":           deal.get("city"),
                "state":          deal.get("state"),
                "latitude":       deal.get("latitude"),
                "longitude":      deal.get("longitude"),
                "distance_miles": deal.get("distance_miles") or 0,
                "items":          [],
                "total_price":    0.0,
            }
        carts[pin_key]["items"].append({
            "product": deal["product_name"],
            "price":   deal.get("product_price"),
        })
        carts[pin_key]["total_price"] += deal.get("product_price") or 0

    for c in carts.values():
        c["items_found"] = len(c["items"])
        c["score"]       = c["total_price"] + c["distance_miles"] * 0.10

    return sorted(carts.values(), key=lambda c: c["score"])