# api/main.py
#
# Prox Backend API
#
# Run with:
#   PYTHONUTF8=1 PYTHONPATH=. uvicorn api.main:app --reload --port 8000

import statistics
from collections import defaultdict, Counter
from fastapi import FastAPI, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from services.cross_retailer_service import (
    compare_product_across_retailers,
    search_products,
    normalize_retailer,
)
from scoring.product_normalizer import build_canonical_name
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
    min_savings:   float = Query(15.0, ge=0,  le=100, description="Min % savings"),
    min_retailers: int   = Query(2,    ge=2,          description="Min retailers carrying product"),
):
    """Returns products with the highest savings potential across retailers."""
    try:
        rows = []
        offset = 0
        batch = 1000
        while True:
            batch_rows = (
                sb.table("test_flyer_deals_duplicate")
                .select("canonical_product_name, brand, product_price, retailer, base_amount, base_unit")
                .not_.is_("canonical_product_name", "null")
                .not_.is_("product_price", "null")
                .range(offset, offset + batch - 1)
                .execute()
                .data or []
            )
            rows.extend(batch_rows)
            if len(batch_rows) < batch:
                break
            offset += batch

        products: dict[tuple, dict] = defaultdict(lambda: {
            "prices": [], "ppus": [], "retailers": set()
        })

        for row in rows:
            raw   = row["canonical_product_name"] or ""
            brand = row.get("brand")
            key   = (raw, brand)
            try:
                price = float(row["product_price"])
                if price <= 0:
                    continue
            except (TypeError, ValueError):
                continue

            ppu = _calc_ppu(price, row.get("base_amount"), row.get("base_unit"))

            products[key]["prices"].append(price)
            if ppu:
                products[key]["ppus"].append(ppu)
            products[key]["retailers"].add(
                normalize_retailer((row.get("retailer") or "").lower())
            )

        deals = []
        for (name, brand), data in products.items():
            if len(data["retailers"]) < min_retailers:
                continue

            # Filter produce — not meaningful to compare by price
            name_words = set(name.lower().split())
            if name_words & _PRODUCE_KEYWORDS:
                continue

            # Filter long scraper artifact names
            if len(name) > 80:
                continue

            prices = data["prices"]
            ppus   = data["ppus"]

            # Outlier filter on prices
            if len(prices) >= 3:
                med    = statistics.median(prices)
                prices = [p for p in prices if p <= med * 2.0]
            if not prices:
                continue

            min_p = min(prices)
            max_p = max(prices)
            if max_p == 0:
                continue

            # Use PPU savings if available (more accurate for multi-size products)
            # This prevents bulk water at 87% savings from misleading users
            if len(ppus) >= 2:
                ppus_filtered = ppus
                if len(ppus) >= 3:
                    med_ppu      = statistics.median(ppus)
                    ppus_filtered = [p for p in ppus if p <= med_ppu * 2.0]
                if ppus_filtered:
                    min_ppu     = min(ppus_filtered)
                    max_ppu     = max(ppus_filtered)
                    savings_pct = round(((max_ppu - min_ppu) / max_ppu) * 100, 1) if max_ppu else 0
                    best_ppu    = round(min_ppu, 4)
                else:
                    savings_pct = round(((max_p - min_p) / max_p) * 100, 1)
                    best_ppu    = None
            else:
                savings_pct = round(((max_p - min_p) / max_p) * 100, 1)
                best_ppu    = None

            if savings_pct < min_savings:
                continue

            deals.append({
                "canonical_product_name": name,
                "brand":                  brand,
                "min_price":              min_p,
                "max_price":              max_p,
                "avg_price":              round(sum(prices) / len(prices), 2),
                "best_price_per_oz":      best_ppu,
                "savings_pct_vs_max":     savings_pct,
                "absolute_savings":       round(max_p - min_p, 2),
                "retailer_count":         len(data["retailers"]),
                "popularity_score":       len(prices),
            })

        deals.sort(key=lambda d: (-d["retailer_count"], -d["savings_pct_vs_max"]))
        return {"count": len(deals[:limit]), "deals": deals[:limit]}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/retailers")
def retailers():
    """Returns list of retailers and deal counts."""
    try:
        rows = (
            sb.table("test_flyer_deals_duplicate")
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