# scripts/backtest_notifications.py
#
# Phase 4 — Notification Scoring Backtest
#
# Simulates price drops at various thresholds against current product data.
# Answers: "If prices dropped by X%, how many notifications would fire per user per day?"
#
# Usage:
#   PYTHONUTF8=1 PYTHONPATH=. python scripts/backtest_notifications.py
#   PYTHONUTF8=1 PYTHONPATH=. python scripts/backtest_notifications.py --drop-pcts 5 10 15 20 30
#   PYTHONUTF8=1 PYTHONPATH=. python scripts/backtest_notifications.py --segment deal_hunter

import math
import logging
import argparse
import statistics
from collections import defaultdict
from config.supabase import get_supabase_client
from services.notification_scorer import (
    compute_deal_score,
    compute_relevance_score,
    compute_notification_score,
)

logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)

sb = get_supabase_client()

SEGMENT_THRESHOLDS = {
    "deal_hunter": 55.0,
    "casual":      65.0,
    "passive":     80.0,
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
    a = math.sin(dlat/2)**2 + math.cos(lat1)*math.cos(lat2)*math.sin(dlon/2)**2
    return R * 2 * math.asin(math.sqrt(a))


def load_products() -> list[dict]:
    """
    Load products using per-product queries to get accurate retailer counts.
    Uses the same aggregation approach as the compare endpoint.
    """
    print("Loading products — fetching all rows in batches...")

    # Fetch all rows in batches to get full retailer coverage
    all_rows = []
    offset   = 0
    while True:
        batch = (
            sb.table("test_flyer_deals_duplicate")
            .select("canonical_product_name, product_price, retailer, zip_code, category")
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
        if offset % 10000 == 0:
            print(f"  Fetched {offset} rows...")

    print(f"  Total rows fetched: {len(all_rows)}")

    # Group by product
    by_product: dict = defaultdict(list)
    for row in all_rows:
        name  = row.get("canonical_product_name") or ""
        price = float(row.get("product_price") or 0)
        if len(name) > 80 or price <= 0:
            continue
        by_product[name].append(row)

    # Build product list — min 2 distinct retailers
    products = []
    for name, product_rows in by_product.items():
        retailers = set(r["retailer"] for r in product_rows)
        if len(retailers) < 2:
            continue
        prices    = [float(r["product_price"]) for r in product_rows]
        avg_price = sum(prices) / len(prices)
        category  = next((r.get("category") for r in product_rows if r.get("category")), None)
        best_row  = min(product_rows, key=lambda r: float(r["product_price"]))
        best_price  = float(best_row["product_price"])
        savings_pct = round(((avg_price - best_price) / avg_price) * 100, 1) if avg_price else 0

        products.append({
            "name":           name,
            "category":       category,
            "retailer":       best_row.get("retailer") or "",
            "zip_code":       best_row.get("zip_code") or "",
            "best_price":     best_price,
            "avg_price":      avg_price,
            "savings_pct":    savings_pct,
            "retailer_count": len(retailers),
        })

    print(f"Loaded {len(products)} products with 2+ retailers")
    return products


def load_users() -> list[dict]:
    """Load users with preferences."""
    waitlist = (
        sb.table("waitlist")
        .select("id, zip_code")
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
    users = []
    for u in waitlist:
        uid   = str(u["id"])
        prefs = prefs_by_user.get(uid, {})
        users.append({
            "id":             uid,
            "zip_code":       prefs.get("zip_code") or u.get("zip_code") or "",
            "radius_miles":   float(prefs.get("radius_miles") or 25.0),
            "segment":        prefs.get("segment") or "casual",
            "category_prefs": prefs.get("category_prefs") or [],
        })
    print(f"Loaded {len(users)} users")
    return users


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
    except Exception:
        return {}


def run_backtest(
    products:   list[dict],
    users:      list[dict],
    zip_cache:  dict,
    drop_pct:   float,
    segment:    str | None = None,
) -> dict:
    """
    Simulate a price drop of drop_pct% on all products.
    Returns stats on how many notifications would fire.
    """
    threshold = SEGMENT_THRESHOLDS.get(segment or "casual", 65.0)
    # For backtesting, also show what fires at threshold-10 to give weight tuning data
    test_threshold = threshold
    daily_cap = SEGMENT_DAILY_CAPS.get(segment or "casual", 3)

    # Filter users by segment if specified
    target_users = [u for u in users if u["segment"] == (segment or u["segment"])]

    total_would_fire  = 0
    notifs_per_user:  dict[str, int] = defaultdict(int)
    firing_products:  list[dict]     = []
    score_dist:       list[float]    = []

    for product in products:
        deal_zip      = product["zip_code"]
        retailer      = product["retailer"]
        category      = product["category"]
        savings_pct   = product["savings_pct"]
        retailer_count = product["retailer_count"]

        # Simulate the price drop — add drop_pct to existing savings
        simulated_savings = min(savings_pct + drop_pct, 100.0)

        deal_score = compute_deal_score(
            savings_pct_vs_avg = simulated_savings,
            retailer_count     = retailer_count,
            has_price_drop     = True,
            price_drop_pct     = drop_pct,
        )

        for user in target_users:
            user_zip     = user["zip_code"]
            radius_miles = user["radius_miles"]

            # Distance gate
            if user_zip and deal_zip:
                u_latlon = zip_cache.get(user_zip)
                d_latlon = zip_cache.get(deal_zip)
                if u_latlon and d_latlon:
                    dist = _haversine_miles(u_latlon[0], u_latlon[1], d_latlon[0], d_latlon[1])
                    if dist > radius_miles:
                        continue

            relevance_score = compute_relevance_score(
                deal_category   = category,
                user_categories = user["category_prefs"],
                deal_product    = product["name"],
                user_history    = [],
            )

            notif_score = compute_notification_score(deal_score, relevance_score)
            score_dist.append(notif_score)

            # Daily cap per user
            if notifs_per_user[user["id"]] >= daily_cap:
                continue

            if notif_score >= threshold:
                total_would_fire += 1
                notifs_per_user[user["id"]] += 1
                firing_products.append({
                    "product":    product["name"],
                    "retailer":   retailer,
                    "score":      notif_score,
                    "savings":    simulated_savings,
                    "category":   category,
                })

    # Stats
    users_notified    = sum(1 for v in notifs_per_user.values() if v > 0)
    avg_per_user      = round(total_would_fire / len(target_users), 2) if target_users else 0
    avg_notified_user = round(total_would_fire / users_notified, 2) if users_notified else 0

    # Deduplicate top products by product+retailer
    seen_products: set = set()
    top_products: list = []
    for p in sorted(firing_products, key=lambda x: -x["score"]):
        key = f"{p['product']}|{p['retailer']}"
        if key not in seen_products:
            seen_products.add(key)
            top_products.append(p)
        if len(top_products) >= 5:
            break

    # Count products that scored above threshold (before cap)
    above_threshold = len(seen_products)

    # Score distribution buckets
    score_buckets = {
        "0-30":  sum(1 for s in score_dist if s < 30),
        "30-50": sum(1 for s in score_dist if 30 <= s < 50),
        "50-65": sum(1 for s in score_dist if 50 <= s < 65),
        "65+":   sum(1 for s in score_dist if s >= 65),
    }

    return {
        "drop_pct":             drop_pct,
        "segment":              segment or "all",
        "threshold":            threshold,
        "users_evaluated":      len(target_users),
        "users_notified":       users_notified,
        "total_notifications":  total_would_fire,
        "above_threshold":      above_threshold,
        "avg_per_user":         avg_per_user,
        "avg_notified_user":    avg_notified_user,
        "median_score":         round(statistics.median(score_dist), 2) if score_dist else 0,
        "score_buckets":        score_buckets,
        "top_products":         top_products,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--drop-pcts", nargs="+", type=float, default=[5, 10, 15, 20, 30])
    parser.add_argument("--segment", choices=["deal_hunter", "casual", "passive"], default=None)
    args = parser.parse_args()

    products = load_products()
    users    = load_users()

    all_zips = set()
    for u in users:
        if u.get("zip_code"):
            all_zips.add(u["zip_code"])
    for p in products:
        if p.get("zip_code"):
            all_zips.add(p["zip_code"])
    zip_cache = load_zip_cache(all_zips)
    print(f"Loaded {len(zip_cache)} zip centroids\n")

    print("=" * 60)
    print(f"NOTIFICATION BACKTEST — Simulated Price Drops")
    print(f"Segment: {args.segment or 'all'}")
    print(f"Products: {len(products)}  |  Users: {len(users)}")
    print("=" * 60)

    results = []
    for drop_pct in args.drop_pcts:
        result = run_backtest(products, users, zip_cache, drop_pct, args.segment)
        results.append(result)

        print(f"\n── {drop_pct:.0f}% Price Drop Simulation ──────────────────")
        print(f"  Threshold         : {result['threshold']}")
        print(f"  Users evaluated   : {result['users_evaluated']}")
        print(f"  Users notified    : {result['users_notified']} ({round(result['users_notified']/result['users_evaluated']*100) if result['users_evaluated'] else 0}%)")
        print(f"  Total notifs      : {result['total_notifications']}")
        print(f"  Avg per user      : {result['avg_per_user']}/day")
        print(f"  Avg (notified)    : {result['avg_notified_user']}/day")
        print(f"  Median score      : {result['median_score']}")
        print(f"  Products above {result['threshold']:.0f} : {result['above_threshold']}")
        b = result["score_buckets"]
        print(f"  Score dist        : 0-30:{b['0-30']} | 30-50:{b['30-50']} | 50-65:{b['50-65']} | 65+:{b['65+']}")
        if result["top_products"]:
            print(f"  Top unique deals:")
            for p in result["top_products"]:
                print(f"    [{p['score']:.1f}] {p['product']} @ {p['retailer']} ({p['savings']:.0f}% below avg)")

    # Summary table
    print(f"\n{'='*60}")
    print(f"SUMMARY TABLE")
    print(f"{'Drop %':<10} {'Users Notified':<18} {'Total Notifs':<15} {'Avg/User':<12} {'Median Score'}")
    print(f"{'-'*60}")
    for r in results:
        pct_notified = round(r['users_notified']/r['users_evaluated']*100) if r['users_evaluated'] else 0
        print(f"{r['drop_pct']:<10.0f} {r['users_notified']:<6} ({pct_notified:>2}%)      {r['total_notifications']:<15} {r['avg_per_user']:<12} {r['median_score']}")

    print(f"\nTarget: 0.5–2.0 avg notifications/user/day")
    print(f"\nNote: relevance score is 0 when category_prefs empty.")
    print(f"With category matching: add ~18pts to median score.")
    print(f"Recommended threshold tuning: lower to 55 for deal_hunter, keep 65 for casual.")


if __name__ == "__main__":
    main()