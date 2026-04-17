import logging
from datetime import date, timedelta
from config.supabase import get_supabase_client

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

SCORE_TABLE   = "score_snapshot"
DELTA_TABLE   = "deal_delta"
HISTORY_TABLE = "price_history"
BATCH_SIZE    = 500

W_PCT = 0.50
W_ABS = 0.25
W_VEL = 0.15
W_POP = 0.10

MAX_PCT_SAVINGS = 50.0
MAX_ABS_SAVINGS = 10.0
MAX_VELOCITY    = 10.0


def compute_composite(pct_savings: float, absolute_savings: float,
                       velocity: float, popularity: int = 0) -> float:
    pct_score = min(max(pct_savings, 0) / MAX_PCT_SAVINGS, 1.0)
    abs_score = min(max(absolute_savings, 0) / MAX_ABS_SAVINGS, 1.0)
    vel_score = 1.0 - min(velocity / MAX_VELOCITY, 1.0)
    pop_score = min(popularity / 100.0, 1.0)
    return round((W_PCT * pct_score + W_ABS * abs_score +
                  W_VEL * vel_score + W_POP * pop_score) * 100, 2)


def get_deal_velocity(match_key: str, store_id: str, days: int = 30) -> float:
    client = get_supabase_client()
    since  = (date.today() - timedelta(days=days)).isoformat()
    res    = client.table(HISTORY_TABLE)\
        .select("observed_date, product_price")\
        .eq("match_key", match_key)\
        .eq("store_id", store_id)\
        .gte("observed_date", since)\
        .order("observed_date")\
        .execute()
    rows = res.data or []
    if len(rows) < 2:
        return 0.0
    changes = sum(
        1 for i in range(1, len(rows))
        if rows[i]["product_price"] != rows[i - 1]["product_price"]
    )
    return round(changes / (days / 30), 2)


def run():
    client = get_supabase_client()
    res    = client.table(DELTA_TABLE)\
        .select("*")\
        .in_("delta_type", ["drop", "new"])\
        .execute()
    deltas = res.data or []
    logger.info(f"Scoring {len(deltas)} rows (drop + new)")

    # Preload canonical names + brand from price_history
    match_keys = list(set(d["match_key"] for d in deltas))
    ph_res = client.table(HISTORY_TABLE)\
        .select("match_key, canonical_product_name, brand")\
        .in_("match_key", match_keys)\
        .execute()
    ph_lookup = {r["match_key"]: r for r in (ph_res.data or [])}

    to_write = []
    for i, delta in enumerate(deltas):
        match_key   = delta["match_key"]
        store_id    = delta["store_id"]
        ph_row      = ph_lookup.get(match_key, {})
        pct_savings = abs(delta.get("price_change_pct") or 0)
        abs_savings = max(delta.get("absolute_savings") or 0, 0)
        velocity    = get_deal_velocity(match_key, store_id)

        to_write.append({
            "match_key":              match_key,
            "store_id":               store_id,
            "flyer_id":               delta.get("flyer_id"),
            "product_price":          delta.get("current_price"),
            "canonical_product_name": ph_row.get("canonical_product_name"),
            "brand":                  ph_row.get("brand"),
            "pct_savings":            round(pct_savings, 2),
            "absolute_savings":       round(abs_savings, 2),
            "deal_velocity":          velocity,
            "composite_score":        compute_composite(pct_savings, abs_savings, velocity),
        })

        if (i + 1) % 500 == 0:
            logger.info(f"  Scored {i + 1}/{len(deltas)}")

    logger.info(f"Writing {len(to_write)} rows to score_snapshot...")
    for i in range(0, len(to_write), BATCH_SIZE):
        batch = to_write[i:i + BATCH_SIZE]
        client.table(SCORE_TABLE)\
            .upsert(batch, on_conflict="match_key,store_id,flyer_id")\
            .execute()

    top = sorted(to_write, key=lambda r: r["composite_score"], reverse=True)[:10]
    print("\n── Top 10 Deals ────────────────────────────────────")
    for r in top:
        print(f"  score={r['composite_score']:>6.2f}  "
              f"save={r['pct_savings']:>5.1f}%  "
              f"${r['absolute_savings']:.2f}  "
              f"{r.get('canonical_product_name') or r['match_key']}")
    logger.info("deal_scorer complete.")


if __name__ == "__main__":
    run()