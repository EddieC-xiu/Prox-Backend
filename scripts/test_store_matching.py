# scripts/test_store_matching.py
# Dry run — tests matching logic ONLY.  Zero writes to any table.
#
# Run with: PYTHONPATH=. python scripts/test_store_matching.py

from services.store_matching import find_store_for_deal

TEST_CASES = [
    # (retailer_raw,               zip_code,   should_match)

    # Direct keys
    ("kroger",                     "11211",    True),
    ("safeway",                    "19702",    True),

    # Alias resolution  →  kroger
    ("Kroger Delivery Now",        "11211",    True),
    ("Kroger",                     "11211",    True),

    # Alias resolution  →  safeway
    ("Safeway Rapid",              "19702",    True),
    ("SAFEWAY",                    "19702",    True),

    # Suffix variants
    ("Stop & Shop Express",        "01007",    True),   # → stopandshop
    ("King Soopers Delivery Now",  "80002",    True),   # → kingsoopers

    # Should NEVER match — in _NO_MATCH_RETAILERS
    ("walgreens",                  "10001",    False),
    ("cvs",                        "10001",    False),
    ("dollargeneral",              "10001",    False),

    # Should NEVER match — unknown retailer
    ("fake_retailer_xyz",          "00000",    False),
    ("",                           "10001",    False),
]

passed = 0
failed = 0

print(f"{'STATUS':<6}  {'RETAILER_RAW':<30}  {'ZIP':<10}  {'STORE_ID':<10}  {'CONFIDENCE':<30}  BY")
print("-" * 110)

for retailer_raw, zip_code, should_match in TEST_CASES:
    result  = find_store_for_deal(retailer_raw=retailer_raw, zip_code=zip_code)
    matched = result.store_id is not None
    ok      = matched == should_match

    status  = "✅ PASS" if ok else "❌ FAIL"
    print(
        f"{status:<6}  {retailer_raw:<30}  {zip_code:<10}  "
        f"{str(result.store_id):<10}  {result.match_confidence:<30}  {result.matched_by}"
    )

    if ok:
        passed += 1
    else:
        failed += 1

print("-" * 110)
print(f"\n{passed} passed, {failed} failed")
assert failed == 0, "❌ some matching cases failed — see rows above"
print("✅ all matching tests passed — zero rows written to any table")