import logging
from collections import Counter
from services.price_history_service import (
    get_all_match_key_store_pairs,
    get_latest_price,
    get_baseline_price,
)
from config.supabase import get_supabase_client

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

TABLE          = "deal_delta"
BATCH_SIZE     = 500
BASELINE_DAYS  = 90
DROP_THRESHOLD = 2.0

def classify_delta(current: float, baseline: float) -> tuple[str, float, float]:
    if baseline == 0:
        return "unchanged", 0.0, 0.0
    change_pct = (current - baseline) / baseline * 100
    savings    = round(baseline - current, 2)
    if change_pct < -DROP_THRESHOLD:
        delta_type = "drop"
    elif change_pct > DROP_THRESHOLD:
        delta_type = "rise"
    else:
        delta_type = "unchanged"
    return delta_type, round(change_pct, 2), savings

def run():
    client = get_supabase_client()
    pairs  = get_all_match_key_store_pairs()
    logger.info(f"Processing {len(pairs)} (match_key, store_id) pairs")

    to_write, processed = [], 0

    for pair in pairs:
        match_key = pair["match_key"]
        store_id  = pair["store_id"]

        latest = get_latest_price(match_key, store_id)
        if not latest:
            continue

        baseline = get_baseline_price(match_key, store_id, days=BASELINE_DAYS)
        if baseline is None:
            to_write.append({
                "match_key":        match_key,
                "store_id":         store_id,
                "flyer_id":         latest.get("flyer_id"),
                "current_price":    float(latest["product_price"]),
                "baseline_price":   float(latest["product_price"]),
                "price_change_pct": 0.0,
                "absolute_savings": 0.0,
                "delta_type":       "new",
            })
            continue

        current_price                   = float(latest["product_price"])
        delta_type, change_pct, savings = classify_delta(current_price, baseline)

        to_write.append({
            "match_key":        match_key,
            "store_id":         store_id,
            "flyer_id":         latest.get("flyer_id"),
            "current_price":    current_price,
            "baseline_price":   baseline,
            "price_change_pct": change_pct,
            "absolute_savings": savings,
            "delta_type":       delta_type,
        })

        processed += 1
        if processed % 500 == 0:
            logger.info(f"  Processed {processed}/{len(pairs)}")

    logger.info(f"Writing {len(to_write)} rows to deal_delta...")

    for i in range(0, len(to_write), BATCH_SIZE):
        batch = to_write[i:i + BATCH_SIZE]
        client.table(TABLE)\
            .upsert(batch, on_conflict="match_key,store_id,flyer_id")\
            .execute()

    counts = Counter(r["delta_type"] for r in to_write)
    drops  = [r for r in to_write if r["delta_type"] == "drop"]

    print("\n── Deal Delta Summary ──────────────────────────────")
    for k, v in sorted(counts.items()):
        print(f"  {k:<12} {v:>6} rows")
    if drops:
        avg = sum(r["absolute_savings"] for r in drops) / len(drops)
        print(f"\n  Avg savings on drops: ${avg:.2f}")
    print()
    logger.info("deal_delta_job complete.")

if __name__ == "__main__":
    run()