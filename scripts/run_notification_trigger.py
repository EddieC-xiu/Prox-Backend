# scripts/run_notification_trigger.py
#
# Phase 4 — Notification Trigger Job
#
# Runs after deal_delta batch. For each price drop or new deal,
# evaluates all waitlist users and fires notifications where appropriate.
#
# Now reads user preferences (zip, radius, segment, category_prefs) from
# user_preferences table. Falls back to waitlist zip if no preferences exist.
#
# Optimized: all data loaded in batch upfront — minimal API calls during main loop.
#
# Usage:
#   PYTHONUTF8=1 PYTHONPATH=. python scripts/run_notification_trigger.py
#   PYTHONUTF8=1 PYTHONPATH=. python scripts/run_notification_trigger.py --dry-run
#   PYTHONUTF8=1 PYTHONPATH=. python scripts/run_notification_trigger.py --dry-run --trigger-types unchanged

import math
import logging
import argparse
from collections import defaultdict
from config.supabase import get_supabase_client
from services.notification_scorer import should_notify, log_notification, preload_notification_log
from services.notification_sender import send_notification, preload_notification_devices

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)

sb = get_supabase_client()

SEGMENT_THRESHOLDS = {
    "deal_hunter": 45.0,
    "casual":      55.0,
    "passive":     70.0,
}

SEGMENT_DAILY_CAPS = {
    "deal_hunter": 5,
    "casual":      3,
    "passive":     1,
}


def _haversine_miles(lat1, lon1, lat2, lon2):
    R = 3958.8
    lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
    return R * 2 * math.asin(math.sqrt(a))


def load_zip_cache(zip_codes: set) -> dict:
    if not zip_codes:
        return {}
    try:
        res = (
            sb.table("zip_centroids")
            .select("zip_code, latitude, longitude")
            .in_("zip_code", list(zip_codes))
            .execute()
        )
        cache = {r["zip_code"]: (float(r["latitude"]), float(r["longitude"])) for r in (res.data or [])}
        logger.info(f"Loaded {len(cache)}/{len(zip_codes)} zip centroids into cache")
        return cache
    except Exception as e:
        logger.error(f"Failed to load zip cache: {e}")
        return {}


def _is_within_radius(user_zip, deal_zip, radius_miles, zip_cache):
    if not user_zip or not deal_zip:
        return True
    u = zip_cache.get(user_zip)
    d = zip_cache.get(deal_zip)
    if not u or not d:
        return True
    return _haversine_miles(u[0], u[1], d[0], d[1]) <= radius_miles


def get_trigger_deals(trigger_types=["drop", "new"]) -> list:
    try:
        res = (
            sb.table("deal_delta")
            .select("match_key, store_id, current_price, baseline_price, price_change_pct, delta_type")
            .in_("delta_type", trigger_types)
            .execute()
        )
        deltas = res.data or []
        if not deltas:
            return []

        match_keys = list(set(d["match_key"] for d in deltas))
        ph_res = (
            sb.table("price_history")
            .select("match_key, brand, canonical_product_name, size_oz")
            .in_("match_key", match_keys)
            .execute()
        )
        ph_by_key = {}
        for row in (ph_res.data or []):
            if row["match_key"] not in ph_by_key:
                ph_by_key[row["match_key"]] = row

        store_ids = list(set(str(d["store_id"]) for d in deltas if d.get("store_id")))
        sl_res = (
            sb.table("store_locations")
            .select("id, retailer, retailer_key, zip_code")
            .in_("id", store_ids)
            .execute()
        )
        sl_by_id = {str(r["id"]): r for r in (sl_res.data or [])}

        logger.info(f"Batch loaded {len(ph_by_key)} price_history, {len(sl_by_id)} store_locations")

        results = []
        for delta in deltas:
            ph = ph_by_key.get(delta["match_key"])
            if not ph:
                continue
            sl = sl_by_id.get(str(delta.get("store_id") or ""), {})
            results.append({
                "canonical_product_name": ph["canonical_product_name"],
                "brand":                  ph.get("brand"),
                "retailer":               sl.get("retailer"),
                "retailer_key":           sl.get("retailer_key"),
                "zip_code":               sl.get("zip_code") or "",
                "current_price":          delta["current_price"],
                "previous_price":         delta["baseline_price"],
                "delta_type":             delta["delta_type"],
                "delta_pct":              delta.get("price_change_pct"),
            })
        return results

    except Exception as e:
        logger.error(f"Failed to fetch trigger deals: {e}")
        return []


