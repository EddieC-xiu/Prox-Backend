# Compare Kiran's AI canonical lookup vs our build_canonical_name normalizer
# Usage: PYTHONPATH=. python scripts/compare_canonicalization.py [--limit 200]
#
# Prints side-by-side results and a summary showing which system matches more
# flyer_deals rows to each other (proxy for "better grouping").

import argparse
import re
from collections import defaultdict
from config.supabase import get_supabase_client
from scoring.product_normalizer import extract_brand, build_canonical_name
from services.cross_retailer_service import _kiran_canonical

sb = get_supabase_client()

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=200, help="Number of rows to sample")
    args = parser.parse_args()

    print(f"Fetching {args.limit} rows from flyer_deals...\n")
    rows = (
        sb.table("flyer_deals")
        .select("id, product_name, brand, retailer")
        .not_.is_("product_name", "null")
        .limit(args.limit)
        .execute()
        .data or []
    )

    kiran_hits = 0
    ours_hits  = 0
    both_same  = 0
    kiran_wins = 0
    ours_wins  = 0

    kiran_groups: dict[str, list[str]] = defaultdict(list)
    ours_groups:  dict[str, list[str]] = defaultdict(list)

    print(f"{'product_name':<45} {'kiran':<40} {'ours':<40} match?")
    print("-" * 170)

    for row in rows:
        name  = (row.get("product_name") or "").strip()
        brand = row.get("brand") or extract_brand(name)
        if not name:
            continue

        ours  = build_canonical_name(name, brand)
        kiran = _kiran_canonical(name, pre_normalized=ours)

        if kiran:
            kiran_hits += 1
            kiran_groups[kiran].append(name)
        if ours:
            ours_hits += 1
            ours_groups[ours].append(name)

        if kiran and ours:
            if kiran == ours:
                both_same += 1
                flag = "="
            elif kiran and not ours:
                kiran_wins += 1
                flag = "K"
            elif ours and not kiran:
                ours_wins += 1
                flag = "O"
            else:
                flag = "diff"
        elif kiran and not ours:
            kiran_wins += 1
            flag = "K"
        elif ours and not kiran:
            ours_wins += 1
            flag = "O"
        else:
            flag = "-"

        trunc = lambda s, n: (s or "")[:n].ljust(n)
        print(f"{trunc(name,45)} {trunc(kiran,40)} {trunc(ours,40)} {flag}")

    total = len(rows)
    print("\n" + "=" * 80)
    print(f"SUMMARY  (n={total})")
    print(f"  Kiran hit rate : {kiran_hits}/{total} = {kiran_hits/total*100:.1f}%")
    print(f"  Ours  hit rate : {ours_hits}/{total}  = {ours_hits/total*100:.1f}%")
    print(f"  Both agree     : {both_same}")
    print(f"  Only Kiran hit : {kiran_wins}")
    print(f"  Only ours hit  : {ours_wins}")

    # Grouping power: how many unique products collapse to the same canonical name?
    # Higher avg group size = better cross-retailer matching
    def avg_group(groups: dict) -> float:
        sizes = [len(v) for v in groups.values() if len(v) > 1]
        return sum(sizes) / len(sizes) if sizes else 1.0

    print(f"\n  Kiran avg group size (multi-match only): {avg_group(kiran_groups):.2f}")
    print(f"  Ours  avg group size (multi-match only): {avg_group(ours_groups):.2f}")
    print("\n  Larger avg group size = more products collapsing to same canonical = more cross-retailer matches")

    print("\nTop Kiran groups (size > 1):")
    for k, v in sorted(kiran_groups.items(), key=lambda x: -len(x[1]))[:10]:
        if len(v) > 1:
            print(f"  [{len(v)}] '{k}' <- {v[:3]}")

if __name__ == "__main__":
    main()
