# scripts/test_deterministic_matching.py
#
# Pulls test_flyer_deals_duplicate, runs the deterministic normalizer,
# groups by match_key, and produces the report Alston asked for.
#
# Run: PYTHONPATH=. python scripts/test_deterministic_matching.py

import logging
from collections import defaultdict
from config.supabase import get_supabase_client
from scoring.product_normalizer import make_match_key
from services.store_matching import RETAILER_ALIASES

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)

BATCH_SIZE = 1000


def normalize_retailer(raw: str) -> str:
    stripped = (raw or "").strip()
    return RETAILER_ALIASES.get(stripped, stripped.lower())


def fetch_all_rows(supabase) -> list[dict]:
    rows, offset = [], 0
    while True:
        res = (
            supabase.table("test_flyer_deals_duplicate")
            .select("id, retailer, product_name, base_amount, base_unit, product_price")
            .range(offset, offset + BATCH_SIZE - 1)
            .execute()
        )
        batch = res.data or []
        rows.extend(batch)
        logger.info(f"Fetched {len(rows)} rows...")
        if len(batch) < BATCH_SIZE:
            break
        offset += BATCH_SIZE
    return rows


def main():
    supabase = get_supabase_client()
    logger.info("Fetching rows...")
    rows = fetch_all_rows(supabase)
    logger.info(f"Total rows: {len(rows)}")

    keyed     = []
    no_key    = 0
    by_conf   = defaultdict(int)

    for row in rows:
        result = make_match_key(
            product_name=row.get("product_name") or "",
            base_amount=row.get("base_amount"),
            base_unit=row.get("base_unit"),
        )
        result["id"]            = row["id"]
        result["retailer"]      = normalize_retailer(row.get("retailer"))
        result["product_name"]  = row.get("product_name")
        result["product_price"] = row.get("product_price")
        by_conf[result["confidence"]] += 1

        if result["match_key"]:
            keyed.append(result)
        else:
            no_key += 1

    # Group by match_key
    groups: dict[str, list] = defaultdict(list)
    for r in keyed:
        groups[r["match_key"]].append(r)

    # Cross-retailer = 2+ distinct retailers in same group
    cross = {
        k: v for k, v in groups.items()
        if len({r["retailer"] for r in v}) >= 2
    }

    total        = len(rows)
    matched_rows = sum(len(v) for v in cross.values())
    match_rate   = matched_rows / total * 100

    print("\n── Deterministic Match Report ──────────────────────────────────────")
    print(f"  Total rows:             {total:,}")
    print(f"  Rows with a match key:  {len(keyed):,}  ({len(keyed)/total*100:.1f}%)")
    print(f"  Rows without key:       {no_key:,}")
    print(f"  Confidence breakdown:   {dict(by_conf)}")
    print(f"  Cross-retailer groups:  {len(cross):,}")
    print(f"  Rows in those groups:   {matched_rows:,}  ({match_rate:.1f}%)")

    # ── Correct match examples ───────────────────────────────────────────────
    print("\n── Sample: Correct Matches (same product, different retailer) ──────")
    shown = 0
    for key, members in sorted(cross.items(), key=lambda x: -len(x[1])):
        if shown >= 5: break
        print(f"\n  KEY: {key}")
        for m in members[:4]:
            print(f"    [{m['retailer']}]  {m['product_name']}  — ${m['product_price']}")
        shown += 1

    # ── Ambiguous examples (same brand+name, DIFFERENT size) ────────────────
    print("\n── Sample: Ambiguous / Suspect (same name, size mismatch) ─────────")
    by_name: dict[str, list] = defaultdict(list)
    for r in keyed:
        name_key = f"{r['brand'] or 'unknown'}|{r['canonical_name']}"
        by_name[name_key].append(r)

    shown = 0
    for name_key, members in by_name.items():
        if shown >= 5: break
        retailers = {r["retailer"] for r in members}
        sizes     = {r["size_oz"] for r in members}
        if len(retailers) < 2 or len(sizes) < 2:
            continue
        print(f"\n  NAME KEY: {name_key}")
        for m in members[:4]:
            print(f"    [{m['retailer']}]  {m['product_name']}  size_oz={m['size_oz']}  — ${m['product_price']}")
        shown += 1

    # ── Recommendation ───────────────────────────────────────────────────────
    print("\n── Recommendation ──────────────────────────────────────────────────")
    if match_rate >= 60:
        print("  ✅ Strong coverage. Embeddings as fallback optional.")
    elif match_rate >= 30:
        print("  ⚠️  Moderate. Recommend embeddings as fallback for unmatched rows.")
    else:
        print("  ❌ Low coverage. Expand KNOWN_BRANDS or add embeddings fallback.")
    print()


if __name__ == "__main__":
    main()