def preload_deal_details(deals: list) -> dict:
    if not deals:
        return {}

    unique_products = list(set(d["canonical_product_name"] for d in deals if d.get("canonical_product_name")))
    logger.info(f"Preloading deal details for {len(unique_products)} unique products...")

    try:
        rows_res = (
            sb.table("flyer_deals")
            .select("canonical_product_name, retailer, zip_code, product_price, category")
            .in_("canonical_product_name", unique_products)
            .not_.is_("product_price", "null")
            .execute()
        )
        all_rows = rows_res.data or []
    except Exception as e:
        logger.error(f"Failed to preload deal details: {e}")
        return {}

    by_product: dict = defaultdict(list)
    for row in all_rows:
        by_product[row["canonical_product_name"]].append(row)

    detail_cache = {}
    for deal in deals:
        product  = deal.get("canonical_product_name")
        retailer = deal.get("retailer")
        zip_code = deal.get("zip_code") or ""
        if not product or not retailer:
            continue

        key = (product, retailer, zip_code)
        if key in detail_cache:
            continue

        product_rows = by_product.get(product, [])
        if not product_rows:
            continue

        # Normalize retailer name — store_locations may have "walmart supercenter"
        # while flyer_deals has "walmart" or "Walmart"
        from services.cross_retailer_service import normalize_retailer, RETAILER_ALIASES
        retailer_normalized = normalize_retailer(retailer)

        # Also build a set of all lowercase variants to match against
        retailer_variants = {
            retailer.lower(),
            retailer_normalized.lower(),
            retailer.lower().replace(" supercenter", "").replace(" neighborhood market", "").replace(" express", ""),
        }

        # Category — try normalized retailer match first, fall back to any row with category
        category = None
        for row in product_rows:
            row_retailer = normalize_retailer(row["retailer"]).lower()
            if row_retailer in retailer_variants:
                category = row.get("category")
                break
        if not category:
            for row in product_rows:
                if row.get("category"):
                    category = row["category"]
                    break

        # Avg price and retailer count — exclude $0 prices and outliers
        prices    = [float(r["product_price"]) for r in product_rows if float(r["product_price"]) > 0]
        # Filter outliers — exclude prices > 3x median (catches bulk/case prices like $48)
        if len(prices) >= 3:
            import statistics
            med    = statistics.median(prices)
            prices = [p for p in prices if p <= med * 3]
        avg_price = sum(prices) / len(prices) if prices else 0
        retailers = len(set(normalize_retailer(r["retailer"]) for r in product_rows if float(r["product_price"]) > 0))

        # Best price for this retailer — match by normalized name variants
        retailer_prices = [
            float(r["product_price"]) for r in product_rows
            if normalize_retailer(r["retailer"]).lower() in retailer_variants
            and float(r["product_price"]) > 0
        ]
        best_price  = min(retailer_prices) if retailer_prices else 0
        savings_pct = round(((avg_price - best_price) / avg_price) * 100, 1) if avg_price else 0

        # Skip if no valid price, no savings, or only one retailer
        if best_price <= 0 or savings_pct <= 0 or retailers < 2:
            continue

        detail_cache[key] = {
            "category":       category,
            "retailer_count": retailers,
            "savings_pct":    savings_pct,
            "avg_price":      avg_price,
            "best_price":     best_price,
        }

    logger.info(f"Preloaded details for {len(detail_cache)} deal+retailer combinations")
    return detail_cache


