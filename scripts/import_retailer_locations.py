# scripts/import_retailer_locations.py
#
# Imports Smart & Final locations from provided data files.
#
# Dry run:
#   PYTHONUTF8=1 PYTHONPATH=. python scripts/import_retailer_locations.py --dry-run
#
# Real write:
#   PYTHONUTF8=1 PYTHONPATH=. python scripts/import_retailer_locations.py

import json
import argparse
from datetime import datetime, timezone
from config.supabase import get_supabase_client

sb = get_supabase_client()

def now_iso():
    return datetime.now(timezone.utc).isoformat()

# ── Parse Smart & Final ────────────────────────────────────────────────────────
def load_smart_final(path: str) -> list[dict]:
    with open(path) as f:
        data = json.load(f)
    seen = {}
    for r in data:
        sid = r["field_store_id"]
        if sid not in seen:
            seen[sid] = r
    rows = []
    for r in seen.values():
        zip_code = r.get("field_zipcode", "").strip()[:5]
        full_address = f"{r['field_contact_address']}, {r['field_city']}, {r['field_state']} {zip_code}"
        rows.append({
            "retailer": "smart_final",
            "full_address": full_address,
            "zip_code": zip_code,
            "latitude": float(r["field_latitude"]),
            "longitude": float(r["field_longitude"]),
            "geocode_source": "osm",
            "geocode_confidence": "exact",
            "show_on_map": True,
            "geocoded_at": now_iso(),
        })
    return rows

# ── Write to DB ────────────────────────────────────────────────────────────────
def write_rows(rows: list[dict]):
    batch_size = 50
    written = 0
    for i in range(0, len(rows), batch_size):
        batch = rows[i:i + batch_size]
        try:
            sb.table("store_locations").insert(batch).execute()
            written += len(batch)
            print(f"  Written {written} / {len(rows)}...")
        except Exception as e:
            print(f"  Batch {i} failed: {e}")
    return written

# ── Main ───────────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if args.dry_run:
        print("[DRY RUN] Nothing will be written.\n")

    print("Loading Smart & Final locations...")
    sf_rows = load_smart_final("data/smart___final_locaitons.txt")
    print(f"  {len(sf_rows)} unique stores loaded")
    print(f"  Sample: {sf_rows[0]['full_address']} → ({sf_rows[0]['latitude']}, {sf_rows[0]['longitude']})")
    print(f"  Sample: {sf_rows[1]['full_address']} → ({sf_rows[1]['latitude']}, {sf_rows[1]['longitude']})")
    print(f"  Sample: {sf_rows[2]['full_address']} → ({sf_rows[2]['latitude']}, {sf_rows[2]['longitude']})")

    if args.dry_run:
        print(f"\n[DRY RUN] Would write {len(sf_rows)} Smart & Final rows.")
        return

    print("\nWriting Smart & Final to DB...")
    written = write_rows(sf_rows)
    print(f"\n✅ Smart & Final done. {written} rows written.")

    print("\nCleaning up old null-address Smart & Final rows...")
    try:
        sb.table("store_locations").delete().eq(
            "retailer", "smart_final"
        ).is_("full_address", "null").execute()
        print("✅ Old rows cleaned up.")
    except Exception as e:
        print(f"Cleanup failed: {e}")

if __name__ == "__main__":
    main()