# api/main.py
#
# Prox Backend API
#
# Run with:
#   PYTHONUTF8=1 PYTHONPATH=. uvicorn api.main:app --reload --port 8000

import statistics
from collections import Counter
from fastapi import FastAPI, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from services.cross_retailer_service import (
    compare_product_across_retailers,
    search_products,
)
from services.price_history_service import get_price_history
from config.supabase import get_supabase_client

app = FastAPI(
    title="Prox API",
    description="Cross-retailer grocery price comparison",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

sb = get_supabase_client()

_PRODUCE_KEYWORDS = {
    "grapes", "strawberries", "strawberry", "banana", "bananas",
    "apple", "apples", "orange", "oranges", "tomato", "tomatoes",
    "potato", "potatoes", "onion", "onions", "lettuce", "spinach",
    "blueberries", "blueberry", "mango", "avocado", "lemon", "lemons",
    "lime", "limes", "peach", "peaches", "plum", "plums", "melon",
    "watermelon", "cantaloupe", "pineapple", "plantain", "kiwi",
    "corn", "broccoli", "cauliflower", "celery", "carrot", "carrots",
    "cucumber", "zucchini", "asparagus", "mushroom", "mushrooms",
    "garlic", "ginger", "beet", "beets", "radish", "cabbage",
}

_UNIT_TO_OZ = {
    "oz": 1.0, "fl oz": 1.0, "fl-oz": 1.0, "floz": 1.0,
    "lb": 16.0, "lbs": 16.0, "pound": 16.0, "pounds": 16.0,
    "g": 0.035274, "gram": 0.035274, "grams": 0.035274,
    "ml": 0.033814, "liter": 33.814, "l": 33.814,
}


def _calc_ppu(price: float, amount: str | None, unit: str | None) -> float | None:
    if not amount or not unit:
        return None
    try:
        amt = float(amount)
        if amt <= 0:
            return None
    except (ValueError, TypeError):
        return None
    u = unit.strip().lower().replace(" ", "").replace("-", "").replace(".", "")
    multiplier = _UNIT_TO_OZ.get(u)
    if not multiplier:
        return None
    oz = amt * multiplier
    return round(price / oz, 4) if oz > 0 else None


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/search")
def search(
    q:            str        = Query(..., min_length=2, description="Product search query"),
    limit:        int        = Query(10, ge=1, le=50,   description="Max results"),
    zip_code:     str | None = Query(None,              description="User zip code for local results"),
    radius_miles: float      = Query(25.0, ge=1, le=200, description="Search radius in miles"),
):
    """Search for products by name, optionally filtered by location."""
    try:
        results = search_products(q, limit=limit, zip_code=zip_code, radius_miles=radius_miles)
        return {
            "query":        q,
            "count":        len(results),
            "zip_code":     zip_code,
            "radius_miles": radius_miles if zip_code else None,
            "results":      results,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/compare")
def compare(
    product:      str        = Query(..., min_length=2, description="Canonical product name"),
    brand:        str | None = Query(None,              description="Brand name (optional)"),
    limit:        int        = Query(50, ge=1, le=100,  description="Max retailer rows"),
    zip_code:     str | None = Query(None,              description="User zip code for local results"),
    radius_miles: float      = Query(25.0, ge=1, le=200, description="Search radius in miles"),
    size:         str | None = Query(None,              description="Size key to filter by (e.g. '10.8_oz')"),
):
    """Compare prices for a specific product, optionally filtered by location and size."""
    try:
        result = compare_product_across_retailers(
            product, brand=brand, limit=limit,
            zip_code=zip_code, radius_miles=radius_miles,
            size=size,
        )
        if not result.get("retailers"):
            raise HTTPException(
                status_code=404,
                detail=f"No data found for '{product}'" + (f" by {brand}" if brand else "") +
                       (f" near {zip_code}" if zip_code else ""),
            )
        result["zip_code"]     = zip_code
        result["radius_miles"] = radius_miles if zip_code else None
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/best-deals")
def best_deals(
    limit:         int   = Query(20,   ge=1,  le=100, description="Max deals"),
    min_savings:   float = Query(10.0, ge=0,  le=100, description="Min % below median price"),
    min_retailers: int   = Query(2,    ge=1,          description="Min retailers carrying product"),
    min_days:      int   = Query(3,    ge=1,          description="Min days of price history"),
):
    """Returns best deals using the pre-computed best_deals_comprehensive view."""
    try:
        rows = (
            sb.table("best_deals_comprehensive")
            .select("canonical_product_name, brand, match_key, best_current_price, "
                    "all_time_low, all_time_high, median_price, pct_below_median, "
                    "price_status, composite_score, retailer_count, days_tracked, "
                    "absolute_savings, pct_savings")
            .not_.is_("composite_score", "null")
            .not_.is_("canonical_product_name", "null")
            .gte("retailer_count", min_retailers)
            .gte("days_tracked", min_days)
            .gte("pct_below_median", min_savings)
            .lte("best_current_price", 200)
            .order("composite_score", desc=True)
            .limit(limit)
            .execute()
            .data or []
        )

        deals = []
        for r in rows:
            name = r.get("canonical_product_name") or ""
            if len(name) > 80:
                continue
            name_words = set(name.lower().split())
            if name_words & _PRODUCE_KEYWORDS:
                continue
            deals.append({
                "canonical_product_name": name,
                "brand":              r.get("brand"),
                "match_key":          r.get("match_key"),
                "best_price":         r.get("best_current_price"),
                "all_time_low":       r.get("all_time_low"),
                "median_price":       r.get("median_price"),
                "pct_below_median":   r.get("pct_below_median"),
                "price_status":       r.get("price_status"),
                "composite_score":    r.get("composite_score"),
                "retailer_count":     r.get("retailer_count"),
                "days_tracked":       r.get("days_tracked"),
                "absolute_savings":   r.get("absolute_savings"),
            })

        return {"count": len(deals), "deals": deals}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/retailers")
def retailers():
    """Returns list of retailers and deal counts."""
    try:
        rows = (
            sb.table("flyer_deals")
            .select("retailer")
            .not_.is_("retailer", "null")
            .execute()
            .data or []
        )
        counts = Counter(r["retailer"].strip().lower() for r in rows)
        return {
            "count": len(counts),
            "retailers": [
                {"retailer": k, "deal_count": v}
                for k, v in sorted(counts.items(), key=lambda x: -x[1])
            ],
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/deals/{match_key}")
def deal_details(
    match_key: str,
    zip_code:     str | None = Query(None, description="User zip code for nearby store prices"),
    radius_miles: float      = Query(10.0, ge=1, le=100),
):
    """
    Deal details for a specific product by match_key.
    Returns current deal info, price summary, and nearby store prices.
    Maps to the Deal Details screen in the mobile app.
    """
    try:
        # Get current deals for this match_key
        query = (
            sb.table("flyer_deals")
            .select("match_key, canonical_product_name, product_price, retailer, store_id, coupon_detail, date_added, image_link, category, brand, display_size")
            .eq("match_key", match_key)
            .not_.is_("product_price", "null")
        )
        rows = query.execute().data or []

        if not rows:
            raise HTTPException(status_code=404, detail=f"No deals found for match_key '{match_key}'")

        prices = [float(r["product_price"]) for r in rows if r.get("product_price")]
        if not prices:
            raise HTTPException(status_code=404, detail=f"No prices found for match_key '{match_key}'")

        # If zip_code provided, find deals for this product at nearby stores
        nearby_stores = []
        if zip_code:
            from services.store_distance import get_nearby_stores
            nearby = get_nearby_stores(zip_code, radius_miles)
            if nearby:
                nearby_ids = [s["store_id"] for s in nearby]
                nearby_map = {s["store_id"]: s for s in nearby}
                # Query deals for this specific match_key at nearby stores
                for i in range(0, len(nearby_ids), 200):
                    batch = nearby_ids[i:i+200]
                    res = (
                        sb.table("flyer_deals")
                        .select("store_id, product_price, retailer, coupon_detail")
                        .eq("match_key", match_key)
                        .in_("store_id", batch)
                        .not_.is_("product_price", "null")
                        .execute()
                    )
                    for deal in (res.data or []):
                        sid = deal["store_id"]
                        store = nearby_map.get(sid, {})
                        nearby_stores.append({
                            "retailer":       deal.get("retailer"),
                            "product_price":  float(deal["product_price"]),
                            "coupon_detail":  deal.get("coupon_detail"),
                            "store_id":       sid,
                            "address":        store.get("address"),
                            "city":           store.get("city"),
                            "state":          store.get("state"),
                            "distance_miles": store.get("distance_miles"),
                        })
                nearby_stores.sort(key=lambda x: (x.get("distance_miles") or 999, x.get("product_price") or 999))

        return {
            "match_key":       match_key,
            "canonical_name":  rows[0].get("canonical_product_name"),
            "category":        rows[0].get("category"),
            "brand":           rows[0].get("brand"),
            "display_size":    rows[0].get("display_size"),
            "coupon_detail":   rows[0].get("coupon_detail"),
            "image_url":       rows[0].get("image_link"),
            "price_summary": {
                "min":    min(prices),
                "max":    max(prices),
                "median": round(statistics.median(prices), 2),
            },
            "nearby_stores":      nearby_stores,
            "all_retailer_count": len({r["retailer"] for r in rows if r.get("retailer")}),
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/deals/{match_key}/history")
def deal_history(
    match_key: str,
    store_id:  str | None = Query(None, description="Filter to a specific store_id"),
    days:      int        = Query(90, ge=7, le=365, description="Days of history to return"),
):
    """
    Price history for a product, used to render the price history chart.
    Optionally filtered to a single store.
    """
    try:
        if store_id:
            rows = get_price_history(match_key, store_id, days=days)
        else:
            # Get history across all stores, grouped by date
            since = (__import__("datetime").datetime.now(__import__("datetime").timezone.utc)
                     - __import__("datetime").timedelta(days=days)).isoformat()
            res = (
                sb.table("price_history")
                .select("observed_date, product_price, store_id")
                .eq("match_key", match_key)
                .gte("observed_date", since)
                .order("observed_date", desc=False)
                .execute()
            )
            rows = res.data or []

        if not rows:
            raise HTTPException(status_code=404, detail=f"No price history for '{match_key}'")

        # Group by date, take min price per day (best available price)
        by_date: dict[str, list[float]] = {}
        for r in rows:
            day = (r.get("observed_date") or r.get("observed_at", ""))[:10]
            try:
                by_date.setdefault(day, []).append(float(r["product_price"]))
            except (ValueError, TypeError):
                pass

        history = [
            {"date": day, "min_price": min(prices), "max_price": max(prices)}
            for day, prices in sorted(by_date.items())
        ]

        all_prices = [p for prices in by_date.values() for p in prices]
        return {
            "match_key":    match_key,
            "store_id":     store_id,
            "days":         days,
            "data_points":  len(history),
            "all_time_low": min(all_prices),
            "all_time_high": max(all_prices),
            "history":      history,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))