def get_waitlist_users() -> list:
    try:
        waitlist = (
            sb.table("waitlist")
            .select("id, zip_code, email, preferred_brands")
            .not_.is_("zip_code", "null")
            .execute()
            .data or []
        )
        prefs_by_user = {
            r["user_id"]: r for r in (
                sb.table("user_preferences")
                .select("user_id, zip_code, radius_miles, segment, category_prefs, retailer_prefs, quiet_start, quiet_end")
                .execute()
                .data or []
            )
        }
        users = []
        for u in waitlist:
            uid   = str(u["id"])
            prefs = prefs_by_user.get(uid, {})
            default_categories = ["MEAT", "DAIRY_EGGS", "BEVERAGES", "PANTRY", "SNACKS", "FROZEN", "PRODUCE", "BAKERY", "DELI_PREPARED"]
            users.append({
                "id":               uid,
                "email":            u.get("email"),
                "zip_code":         prefs.get("zip_code") or u.get("zip_code") or "",
                "radius_miles":     float(prefs.get("radius_miles") or 25.0),
                "segment":          prefs.get("segment") or "casual",
                "category_prefs":   prefs.get("category_prefs") or default_categories,
                "retailer_prefs":   prefs.get("retailer_prefs") or [],
                "preferred_brands": u.get("preferred_brands") or [],
                "quiet_start":      int(prefs.get("quiet_start") or 22),
                "quiet_end":        int(prefs.get("quiet_end") or 7),
                "has_preferences":  uid in prefs_by_user,
            })
        return users
    except Exception as e:
        logger.error(f"Failed to fetch users: {e}")
        return []


