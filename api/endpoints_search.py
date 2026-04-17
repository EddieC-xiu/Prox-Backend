# api/endpoints/search.py
from fastapi import APIRouter, Query, HTTPException
from services.deal_location_service import (
    get_deals_near_zip,
    get_map_pins_near_zip,
    get_cart_optimizer_stores,
)

router = APIRouter(prefix="/search", tags=["search"])


def _validate_zip(z: str) -> None:
    if not z or len(z) != 5 or not z.isdigit():
        raise HTTPException(400, "zip_code must be exactly 5 digits")


@router.get("/deals")
def search_deals(
    zip_code:  str          = Query(...,  description="5-digit ZIP"),
    radius:    float        = Query(10.0, ge=0.5, le=50.0),
    retailer:  str | None   = Query(None),
    category:  str | None   = Query(None),
    limit:     int          = Query(100,  ge=1, le=500),
    user_lat:  float | None = Query(None, description="GPS lat — enables zip_multi re-resolution"),
    user_lng:  float | None = Query(None, description="GPS lng — enables zip_multi re-resolution"),
):
    _validate_zip(zip_code)
    deals = get_deals_near_zip(zip_code, radius, retailer, category, limit, user_lat, user_lng)
    return {"zip_code": zip_code, "radius": radius, "count": len(deals), "deals": deals}


@router.get("/map-pins")
def search_map_pins(
    zip_code:  str          = Query(...),
    radius:    float        = Query(10.0, ge=0.5, le=50.0),
    user_lat:  float | None = Query(None),
    user_lng:  float | None = Query(None),
):
    _validate_zip(zip_code)
    pins = get_map_pins_near_zip(zip_code, radius, user_lat, user_lng)
    return {"zip_code": zip_code, "radius": radius, "count": len(pins), "pins": pins}


@router.get("/cart")
def cart_optimizer(
    zip_code:  str          = Query(...),
    radius:    float        = Query(10.0, ge=0.5, le=50.0),
    products:  str          = Query(..., description="Comma-separated: 'milk,bread,eggs'"),
    user_lat:  float | None = Query(None),
    user_lng:  float | None = Query(None),
):
    _validate_zip(zip_code)
    product_list = [p.strip() for p in products.split(",") if p.strip()]
    if not product_list:
        raise HTTPException(400, "Provide at least one product name")
    results = get_cart_optimizer_stores(zip_code, product_list, radius, user_lat, user_lng)
    return {"zip_code": zip_code, "radius": radius, "products": product_list, "stores": results}

