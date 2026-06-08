"""
Backfill cleaned daily price history from flyer_deals.

This script is intentionally standalone: it uses only Python's standard library
so it can run locally without installing the backend dependencies.

Usage:
    python scripts/backfill_price_history.py --dry-run --days 7
    python scripts/backfill_price_history.py --days 7
    python scripts/backfill_price_history.py --date-field processed_at --from-date 2026-06-07 --to-date 2026-06-08
"""
import argparse
import json
import logging
import os
import re
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

SOURCE_TABLE = "flyer_deals"
TARGET_TABLE = "price_history"
FETCH_BATCH = 1000
WRITE_BATCH = 500
MAX_RETRIES = 2
MAX_PRICE = 999999.0
MIN_REAL_SIZE_OZ = 1.5

SIZE_IN_NAME_RE = re.compile(
    r"(\d+(?:\.\d+)?)\s*(oz|fl\.?\s*oz|g|gram|lb|pound|ml|liter)\b",
    re.IGNORECASE,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Backfill one daily best price row per match_key + store_id + date."
    )
    parser.add_argument("--dry-run", action="store_true", help="Count rows without writing to price_history")
    parser.add_argument("--days", type=int, default=7, help="Only backfill flyer_deals from the last N days")
    parser.add_argument("--from-date", help="Start date, YYYY-MM-DD. Overrides --days when provided.")
    parser.add_argument("--to-date", help="End date, YYYY-MM-DD inclusive. Defaults to today.")
    parser.add_argument(
        "--date-field",
        choices=("deal_date", "processed_at"),
        default="deal_date",
        help="Use deal_date for date_added/created_at, or processed_at for pipeline-ready rows.",
    )
    return parser.parse_args()


def load_env_file() -> None:
    env_path = Path(__file__).resolve().parents[1] / ".env"
    if not env_path.exists():
        return

    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def supabase_config() -> tuple[str, str]:
    load_env_file()
    url = (os.environ.get("SUPABASE_URL") or "").rstrip("/")
    key = os.environ.get("SUPABASE_KEY") or ""
    if not url or not key:
        raise EnvironmentError("SUPABASE_URL and SUPABASE_KEY must be set in .env or environment variables.")
    return url, key


def request_json(
    method: str,
    path: str,
    params: dict | list[tuple[str, str]] | None = None,
    payload: object | None = None,
) -> object:
    base_url, key = supabase_config()
    query = f"?{urlencode(params)}" if params else ""
    url = f"{base_url}/rest/v1/{path}{query}"
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    headers = {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
    }
    if method == "POST" and path.startswith(TARGET_TABLE):
        headers["Prefer"] = "resolution=merge-duplicates,return=minimal"

    req = Request(url, data=data, headers=headers, method=method)
    with urlopen(req, timeout=120) as res:
        body = res.read()
        if not body:
            return None
        return json.loads(body.decode("utf-8"))


def to_oz(amount: float, unit: str) -> float | None:
    u = unit.lower().replace(" ", "").replace(".", "")
    if u in ("oz", "floz"):
        return round(amount, 2)
    if u in ("g", "gram"):
        return round(amount * 0.035274, 2)
    if u in ("lb", "pound"):
        return round(amount * 16.0, 2)
    if u == "ml":
        return round(amount * 0.033814, 2)
    if u in ("l", "liter"):
        return round(amount * 33.814, 2)
    return None


def normalize_size_oz(base_amount, base_unit, product_name: str) -> float | None:
    db_oz = None
    if base_amount is not None and base_unit:
        try:
            db_oz = to_oz(float(base_amount), str(base_unit))
        except (TypeError, ValueError):
            pass

    name_candidates = []
    for amt_str, unit in SIZE_IN_NAME_RE.findall(product_name or ""):
        oz = to_oz(float(amt_str), unit)
        if oz and oz >= MIN_REAL_SIZE_OZ:
            name_candidates.append(oz)

    name_oz = max(name_candidates) if name_candidates else None
    if db_oz and db_oz >= MIN_REAL_SIZE_OZ:
        return db_oz
    if name_oz:
        return name_oz
    return db_oz


def fetch_batch(
    last_seen_id: int,
    start_iso: str,
    end_exclusive_iso: str,
    date_field: str,
) -> list[dict] | None:
    params: list[tuple[str, str]] = [
        ("select", (
            "id,match_key,brand,canonical_product_name,product_price,"
            "base_amount,base_unit,store_id,date_added,created_at,processed_at"
        )),
        ("match_key", "not.is.null"),
        ("store_id", "not.is.null"),
        ("product_price", "not.is.null"),
        ("id", f"gt.{last_seen_id}"),
        ("order", "processed_at.asc,id.asc" if date_field == "processed_at" else "date_added.asc,id.asc"),
        ("limit", str(FETCH_BATCH)),
    ]

    if date_field == "processed_at":
        params.extend([
            ("processed_at", f"gte.{start_iso}T00:00:00+00:00"),
            ("processed_at", f"lt.{end_exclusive_iso}T00:00:00+00:00"),
        ])
    else:
        end_inclusive_iso = (datetime.fromisoformat(end_exclusive_iso).date() - timedelta(days=1)).isoformat()
        params.extend([
            ("date_added", f"gte.{start_iso}"),
            ("date_added", f"lte.{end_inclusive_iso}"),
        ])

    for attempt in range(MAX_RETRIES):
        try:
            return request_json("GET", SOURCE_TABLE, params=params) or []
        except Exception as e:
            logger.warning(f"Fetch failed after id {last_seen_id} (attempt {attempt + 1}): {e}; retrying in 2s")
            time.sleep(2)
    logger.error(f"Fetch permanently failed after id {last_seen_id}; stopping")
    return None