def build_deal_reason(product, retailer, best_price, savings_pct, retailer_count, trigger_type, delta_pct):
    if trigger_type == "drop" and delta_pct:
        return (
            f"{retailer} dropped the price on {product} by {abs(float(delta_pct)):.1f}% "
            f"to ${best_price:.2f} — {savings_pct:.0f}% below average across {retailer_count} retailers"
        )
    elif savings_pct >= 15:
        return (
            f"{retailer} has {product} for ${best_price:.2f} — "
            f"{savings_pct:.0f}% below average across {retailer_count} retailers"
        )
    else:
        return (
            f"{retailer} has {product} for ${best_price:.2f} — "
            f"available at {retailer_count} retailers near you"
        )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--trigger-types", nargs="+", default=["drop", "new"])
    args = parser.parse_args()

    if args.dry_run:
        print("[DRY RUN] Nothing will be sent or logged.\n")

    trigger_deals = get_trigger_deals(args.trigger_types)
    logger.info(f"Found {len(trigger_deals)} trigger deals ({', '.join(args.trigger_types)})")

    users = get_waitlist_users()
    logger.info(f"Evaluating {len(users)} waitlist users")
    logger.info(f"  {sum(1 for u in users if u['has_preferences'])} with custom prefs, "
                f"{sum(1 for u in users if not u['has_preferences'])} using defaults")

    all_zips = set()
    for u in users:
        if u.get("zip_code"):
            all_zips.add(u["zip_code"])
    for d in trigger_deals:
        if d.get("zip_code"):
            all_zips.add(d["zip_code"])
    zip_cache = load_zip_cache(all_zips)

    user_ids          = [u["id"] for u in users]
    notif_log_cache   = preload_notification_log(user_ids)
    device_cache      = preload_notification_devices(user_ids)

    logger.info(f"  {len(device_cache)} users have active notification devices")

    deal_details_cache = preload_deal_details(trigger_deals)

    total_sent = total_blocked = total_distance_filtered = 0
    block_reasons: dict = {}

    for deal in trigger_deals:
        product      = deal["canonical_product_name"]
        retailer     = deal["retailer"]
        retailer_key = deal.get("retailer_key")
        deal_zip     = deal.get("zip_code") or ""
        delta_type   = deal["delta_type"]
        delta_pct    = deal.get("delta_pct")

        details = deal_details_cache.get((product, retailer, deal_zip))
        if not details:
            continue

        deal_reason = build_deal_reason(
            product, retailer, details["best_price"], details["savings_pct"],
            details["retailer_count"], delta_type, delta_pct,
        )

        for user in users:
            user_id          = user["id"]
            user_zip         = user["zip_code"]
            radius_miles     = user["radius_miles"]
            segment          = user["segment"]
            category_prefs   = user["category_prefs"]
            preferred_brands = user.get("preferred_brands") or []

            if user_zip and deal_zip:
                if not _is_within_radius(user_zip, deal_zip, radius_miles, zip_cache):
                    total_distance_filtered += 1
                    continue

            threshold = SEGMENT_THRESHOLDS.get(segment, 55.0)

            result = should_notify(
                user_id            = user_id,
                product            = product,
                retailer           = retailer,
                retailer_key       = retailer_key,
                zip_code           = deal_zip,
                price              = details["best_price"],
                deal_category      = details["category"],
                savings_pct_vs_avg = details["savings_pct"],
                retailer_count     = details["retailer_count"],
                has_price_drop     = delta_type == "drop",
                price_drop_pct     = abs(float(delta_pct)) if delta_pct else 0.0,
                user_categories    = category_prefs,
                user_history       = [],
                deal_reason        = deal_reason,
                trigger_type       = delta_type,
                log_cache          = notif_log_cache,
                deal_brand         = deal.get("brand"),
                preferred_brands   = preferred_brands,
            )

            if result["notification_score"] < threshold:
                result["should_send"]    = False
                result["blocked_reason"] = f"score {result['notification_score']} below {segment} threshold {threshold}"

            if result["should_send"]:
                if args.dry_run:
                    print(
                        f"  [WOULD SEND] {user_id[:8]}... ({segment}) → {product} @ {retailer} "
                        f"(score: {result['notification_score']}, zip: {user_zip}) — {deal_reason}"
                    )
                    total_sent += 1
                else:
                    # Check if user has a registered device
                    device = device_cache.get(user_id)
                    if device:
                        send_result = send_notification(
                            subscription_id = device["provider_subscription_id"],
                            product         = product,
                            retailer        = retailer,
                            best_price      = details["best_price"],
                            savings_pct     = details["savings_pct"],
                            deal_reason     = deal_reason,
                            trigger_type    = delta_type,
                        )
                        if not send_result.get("success"):
                            logger.error(f"Failed to send to {user_id[:8]}: {send_result.get('error')}")
                            total_blocked += 1
                            block_reasons["onesignal_send_failed"] = block_reasons.get("onesignal_send_failed", 0) + 1
                            continue

                    log_notification(
                        user_id            = user_id,
                        product            = product,
                        retailer           = retailer,
                        retailer_key       = retailer_key,
                        zip_code           = deal_zip,
                        price              = details["best_price"],
                        deal_score         = result["deal_score"],
                        relevance_score    = result["relevance_score"],
                        notification_score = result["notification_score"],
                        deal_reason        = deal_reason,
                        trigger_type       = delta_type,
                    )
                    total_sent += 1
            else:
                total_blocked += 1
                reason = result.get("blocked_reason") or "unknown"
                block_reasons[reason] = block_reasons.get(reason, 0) + 1

    print(f"\n── Notification Trigger Summary ──────────────────────────")
    print(f"  Trigger deals evaluated  : {len(trigger_deals)}")
    print(f"  Users evaluated          : {len(users)}")
    print(f"  Distance filtered        : {total_distance_filtered}")
    print(f"  Notifications sent       : {total_sent}")
    print(f"  Notifications blocked    : {total_blocked}")
    if block_reasons:
        print(f"  Block reasons:")
        for reason, count in sorted(block_reasons.items(), key=lambda x: -x[1]):
            print(f"    {reason}: {count}")
    print()


if __name__ == "__main__":
    main()