# scripts/run_weekly_digest.py
#
# Phase 4 — Weekly Savings Digest
#
# Runs every Sunday morning. For each user, finds their top 3 deals
# based on location, category preferences, and preferred brands.
# Sends a personalized weekly briefing via OneSignal.
#
# Replaces Tom's placeholder weekly digest with real data-driven copy.
#
# Usage:
#   PYTHONUTF8=1 PYTHONPATH=. python scripts/run_weekly_digest.py --dry-run
#   PYTHONUTF8=1 PYTHONPATH=. python scripts/run_weekly_digest.py

import os
import math
import logging
import argparse
import requests
import statistics
from collections import defaultdict
from config.supabase import get_supabase_client
from services.notification_scorer import compute_deal_score, compute_relevance_score, compute_notification_score

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)

sb                = get_supabase_client()
ONESIGNAL_APP_ID  = os.environ.get("ONESIGNAL_APP_ID", "")
ONESIGNAL_API_KEY = os.environ.get("ONESIGNAL_API_KEY", "")
ONESIGNAL_API_URL = "https://api.onesignal.com/notifications"

TOP_DEALS_PER_USER  = 3
MIN_SCORE_THRESHOLD = 30.0   # lower than daily alerts — weekly digest is broader


# ---------------------------------------------------------------------------
# Haversine
# ---------------------------------------------------------------------------

def _haversine_miles(lat1, lon1, lat2, lon2):
    R = 3958.8
    lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = math.sin(dlat/2)**2 + math.cos(lat1)*math.cos(lat2)*math.sin(dlon/2)**2
    return R * 2 * math.asin(math.sqrt(a))


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

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
        return {r["zip_code"]: (float(r["latitude"]), float(r["longitude"])) for r in (res.data or [])}
    except Exception as e:
        logger.error(f"Failed to load zip cache: {e}")
        return {}


def load_users() -> list[dict]:
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
                .select("user_id, zip_code, radius_miles, segment, category_prefs")
                .execute()
                .data or []
            )
        }
        default_categories = ["MEAT", "DAIRY_EGGS", "BEVERAGES", "PANTRY", "SNACKS", "FROZEN", "PRODUCE", "BAKERY"]
        users = []
        for u in waitlist:
            uid   = str(u["id"])
            prefs = prefs_by_user.get(uid, {})
            users.append({
                "id":               uid,
                "zip_code":         prefs.get("zip_code") or u.get("zip_code") or "",
                "radius_miles":     float(prefs.get("radius_miles") or 25.0),
                "segment":          prefs.get("segment") or "casual",
                "category_prefs":   prefs.get("category_prefs") or default_categories,
                "preferred_brands": u.get("preferred_brands") or [],
            })
        return users
    except Exception as e:
        logger.error(f"Failed to load users: {e}")
        return []


def load_products() -> list[dict]:
    """Load all products with 2+ retailers in batches."""
    logger.info("Loading products...")
    all_rows = []
    offset   = 0
    while True:
        batch = (
            sb.table("flyer_deals")
            .select("canonical_product_name, brand, product_price, retailer, zip_code, category")
            .not_.is_("product_price", "null")
            .not_.is_("canonical_product_name", "null")
            .range(offset, offset + 999)
            .execute()
            .data or []
        )
        all_rows.extend(batch)
        if len(batch) < 1000:
            break
        offset += 1000

    by_product: dict = defaultdict(list)
    for row in all_rows:
        name  = row.get("canonical_product_name") or ""
        price = float(row.get("product_price") or 0)
        if len(name) > 80 or price <= 0:
            continue
        by_product[name].append(row)

    products = []
    for name, rows in by_product.items():
        retailers = set(r["retailer"] for r in rows if float(r["product_price"]) > 0)
        if len(retailers) < 2:
            continue
        prices    = [float(r["product_price"]) for r in rows if float(r["product_price"]) > 0]
        avg_price = sum(prices) / len(prices) if prices else 0
        best_row  = min(rows, key=lambda r: float(r["product_price"]))
        best_price  = float(best_row["product_price"])
        if best_price <= 0:
            continue
        savings_pct = round(((avg_price - best_price) / avg_price) * 100, 1) if avg_price else 0
        if savings_pct <= 0:
            continue
        category = next((r.get("category") for r in rows if r.get("category")), None)

        products.append({
            "name":           name,
            "brand":          (best_row.get("brand") or "").lower().strip() or None,
            "category":       category,
            "retailer":       best_row.get("retailer") or "",
            "zip_code":       best_row.get("zip_code") or "",
            "best_price":     best_price,
            "avg_price":      avg_price,
            "savings_pct":    savings_pct,
            "savings_abs":    round(avg_price - best_price, 2),
            "retailer_count": len(retailers),
        })

    logger.info(f"Loaded {len(products)} products with 2+ retailers and positive savings")
    return products