def row_deal_date(row: dict, date_field: str) -> str | None:
    raw = row.get("processed_at") if date_field == "processed_at" else row.get("date_added") or row.get("created_at")
    return str(raw)[:10] if raw else None


def make_record(row: dict, price: float, deal_date: str, observed_at: str) -> dict:
    canonical = row.get("canonical_product_name")
    return {
        "match_key": row.get("match_key"),
        "store_id": row.get("store_id"),
        "brand": row.get("brand"),
        "canonical_product_name": canonical,
        "size_oz": normalize_size_oz(row.get("base_amount"), row.get("base_unit"), canonical or ""),
        "product_price": price,
        "observed_at": observed_at,
        "observed_date": deal_date,
    }


def upsert_price_history(rows: list[dict]) -> int:
    written = 0
    params = {"on_conflict": "match_key,store_id,observed_date"}
    for i in range(0, len(rows), WRITE_BATCH):
        batch = rows[i:i + WRITE_BATCH]
        for attempt in range(MAX_RETRIES + 1):
            try:
                request_json("POST", TARGET_TABLE, params=params, payload=batch)
                written += len(batch)
                logger.info(f"Upserted {written:,}/{len(rows):,} price_history rows")
                break
            except Exception as e:
                if attempt >= MAX_RETRIES:
                    logger.error(f"Write permanently failed for rows {i}-{i + len(batch) - 1}: {e}")
                    raise
                wait = 2 * (attempt + 1)
                logger.warning(
                    f"Write failed for rows {i}-{i + len(batch) - 1} "
                    f"(attempt {attempt + 1}): {e}; retrying in {wait}s"
                )
                time.sleep(wait)
    return written


def cleanup_duplicates() -> None:
    request_json("POST", "rpc/cleanup_price_history_dupes", payload={})


def main():
    args = parse_args()
    now = datetime.now(timezone.utc)
    observed_at = now.isoformat()
    start_date = args.from_date or (now.date() - timedelta(days=args.days - 1)).isoformat()
    end_date = args.to_date or now.date().isoformat()
    end_exclusive = (datetime.fromisoformat(end_date).date() + timedelta(days=1)).isoformat()

    last_seen_id = 0
    total_fetched = 0
    total_skipped = 0
    grouped: dict[tuple, dict] = {}

    logger.info(
        f"Starting {'DRY RUN ' if args.dry_run else ''}price_history backfill from {SOURCE_TABLE} "
        f"using {args.date_field} from {start_date} through {end_date}"
    )

    while True:
        batch = fetch_batch(last_seen_id, start_date, end_exclusive, args.date_field)

        if batch is None:
            break
        if not batch:
            break

        total_fetched += len(batch)
        last_seen_id = max(int(row["id"]) for row in batch if row.get("id") is not None)

        for row in batch:
            match_key = row.get("match_key")
            store_id = row.get("store_id")
            deal_date = row_deal_date(row, args.date_field)

            if not match_key or store_id is None or not deal_date:
                total_skipped += 1
                continue
            if deal_date < start_date or deal_date > end_date:
                total_skipped += 1
                continue

            try:
                price = float(row.get("product_price") or 0)
            except (TypeError, ValueError):
                total_skipped += 1
                continue

            if price <= 0 or price > MAX_PRICE:
                total_skipped += 1
                continue

            group_key = (match_key, store_id, deal_date)
            existing = grouped.get(group_key)

            if not existing or price < existing["product_price"]:
                grouped[group_key] = make_record(row, price, deal_date, observed_at)

        if total_fetched % 10000 == 0:
            logger.info(
                f"Progress: {total_fetched:,} fetched | {len(grouped):,} grouped | "
                f"{total_skipped:,} skipped | last_id={last_seen_id}"
            )

    rows_to_write = list(grouped.values())
    total_written = 0

    if args.dry_run:
        total_written = len(rows_to_write)
    elif rows_to_write:
        total_written = upsert_price_history(rows_to_write)

    if not args.dry_run:
        logger.info("Running duplicate cleanup...")
        try:
            cleanup_duplicates()
            logger.info("Duplicate cleanup complete.")
        except Exception as e:
            logger.warning(f"Cleanup step failed (non-critical): {e}")

    print("\nDone.")
    print(f"  Fetched:  {total_fetched:,}")
    print(f"  Grouped:  {len(grouped):,}")
    print(f"  Written:  {total_written:,}")
    print(f"  Skipped:  {total_skipped:,}")
    if args.dry_run:
        print("\n[DRY RUN] Nothing was written.")


if __name__ == "__main__":
    main()
