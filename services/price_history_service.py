import logging
from datetime import datetime, timedelta, timezone
from config.supabase import get_supabase_client

logger = logging.getLogger(__name__)

TABLE      = "price_history"
BATCH_SIZE = 500


def upsert_price_history(rows: list[dict]) -> int:
    if not rows:
        return 0
    client  = get_supabase_client()
    written = 0
    for i in range(0, len(rows), BATCH_SIZE):
        batch = rows[i:i + BATCH_SIZE]
        client.table(TABLE)\
            .upsert(batch, on_conflict="match_key,store_id,observed_date")\
            .execute()
        written += len(batch)
        logger.info(f"Upserted {written}/{len(rows)} price_history rows")
    return written


def _match_key_variants(match_key: str) -> list[str]:
    """Return all format variants of a match_key to try in order.

    Handles two historical format mismatches:
    - Brand casing: 'Carolina|...|32' vs 'carolina|...|32'
    - Size field: '...|32' vs '...|no_size'
    - Numeric size formatting: '...|80' vs '...|80.0'
    """
    parts = match_key.rsplit("|", 1)
    if len(parts) != 2:
        return [match_key]
    base, size = parts
    brand_canonical = base.split("|", 1)
    if len(brand_canonical) != 2:
        return [match_key]
    brand, canonical = brand_canonical
    brand_lower = brand.lower()

    sizes = [size]
    if size != "no_size":
        try:
            numeric_size = float(size)
            if numeric_size.is_integer():
                size_with_decimal = f"{numeric_size:.1f}"
                if size_with_decimal not in sizes:
                    sizes.append(size_with_decimal)
            size_without_decimal = f"{numeric_size:g}"
            if size_without_decimal not in sizes:
                sizes.append(size_without_decimal)
        except (TypeError, ValueError):
            pass
        sizes.append("no_size")

    brands = [brand]
    if brand_lower != brand:
        brands.append(brand_lower)

    variants = []
    for variant_size in sizes:
        for variant_brand in brands:
            variant = f"{variant_brand}|{canonical}|{variant_size}"
            if variant not in variants:
                variants.append(variant)
    return variants


def _query_history(client, key: str, store_id: str, since: str) -> list[dict]:
    return client.table(TABLE)\
        .select("observed_at, product_price, store_id")\
        .eq("match_key", key)\
        .eq("store_id", store_id)\
        .gte("observed_at", since)\
        .order("observed_at", desc=False)\
        .execute().data or []


def get_price_history(match_key: str, store_id: str, days: int = 90) -> list[dict]:
    client = get_supabase_client()
    since  = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    for key in _match_key_variants(match_key):
        rows = _query_history(client, key, store_id, since)
        if rows:
            return rows
    return []


def get_baseline_price(match_key: str, store_id: str, days: int = 90) -> float | None:
    history = get_price_history(match_key, store_id, days)
    if not history:
        return None
    # Group by date (truncate timestamp to date) and take daily min
    by_date: dict[str, list[float]] = {}
    for row in history:
        day = row["observed_at"][:10]  # "2026-03-23T..." → "2026-03-23"
        by_date.setdefault(day, []).append(float(row["product_price"]))
    daily_mins = [min(prices) for prices in by_date.values()]
    return round(sum(daily_mins) / len(daily_mins), 2)


def get_latest_price(match_key: str, store_id: str) -> dict | None:
    client = get_supabase_client()
    res    = client.table(TABLE)\
        .select("product_price, observed_at, flyer_id")\
        .eq("match_key", match_key)\
        .eq("store_id", store_id)\
        .order("observed_at", desc=True)\
        .limit(1)\
        .execute()
    return res.data[0] if res.data else None


def get_all_match_key_store_pairs() -> list[dict]:
    client = get_supabase_client()
    res    = client.table(TABLE).select("match_key, store_id").execute()
    seen, pairs = set(), []
    for row in res.data or []:
        key = (row["match_key"], row["store_id"])
        if key not in seen:
            seen.add(key)
            pairs.append({"match_key": row["match_key"], "store_id": row["store_id"]})
    return pairs
