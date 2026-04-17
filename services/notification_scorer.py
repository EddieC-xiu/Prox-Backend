# services/notification_scorer.py

import logging
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo
from config.supabase import get_supabase_client

logger = logging.getLogger(__name__)
sb     = get_supabase_client()

# ---------------------------------------------------------------------------
# Scoring constants
# ---------------------------------------------------------------------------

DEAL_SCORE_WEIGHT      = 0.7
RELEVANCE_SCORE_WEIGHT = 0.3

SAVINGS_PCT_WEIGHT     = 0.50
PRICE_DROP_WEIGHT      = 0.30
RETAILER_COUNT_WEIGHT  = 0.20

CATEGORY_MATCH_WEIGHT  = 0.60
HISTORY_MATCH_WEIGHT   = 0.40

NOTIFICATION_THRESHOLD = 55.0

MAX_NOTIFICATIONS_PER_DAY  = 3
MAX_NEW_DEALS_PER_WEEK     = 2
MAX_PRICE_DROP_PER_CYCLE   = 1
MAX_PER_CATEGORY_PER_DAY   = 1
MAX_PER_RETAILER_PER_WEEK  = 1
DEDUP_WINDOW_DAYS          = 7


# ---------------------------------------------------------------------------
# Quiet hours — per user, timezone-aware
# ---------------------------------------------------------------------------

def is_quiet_hours_for_user(
    quiet_start: int,
    quiet_end:   int,
    time_zone:   str | None,
) -> bool:
    try:
        tz = ZoneInfo(time_zone) if time_zone else timezone.utc
    except Exception:
        tz = timezone.utc
    local_hour = datetime.now(tz).hour
    if quiet_start < quiet_end:
        return quiet_start <= local_hour < quiet_end
    else:
        return local_hour >= quiet_start or local_hour < quiet_end


# ---------------------------------------------------------------------------
# Deal score
# ---------------------------------------------------------------------------

def compute_deal_score(
    savings_pct_vs_avg: float,
    retailer_count:     int,
    has_price_drop:     bool,
    price_drop_pct:     float = 0.0,
) -> float:
    savings_component  = min(savings_pct_vs_avg, 100.0) * SAVINGS_PCT_WEIGHT
    drop_component     = (min(price_drop_pct, 100.0) * PRICE_DROP_WEIGHT) if has_price_drop else 0.0
    retailer_component = min(retailer_count / 10.0, 1.0) * 100.0 * RETAILER_COUNT_WEIGHT
    return round(min(savings_component + drop_component + retailer_component, 100.0), 2)


# ---------------------------------------------------------------------------
# Relevance score
# ---------------------------------------------------------------------------

def compute_relevance_score(
    deal_category:    str | None,
    user_categories:  list[str],
    product_name:     str,
    user_history:     list[str],
    deal_brand:       str | None = None,
    preferred_brands: list[str] | None = None,
) -> float:
    category_score = 0.0
    if deal_category and user_categories:
        category_score = 100.0 if deal_category in user_categories else 0.0

    history_score = 0.0
    if user_history and product_name:
        pn = product_name.lower()
        for h in user_history:
            if h.lower() in pn or pn in h.lower():
                history_score = 100.0
                break

    # Brand preference boost
    if not history_score and deal_brand and preferred_brands:
        if deal_brand.lower() in [b.lower() for b in preferred_brands]:
            history_score = 80.0

    return round(
        category_score * CATEGORY_MATCH_WEIGHT + history_score * HISTORY_MATCH_WEIGHT,
        2,
    )


# ---------------------------------------------------------------------------
# Composite score
# ---------------------------------------------------------------------------

def compute_notification_score(deal_score: float, relevance_score: float) -> float:
    return round(
        deal_score * DEAL_SCORE_WEIGHT + relevance_score * RELEVANCE_SCORE_WEIGHT,
        2,
    )


# ---------------------------------------------------------------------------
# Constraint checks
# ---------------------------------------------------------------------------

