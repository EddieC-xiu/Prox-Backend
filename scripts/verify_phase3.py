# scripts/verify_phase3.py
# End-to-end smoke test for Phase 3.
#
# Before running:
#   1. Set TEST_ZIP to a ZIP you have active deal rows for
#   2. Set USER_LAT/USER_LNG to coordinates inside that ZIP area
#
# Usage:
#   PYTHONPATH=. python scripts/verify_phase3.py

import sys
import logging
from config.supabase import get_supabase_client
from services.deal_location_service import (
    get_deals_near_zip,
    get_map_pins_near_zip,
    get_cart_optimizer_stores,
)

logging.basicConfig(level=logging.WARNING)
supabase = get_supabase_client()

# ── Set these before running ──────────────────────────────────────────────────
TEST_ZIP = "10001"     # ZIP you have deal data for
USER_LAT = 40.7128     # Coordinates inside that ZIP area
USER_LNG = -74.0060
# ─────────────────────────────────────────────────────────────────────────────

results: list[bool] = []


def check(label: str, condition: bool, detail: str = "") -> None:
    icon = "✓" if condition else "✗"
    line = f"  {icon}  {label}"
    if detail:
        line += f"  — {detail}"
    print(line)
    results.append(condition)


# ── 1. Columns exist ──────────────────────────────────────────────────────────
print("\n[1] Migration check")
try:
    supabase.table("flyer_deals").select(
        "id, match_confidence, candidate_store_count, matched_by, candidate_store_ids"
    ).limit(1).execute()
    check("All Phase 3 columns exist on flyer_deals", True)
except Exception as e:
    check("All Phase 3 columns exist on flyer_deals", False, str(e))
    print("\n  Cannot continue — run migrations 007 and 008 first.\n")
    sys.exit(1)


# ── 2. zip_multi rows have candidate arrays ───────────────────────────────────
print("\n[2] zip_multi candidate_store_ids")
try:
    res = (
        supabase.table("flyer_deals")
        .select("id, store_id, candidate_store_ids")
        .eq("match_confidence", "zip_multi")
        .not_.is_("candidate_store_ids", "null")
        .limit(5)
        .execute()
    )
    rows = res.data or []
    check("At least one zip_multi row has candidate_store_ids", len(rows) > 0)
    if rows:
        sample = rows[0]
        arr    = sample.get("candidate_store_ids") or []
        check("candidate_store_ids has ≥ 2 entries",         len(arr) >= 2,    f"len={len(arr)}")
        check("assigned store_id is in candidate_store_ids", sample["store_id"] in arr)
    else:
        print("  —  No zip_multi rows yet — run the backfill first")
except Exception as e:
    check("zip_multi query succeeded", False, str(e))


# ── 3. Deals without user coords (fallback path) ──────────────────────────────
print(f"\n[3] get_deals_near_zip — no user coords (ZIP={TEST_ZIP})")
try:
    deals = get_deals_near_zip(TEST_ZIP, radius_miles=15.0, limit=20)
    check("Returns a list", isinstance(deals, list))
    check(
        f"ZIP {TEST_ZIP} has at least 1 active deal",
        len(deals) > 0,
        "Update TEST_ZIP at top of script if this fails",
    )
    if deals:
        d = deals[0]
        check("Deal has store_name",        bool(d.get("store_name")))
        check("Deal has distance_miles",    d.get("distance_miles") is not None)
        check("Deal has latitude",          d.get("latitude") is not None)
        check("resolved_at_query is False", d.get("resolved_at_query") is False)
except Exception as e:
    check("get_deals_near_zip (no coords) succeeded", False, str(e))


# ── 4. Deals with user coords (re-resolution path) ────────────────────────────
print(f"\n[4] get_deals_near_zip — with user coords ({USER_LAT}, {USER_LNG})")
try:
    deals_coords = get_deals_near_zip(
        TEST_ZIP, radius_miles=15.0, limit=20,
        user_lat=USER_LAT, user_lng=USER_LNG,
    )
    check("Returns a list with user coords", isinstance(deals_coords, list))
    multi = [d for d in deals_coords if d.get("match_confidence") == "zip_multi"]
    if multi:
        md = multi[0]
        check("zip_multi deal has resolved_at_query=True", md.get("resolved_at_query") is True)
        check("zip_multi deal has latitude",               md.get("latitude") is not None)
        check("zip_multi deal has distance_miles",         md.get("distance_miles") is not None)
    else:
        print(f"  —  No zip_multi deals in ZIP {TEST_ZIP} sample — not a failure")
except Exception as e:
    check("get_deals_near_zip (with coords) succeeded", False, str(e))


# ── 5. Map pins ───────────────────────────────────────────────────────────────
print(f"\n[5] get_map_pins_near_zip (ZIP={TEST_ZIP})")
try:
    pins = get_map_pins_near_zip(TEST_ZIP, radius_miles=15.0,
                                 user_lat=USER_LAT, user_lng=USER_LNG)
    check("Returns a list of pins",  isinstance(pins, list))
    if pins:
        p = pins[0]
        check("Pin has deal_count ≥ 1",  (p.get("deal_count") or 0) >= 1)
        check("Pin has latitude",        p.get("latitude") is not None)
        check("Pin has store_name",      bool(p.get("store_name")))
        if len(pins) > 1:
            check(
                "Pins sorted nearest-first",
                pins[0].get("distance_miles", 0) <= pins[-1].get("distance_miles", 0),
            )
except Exception as e:
    check("get_map_pins_near_zip succeeded", False, str(e))


# ── 6. Cart optimizer ─────────────────────────────────────────────────────────
print(f"\n[6] get_cart_optimizer_stores (ZIP={TEST_ZIP})")
try:
    stores = get_cart_optimizer_stores(
        TEST_ZIP, ["milk", "bread", "eggs"],
        radius_miles=15.0, user_lat=USER_LAT, user_lng=USER_LNG,
    )
    check("Returns a list",        isinstance(stores, list))
    if stores:
        s = stores[0]
        check("Store has score",       s.get("score") is not None)
        check("Store has items_found", s.get("items_found") is not None)
        check("Store has total_price", s.get("total_price") is not None)
except Exception as e:
    check("get_cart_optimizer_stores succeeded", False, str(e))


# ── Summary ───────────────────────────────────────────────────────────────────
passed = sum(results)
total  = len(results)
print(f"\n{'=' * 50}")
print(f"  {passed}/{total} checks passed")
if passed == total:
    print("  ✓  Phase 3 fully operational.\n")
else:
    print("  Some checks failed — review output above.\n")
    sys.exit(1)