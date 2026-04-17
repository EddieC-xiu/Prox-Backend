# scripts/notification_stats.py
#
# Phase 4 — Notification Volume & Quality Dashboard
#
# Queries notification_log and reports:
#   - Daily send volume
#   - Top products and retailers
#   - Score distribution
#   - Per-user stats
#   - Block reason breakdown
#
# Usage:
#   PYTHONUTF8=1 PYTHONPATH=. python scripts/notification_stats.py
#   PYTHONUTF8=1 PYTHONPATH=. python scripts/notification_stats.py --days 7
#   PYTHONUTF8=1 PYTHONPATH=. python scripts/notification_stats.py --days 1

import argparse
import statistics
from collections import defaultdict
from datetime import datetime, timezone, timedelta
from config.supabase import get_supabase_client

sb = get_supabase_client()


def load_logs(days: int) -> list[dict]:
    since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    try:
        res = (
            sb.table("notification_log")
            .select("user_id, canonical_product_name, retailer, retailer_key, zip_code, price, deal_score, relevance_score, notification_score, deal_reason, trigger_type, sent_at")
            .gte("sent_at", since)
            .order("sent_at", desc=True)
            .execute()
        )
        return res.data or []
    except Exception as e:
        print(f"Error loading logs: {e}")
        return []


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--days", type=int, default=7, help="Look back N days")
    args = parser.parse_args()

    logs = load_logs(args.days)

    print(f"\n{'='*60}")
    print(f"NOTIFICATION STATS — Last {args.days} day(s)")
    print(f"{'='*60}")

    if not logs:
        print(f"\n  No notifications sent in the last {args.days} day(s).")
        print(f"  Pipeline is ready — waiting on real price drop data.\n")
        return

    # ── Overview ──────────────────────────────────────────────
    total         = len(logs)
    unique_users  = len(set(r["user_id"] for r in logs))
    unique_products = len(set(r["canonical_product_name"] for r in logs))
    unique_retailers = len(set(r["retailer"] for r in logs))
    avg_per_user  = round(total / unique_users, 2) if unique_users else 0

    print(f"\n── Overview ──────────────────────────────────────────")
    print(f"  Total sent        : {total}")
    print(f"  Unique users      : {unique_users}")
    print(f"  Avg per user      : {avg_per_user}/day")
    print(f"  Unique products   : {unique_products}")
    print(f"  Unique retailers  : {unique_retailers}")

    # ── Score distribution ────────────────────────────────────
    scores = [float(r["notification_score"]) for r in logs if r.get("notification_score")]
    if scores:
        print(f"\n── Score Distribution ────────────────────────────────")
        print(f"  Min score         : {min(scores):.1f}")
        print(f"  Max score         : {max(scores):.1f}")
        print(f"  Median score      : {statistics.median(scores):.1f}")
        print(f"  Avg score         : {round(sum(scores)/len(scores), 1)}")
        buckets = {
            "50-60": sum(1 for s in scores if 50 <= s < 60),
            "60-70": sum(1 for s in scores if 60 <= s < 70),
            "70-80": sum(1 for s in scores if 70 <= s < 80),
            "80+":   sum(1 for s in scores if s >= 80),
        }
        print(f"  Buckets           : " + " | ".join(f"{k}:{v}" for k,v in buckets.items()))

    # ── Daily volume ──────────────────────────────────────────
    by_day: dict = defaultdict(int)
    for r in logs:
        day = r["sent_at"][:10]
        by_day[day] += 1

    print(f"\n── Daily Volume ──────────────────────────────────────")
    for day in sorted(by_day.keys(), reverse=True):
        bar = "█" * min(by_day[day], 40)
        print(f"  {day} : {bar} {by_day[day]}")

    # ── Top products ──────────────────────────────────────────
    by_product: dict = defaultdict(int)
    for r in logs:
        by_product[r["canonical_product_name"]] += 1

    print(f"\n── Top Products ──────────────────────────────────────")
    for product, count in sorted(by_product.items(), key=lambda x: -x[1])[:10]:
        print(f"  {count:>4}x  {product}")

    # ── Top retailers ─────────────────────────────────────────
    by_retailer: dict = defaultdict(int)
    for r in logs:
        by_retailer[r["retailer"]] += 1

    print(f"\n── Top Retailers ─────────────────────────────────────")
    for retailer, count in sorted(by_retailer.items(), key=lambda x: -x[1])[:10]:
        print(f"  {count:>4}x  {retailer}")

    # ── Trigger type breakdown ────────────────────────────────
    by_trigger: dict = defaultdict(int)
    for r in logs:
        by_trigger[r.get("trigger_type") or "unknown"] += 1

    print(f"\n── Trigger Types ─────────────────────────────────────")
    for trigger, count in sorted(by_trigger.items(), key=lambda x: -x[1]):
        print(f"  {count:>4}x  {trigger}")

    # ── Per-user breakdown ────────────────────────────────────
    by_user: dict = defaultdict(int)
    for r in logs:
        by_user[r["user_id"][:8]] += 1

    print(f"\n── Per-User Breakdown ────────────────────────────────")
    print(f"  {'User':<12} {'Count':<8}")
    for user, count in sorted(by_user.items(), key=lambda x: -x[1])[:10]:
        print(f"  {user}...  {count}")

    # ── Recent notifications ──────────────────────────────────
    print(f"\n── Most Recent Notifications ─────────────────────────")
    for r in logs[:5]:
        sent = r["sent_at"][:16].replace("T", " ")
        print(f"  [{sent}] {r['user_id'][:8]}... → {r['canonical_product_name']} @ {r['retailer']}")
        print(f"           score: {r['notification_score']} | {r['deal_reason']}")
        print()

    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()