def _check_constraints(
    user_id:      str,
    product:      str,
    retailer_key: str,
    zip_code:     str,
    cache:        dict,
    trigger_type: str = "unchanged",
) -> tuple[bool, str | None]:
    week_start = datetime.now(timezone.utc).strftime("%Y-W%W")
    today      = datetime.now(timezone.utc).date().isoformat()

    sent_today       = cache.get(f"{user_id}:day:{today}", [])
    sent_this_week_r = cache.get(f"{user_id}:retailer_week:{retailer_key}:{week_start}", [])
    dedup_key        = f"{user_id}:dedup:{product}:{retailer_key}"

    if dedup_key in cache:
        return False, f"dedup: already notified for {product} at {retailer_key} within {DEDUP_WINDOW_DAYS}d"

    if len(sent_today) >= MAX_NOTIFICATIONS_PER_DAY:
        return False, f"daily cap reached ({MAX_NOTIFICATIONS_PER_DAY})"

    if len(sent_this_week_r) >= MAX_PER_RETAILER_PER_WEEK:
        return False, f"retailer weekly cap reached for {retailer_key}"

    if trigger_type == "new_deals":
        sent_new_deals = cache.get(f"{user_id}:new_deals_week:{week_start}", [])
        if len(sent_new_deals) >= MAX_NEW_DEALS_PER_WEEK:
            return False, f"new deals weekly cap reached ({MAX_NEW_DEALS_PER_WEEK})"

    if trigger_type == "drop":
        sent_drops = cache.get(f"{user_id}:drops_cycle:{week_start}", [])
        if len(sent_drops) >= MAX_PRICE_DROP_PER_CYCLE:
            return False, f"price drop cycle cap reached ({MAX_PRICE_DROP_PER_CYCLE})"

    return True, None


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def should_notify(
    user_id:            str,
    product:            str,
    retailer:           str,
    retailer_key:       str,
    zip_code:           str,
    price:              float,
    deal_category:      str | None,
    savings_pct_vs_avg: float,
    retailer_count:     int,
    has_price_drop:     bool,
    price_drop_pct:     float,
    user_categories:    list[str],
    user_history:       list[str] | None = None,
    deal_reason:        str = "",
    trigger_type:       str = "unchanged",
    log_cache:          dict | None = None,
    deal_brand:         str | None = None,
    preferred_brands:   list[str] | None = None,
    user_prefs:         dict | None = None,
    device_row:         dict | None = None,
) -> dict:
    result = {
        "should_send":        False,
        "notification_score": 0.0,
        "deal_score":         0.0,
        "relevance_score":    0.0,
        "deal_reason":        deal_reason,
        "blocked_reason":     None,
    }

    # Gate 1: Quiet hours — per user, timezone-aware
    prefs  = user_prefs or {}
    device = device_row or {}
    if is_quiet_hours_for_user(
        quiet_start = prefs.get("quiet_start", 22),
        quiet_end   = prefs.get("quiet_end", 7),
        time_zone   = device.get("time_zone"),
    ):
        result["blocked_reason"] = "quiet hours"
        return result

    # Gate 2 + 3: Dedup + frequency caps
    cache = log_cache or {}
    passes, reason = _check_constraints(
        user_id, product, retailer_key, zip_code, cache, trigger_type
    )
    if not passes:
        result["blocked_reason"] = reason
        return result

    # Compute scores
    deal_score      = compute_deal_score(savings_pct_vs_avg, retailer_count, has_price_drop, price_drop_pct)
    relevance_score = compute_relevance_score(
        deal_category,
        user_categories,
        product,
        user_history or [],
        deal_brand,
        preferred_brands,
    )
    notif_score = compute_notification_score(deal_score, relevance_score)

    result["deal_score"]         = deal_score
    result["relevance_score"]    = relevance_score
    result["notification_score"] = notif_score

    if notif_score < NOTIFICATION_THRESHOLD:
        result["blocked_reason"] = f"score {notif_score:.1f} below threshold {NOTIFICATION_THRESHOLD}"
        return result

    result["should_send"] = True
    return result


# ---------------------------------------------------------------------------
# Log a sent notification
# ---------------------------------------------------------------------------

def log_notification(
    user_id:              str,
    product:              str,
    retailer:             str,
    retailer_key:         str,
    zip_code:             str,
    price:                float,
    deal_score:           float,
    relevance_score:      float,
    notification_score:   float,
    deal_reason:          str,
    trigger_type:         str = "unchanged",
    dry_run:              bool = False,
) -> None:
    if dry_run:
        return
    try:
        sb.table("notification_log").insert({
            "user_id":             user_id,
            "canonical_product_name": product,
            "retailer":            retailer,
            "retailer_key":        retailer_key,
            "zip_code":            zip_code,
            "price":               price,
            "deal_score":          deal_score,
            "relevance_score":     relevance_score,
            "notification_score":  notification_score,
            "deal_reason":         deal_reason,
            "trigger_type":        trigger_type,
            "sent_at":             datetime.now(timezone.utc).isoformat(),
        }).execute()
    except Exception as e:
        logger.error(f"Failed to log notification: {e}")


# ---------------------------------------------------------------------------
# Preload notification log cache
# ---------------------------------------------------------------------------

def preload_notification_log(user_ids: list[str]) -> dict:
    if not user_ids:
        return {}

    cutoff = (datetime.now(timezone.utc) - timedelta(days=DEDUP_WINDOW_DAYS)).isoformat()

    try:
        res = (
            sb.table("notification_log")
            .select("user_id, canonical_product_name, retailer_key, sent_at, trigger_type")
            .in_("user_id", user_ids)
            .gte("sent_at", cutoff)
            .execute()
        )
        rows = res.data or []
    except Exception as e:
        logger.error(f"Failed to preload notification log: {e}")
        return {}

    cache = {}
    today      = datetime.now(timezone.utc).date().isoformat()
    week_start = datetime.now(timezone.utc).strftime("%Y-W%W")

    for row in rows:
        uid          = row["user_id"]
        product      = row["canonical_product_name"]
        retailer_key = row["retailer_key"]
        ttype        = row.get("trigger_type", "unchanged")

        cache[f"{uid}:dedup:{product}:{retailer_key}"] = True
        cache.setdefault(f"{uid}:day:{today}", []).append(product)
        cache.setdefault(f"{uid}:retailer_week:{retailer_key}:{week_start}", []).append(product)

        if ttype == "new_deals":
            cache.setdefault(f"{uid}:new_deals_week:{week_start}", []).append(product)
        if ttype == "drop":
            cache.setdefault(f"{uid}:drops_cycle:{week_start}", []).append(product)

    logger.info(f"Preloaded notification cache: {len(rows)} log entries for {len(user_ids)} users")
    return cache