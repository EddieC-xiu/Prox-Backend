# scripts/test_pipeline_ingest.py
# Full end-to-end smoke test — DOES write to flyer_deals (upsert on flyer_id).
#
# Run with: PYTHONPATH=. python scripts/test_pipeline_ingest.py

from jobs.pipeline_ingest import ingest_deals

KROGER_ZIP  = "11211"
SAFEWAY_ZIP = "19702"

TEST_DEALS = [
    # ✅ Should match — exists in store_locations
    {
        "product_name":  "Test Apple",
        "retailer_name": "kroger",
        "zip_code":      KROGER_ZIP,
        "flyer_id":      "test-smoke-001",
    },
    # ✅ Should match — exists in store_locations
    {
        "product_name":  "Test Bread",
        "retailer_name": "safeway",
        "zip_code":      SAFEWAY_ZIP,
        "flyer_id":      "test-smoke-002",
    },
    # ❌ Should NOT match — garbage retailer, still upserted with store_id=NULL
    {
        "product_name":  "Test Milk",
        "retailer_name": "fake_retailer_xyz",
        "zip_code":      "00000",
        "flyer_id":      "test-smoke-003",
    },
]

stats = ingest_deals(TEST_DEALS, dry_run=False)

print("\n── Stats ──────────────────────────────")
print(f"  total:     {stats['total']}")
print(f"  inserted:  {stats['inserted']}")
print(f"  no_store:  {stats['no_store']}  ← should be 1")
print(f"  errors:    {stats['errors']}   ← should be 0")
print(f"  cache:     {stats['cache_snapshot']}")

assert stats["errors"]   == 0, "❌ unexpected errors"
assert stats["no_store"] == 1, "❌ expected exactly 1 no-match"
assert stats["inserted"] == 3, "❌ expected 3 rows upserted (incl. the no-store row)"
print("\n✅ smoke test passed")

# ── Cleanup: run this in Supabase when done ──
# DELETE FROM flyer_deals WHERE flyer_id IN ('test-smoke-001','test-smoke-002','test-smoke-003');