def load_weekly_devices(user_ids: list[str]) -> dict[str, str]:
    """Load subscription IDs for users with weekly_summary_enabled = true."""
    if not user_ids:
        return {}
    try:
        res = (
            sb.table("notification_devices")
            .select("user_id, provider_subscription_id")
            .in_("user_id", user_ids)
            .eq("active", True)
            .eq("weekly_summary_enabled", True)
            .not_.is_("provider_subscription_id", "null")
            .execute()
        )
        return {str(r["user_id"]): r["provider_subscription_id"] for r in (res.data or [])}
    except Exception as e:
        logger.error(f"Failed to load weekly devices: {e}")
        return {}


# ---------------------------------------------------------------------------
# Scoring + top deals per user
# ---------------------------------------------------------------------------

def get_top_deals_for_user(
    user:      dict,
    products:  list[dict],
    zip_cache: dict,
) -> list[dict]:
    user_zip     = user["zip_code"]
    radius_miles = user["radius_miles"]
    u_latlon     = zip_cache.get(user_zip)

    scored = []
    for product in products:
        deal_zip = product["zip_code"]

        # Distance gate
        if u_latlon and deal_zip:
            d_latlon = zip_cache.get(deal_zip)
            if d_latlon:
                dist = _haversine_miles(u_latlon[0], u_latlon[1], d_latlon[0], d_latlon[1])
                if dist > radius_miles:
                    continue

        # Deprioritize produce in weekly digest — volatile pricing misleads users
        produce_penalty = 0.7 if product.get("category") in ("PRODUCE", "MEAT") else 1.0
        deal_score = compute_deal_score(
            savings_pct_vs_avg = product["savings_pct"] * produce_penalty,
            retailer_count     = product["retailer_count"],
            has_price_drop     = False,
            price_drop_pct     = 0.0,
        )
        relevance_score = compute_relevance_score(
            deal_category    = product["category"],
            user_categories  = user["category_prefs"],
            deal_product     = product["name"],
            user_history     = [],
            deal_brand       = product["brand"],
            preferred_brands = user["preferred_brands"],
        )
        notif_score = compute_notification_score(deal_score, relevance_score)

        if notif_score >= MIN_SCORE_THRESHOLD:
            scored.append({**product, "score": notif_score})

    # Sort by score, deduplicate by retailer (don't send 3 Walmart deals)
    scored.sort(key=lambda x: -x["score"])
    seen_retailers = set()
    top_deals      = []
    for deal in scored:
        if deal["retailer"] not in seen_retailers:
            seen_retailers.add(deal["retailer"])
            top_deals.append(deal)
        if len(top_deals) >= TOP_DEALS_PER_USER:
            break

    return top_deals


# ---------------------------------------------------------------------------
# Payload builder
# ---------------------------------------------------------------------------

