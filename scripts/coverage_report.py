# scripts/coverage_report.py
# Phase 3 store-mapping coverage report.
# This is your new health check — replaces validate_and_benchmark for Phase 3.
#
# Usage:
#   PYTHONPATH=. python scripts/coverage_report.py

import logging
from collections import Counter
from config.supabase import get_supabase_client

logging.basicConfig(level=logging.WARNING)
supabase = get_supabase_client()


def run():
    print("\n=== Phase 3 Coverage Report ===\n")

    # Total deals
    total_res = supabase.table("flyer_deals").select("id", count="exact").execute()
    total     = total_res.count or 0
    print(f"  Total deals in flyer_deals: {total:,}\n")

    # Breakdown by match_confidence
    print("  By match_confidence:")
    print(f"  {'confidence':<30} {'count':>8}  {'%':>6}")
    print("  " + "-" * 48)

    for conf in ("zip_single", "zip_multi", "city_state", "created", "none"):
        res = (
            supabase.table("flyer_deals")
            .select("id", count="exact")
            .eq("match_confidence", conf)
            .execute()
        )
        n   = res.count or 0
        pct = round(n / total * 100, 1) if total else 0
        print(f"  {conf:<30} {n:>8,}  {pct:>5.1f}%")

    # NULL / unprocessed
    res = (
        supabase.table("flyer_deals")
        .select("id", count="exact")
        .is_("match_confidence", "null")
        .execute()
    )
    n   = res.count or 0
    pct = round(n / total * 100, 1) if total else 0
    print(f"  {'unprocessed (null)':<30} {n:>8,}  {pct:>5.1f}%")
    if n > 0:
        print(f"\n  ⚠  {n:,} unprocessed rows — run: PYTHONPATH=. python jobs/backfill_store_ids.py")

    # zip_multi candidate array health
    print()
    multi_total_res = (
        supabase.table("flyer_deals")
        .select("id", count="exact")
        .eq("match_confidence", "zip_multi")
        .execute()
    )
    multi_arr_res = (
        supabase.table("flyer_deals")
        .select("id", count="exact")
        .eq("match_confidence", "zip_multi")
        .not_.is_("candidate_store_ids", "null")
        .execute()
    )
    arr_total  = multi_total_res.count or 0
    arr_filled = multi_arr_res.count or 0
    arr_pct    = round(arr_filled / arr_total * 100, 1) if arr_total else 0
    print(
        f"  zip_multi with candidate_store_ids: "
        f"{arr_filled:,}/{arr_total:,} ({arr_pct}%)"
    )
    if arr_pct < 100 and arr_total > 0:
        print("  ⚠  Run: PYTHONPATH=. python jobs/backfill_store_ids.py --all-rows")

    # Per-retailer coverage
    print("\n  Per-retailer (top 20 by deal count):")
    print(f"  {'retailer_key':<30} {'total':>8} {'matched':>8} {'%':>6}")
    print("  " + "-" * 60)

    all_keys_res = supabase.table("flyer_deals").select("retailer_key").execute()
    counts       = Counter(
        r["retailer_key"] for r in (all_keys_res.data or []) if r.get("retailer_key")
    ).most_common(20)

    for key, n in counts:
        matched_res = (
            supabase.table("flyer_deals")
            .select("id", count="exact")
            .eq("retailer_key", key)
            .not_.is_("store_id", "null")
            .execute()
        )
        matched = matched_res.count or 0
        pct     = round(matched / n * 100, 1) if n else 0
        flag    = "  ⚠" if pct < 80 else ""
        print(f"  {key:<30} {n:>8,} {matched:>8,} {pct:>5.1f}%{flag}")

    print()


if __name__ == "__main__":
    run()