def build_digest_payload(subscription_id: str, top_deals: list[dict]) -> dict:
    """
    Build weekly digest payload matching Tom's format.
    Title: "Your Weekly Savings Briefing"
    Body: personalized deal copy with total savings estimate
    """
    total_savings = sum(d["savings_abs"] for d in top_deals)

    # Build body — first deal prominent, rest as "and more"
    if len(top_deals) == 0:
        body = "Check out this week's top deals near you."
    elif len(top_deals) == 1:
        d    = top_deals[0]
        body = (
            f"Your top deal this week: {d['name'].title()} at {d['retailer'].title()} "
            f"for ${d['best_price']:.2f} — {d['savings_pct']:.0f}% below average."
        )
    else:
        d1 = top_deals[0]
        d2 = top_deals[1]
        body = (
            f"This week's top deals could save you ${total_savings:.0f}. "
            f"{d1['name'].title()} ${d1['best_price']:.2f} at {d1['retailer'].title()}, "
            f"{d2['name'].title()} ${d2['best_price']:.2f} at {d2['retailer'].title()}"
        )
        if len(top_deals) >= 3:
            d3   = top_deals[2]
            body += f", and {d3['name'].title()} ${d3['best_price']:.2f} at {d3['retailer'].title()}."
        else:
            body += "."

    return {
        "app_id":                   ONESIGNAL_APP_ID,
        "include_subscription_ids": [subscription_id],
        "headings":                 {"en": "Your Weekly Savings Briefing"},
        "contents":                 {"en": body},
        "data": {
            "deep_link": "/deals?source=weekly-digest",
        },
        "ios_sound":     "default",
        "android_sound": "default",
    }


def send_digest(subscription_id: str, payload: dict, dry_run: bool = False) -> bool:
    if dry_run:
        return True
    if not ONESIGNAL_APP_ID or not ONESIGNAL_API_KEY:
        logger.warning("OneSignal credentials not set")
        return False
    try:
        res = requests.post(
            ONESIGNAL_API_URL,
            headers={"Authorization": f"Key {ONESIGNAL_API_KEY}", "Content-Type": "application/json"},
            json=payload,
            timeout=10,
        )
        data = res.json()
        if res.status_code == 200 and data.get("id"):
            return True
        logger.error(f"OneSignal error: {data}")
        return False
    except Exception as e:
        logger.error(f"Send failed: {e}")
        return False


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if args.dry_run:
        print("[DRY RUN] Nothing will be sent.\n")

    users    = load_users()
    products = load_products()
    logger.info(f"Evaluating {len(users)} users against {len(products)} products")

    all_zips = set()
    for u in users:
        if u.get("zip_code"):
            all_zips.add(u["zip_code"])
    for p in products:
        if p.get("zip_code"):
            all_zips.add(p["zip_code"])
    zip_cache = load_zip_cache(all_zips)

    user_ids    = [u["id"] for u in users]
    device_map  = load_weekly_devices(user_ids)
    logger.info(f"  {len(device_map)} users have weekly digest enabled")

    total_sent    = 0
    total_skipped = 0

    print(f"\n── Weekly Digest Preview ─────────────────────────────\n")

    for user in users:
        uid       = user["id"]
        top_deals = get_top_deals_for_user(user, products, zip_cache)

        if not top_deals:
            total_skipped += 1
            continue

        payload = build_digest_payload(
            subscription_id = device_map.get(uid, "no_device"),
            top_deals       = top_deals,
        )

        title = payload["headings"]["en"]
        body  = payload["contents"]["en"]

        if args.dry_run:
            print(f"  [{uid[:8]}...] zip:{user['zip_code']}")
            print(f"  📱 {title}")
            print(f"     {body}")
            print(f"  Top deals:")
            for d in top_deals:
                print(f"    [{d['score']:.1f}] {d['name']} @ {d['retailer']} — ${d['best_price']:.2f} ({d['savings_pct']:.0f}% below avg)")
            print()

        sub_id = device_map.get(uid)
        if sub_id:
            success = send_digest(sub_id, payload, dry_run=args.dry_run)
            if success:
                total_sent += 1
        else:
            total_skipped += 1

    print(f"\n── Weekly Digest Summary ─────────────────────────────")
    print(f"  Users evaluated   : {len(users)}")
    print(f"  Digests sent      : {total_sent}")
    print(f"  Skipped (no deals or device): {total_skipped}")
    print()


if __name__ == "__main__":
    main()