# prox-backend-sai

Backend engineering internship project — Prox grocery price intelligence platform.

Phases 2 and 3 complete. Phase 4 (push notification intelligence) in design. Phase 5 (store location data quality) in progress.

---

## System Architecture

```
Scraper (external)
    ↓
test_flyer_deals_duplicate    ← raw flyer deal rows
    ↓
Canonicalization Pipeline     ← product name normalization, brand detection
    ↓
Store Matching Pipeline       ← retailer → store_locations (lat/lon)
    ↓
Price History Pipeline        ← price_history, deal_delta, score_snapshot
    ↓
FastAPI (api/main.py)         ← /search, /compare, /best-deals, /retailers
    ↓
index.html                    ← validation UI
```

---

## Data Flow

### 1. Raw Data Ingestion
Flyer deal data lands in `test_flyer_deals_duplicate` (45,905 rows). Each row represents one product deal at one retailer with a zip code, price, and product name.

### 2. Canonicalization
`scoring/product_normalizer.py` normalizes raw product names into canonical names for cross-retailer comparison. Handles:
- Brand stripping from product names
- Size/weight extraction into `base_amount` + `base_unit`
- Word order normalization
- Bulk description truncation
- Price stripping from names

Run:
```bash
PYTHONUTF8=1 PYTHONPATH=. python scripts/recanonicalize.py
```

### 3. Brand Detection
`scoring/product_normalizer.py` contains 300+ known brands in `KNOWN_BRANDS`. Apostrophe normalization handled via `_KNOWN_BRANDS_NORMALIZED`.

Coverage: 72.4% of rows have brand detected.
Remaining 27.6% are store brands or unknown — Charlotte Qin's ML pipeline (`brand_confidence`, `category_confidence`, `is_store_brand`) will cover these once integrated.

Run:
```bash
PYTHONUTF8=1 PYTHONPATH=. python scripts/backfill_brands.py
```

### 4. Store Matching
`services/store_matching.py` matches each `retailer` string to a row in `store_locations` (39,358+ rows with real lat/lon from OpenStreetMap).

Match priority:
1. `retailer_key` + `zip_code`, single result → `zip_single`
2. `retailer_key` + `zip_code`, multiple results → `zip_multi` (closest by Haversine)
3. Geocode + create new store row → `created`

Match rate: **98.0%** (up from 91.7% at phase start).

Remaining 2%:
- Dollar Tree: 173 rows, zero OSM data — on roadmap
- Non-grocery (Ulta, PetSmart, Petco, Sally Beauty): in DB, included in system
- Very small regional chains: no OSM presence

Run:
```bash
PYTHONUTF8=1 PYTHONPATH=. python scripts/backfill_store_matching.py
```

To import new retailers from OpenStreetMap:
```bash
PYTHONUTF8=1 PYTHONPATH=. python scripts/import_unmatched_retailers.py
```

### 5. Price History Pipeline
Three tables track price movement over time:

- `price_history` (26,415 rows) — one row per `match_key` per `observed_at` date. `match_key` = `canonical_product_name|brand|retailer_key|zip_code`
- `deal_delta` — compares latest price to previous. `delta_type`: `drop`, `rise`, `new`, `unchanged`
- `score_snapshot` — scored deals based on delta type. Populates once multiple days of data accumulate

Run in order:
```bash
PYTHONUTF8=1 PYTHONPATH=. python scripts/backfill_price_history.py
PYTHONUTF8=1 PYTHONPATH=. python scripts/run_deal_delta.py
PYTHONUTF8=1 PYTHONPATH=. python scripts/run_scorer.py
```

---

## Key Assumptions and Tradeoffs

### Size Matching
Two modes activate automatically in `services/cross_retailer_service.py`:

**Exact size mode** — activates when product has one valid size tier or user selects a specific size. Only retailers carrying that exact `base_amount + base_unit` are shown. Zero mixing of different pack types.

**Price-per-oz (PPU) mode** — activates automatically when a product has multiple valid size tiers with convertible units (oz, lb, ml, etc.). All retailers across all sizes shown, ranked by $/oz. Deal quality ratings based on $/oz vs average $/oz, not absolute price.

Size coverage by category:
| Category | Coverage |
|---|---|
| Snacks | 97.0% |
| Frozen | 96.5% |
| Baby | 96.7% |
| Beverages | 95.2% |
| Bakery | 95.5% |
| Pantry | 93.9% |
| Meat | 73.3% |
| Pet | 59.4% |

For the 10.9% without size data (mostly Costco bulk and produce), fallback is a 2x median outlier filter.

### Geography Filtering
Haversine distance math against real store lat/lon from `store_locations`. Not zip code matching. A store 24 miles away in a different zip appears in a 25mi search; one 26 miles away doesn't.

Falls back to `zip_centroids` if store not in `store_locations`.

Data coverage: 47 zip codes across 7 states (22 in California). Users outside covered markets will see thin local results — this is a scraper coverage issue, not an infrastructure issue.

### Deal Quality Ratings
- `great` — 15%+ below average
- `good` — 5-15% below average
- `fair` — within 5% of average
- `expensive` — 5%+ above average

In PPU mode, ratings are based on $/oz vs average $/oz, not absolute price.

---

## API Reference

### GET /search
Search for products by name, optionally filtered by location.

```
GET /search?q=cheerios&limit=10&zip_code=92377&radius_miles=25
```

Response:
```json
{
  "query": "cheerios",
  "count": 5,
  "zip_code": "92377",
  "radius_miles": 25.0,
  "results": [
    {
      "canonical_product_name": "cheerios honey nut",
      "brand": "general mills",
      "retailer_count": 7,
      "min_price": 2.89,
      "max_price": 3.49,
      "avg_price": 3.16
    }
  ]
}
```

### GET /compare
Compare prices for a specific product across retailers, optionally filtered by location and size.

```
GET /compare?product=sour+cream&brand=daisy&zip_code=92377&radius_miles=25&size=16.0_oz
```

Response fields:
| Field | Description |
|---|---|
| `product` | Canonical product name |
| `brand` | Brand name |
| `size` | Active size (null in PPU mode) |
| `compare_mode` | `exact_size` or `price_per_oz` |
| `compare_summary` | Plain-language explanation of the comparison |
| `available_sizes` | All valid size tiers with retailer counts |
| `best_price_per_oz` | Lowest $/oz across all retailers |
| `retailer_count` | Number of retailers in comparison |
| `min_price` | Best price |
| `max_price` | Worst price |
| `avg_price` | Average price |
| `savings_vs_max` | Absolute savings vs worst price |
| `savings_pct_vs_max` | % savings vs worst price |
| `best_retailer` | Retailer with best price/value |
| `retailers` | Array of retailer rows (see below) |

Retailer row fields:
| Field | Description |
|---|---|
| `retailer` | Display name |
| `price` | Actual price |
| `size` | Size at this retailer |
| `price_per_oz` | $/oz (null if unit not convertible) |
| `vs_avg` | $ difference from average |
| `vs_avg_pct` | % difference from average (based on $/oz in PPU mode) |
| `deal_quality` | `great`, `good`, `fair`, or `expensive` |
| `deal_reason` | Plain-language explanation e.g. "Best value — 45% below average price per oz across 11 retailers" |
| `zip_code` | Store zip code |
| `store_id` | FK to `store_locations` |

### GET /best-deals
Products with highest savings potential across retailers.

```
GET /best-deals?min_savings=15&min_retailers=3&limit=20
```

### GET /health
API health check. Returns `{"status": "ok"}`.

### GET /retailers
All retailers with deal counts.

---

## Database Tables

| Table | Rows | Description |
|---|---|---|
| `test_flyer_deals_duplicate` | 45,905 | Raw flyer deals — source of truth |
| `store_locations` | 54,848+ | Retailer locations with lat/lon |
| `zip_centroids` | ~33,000 | Zip code center coordinates |
| `price_history` | 26,415 | Price observations over time |
| `deal_delta` | 406 | Price movement between observations |
| `score_snapshot` | 0 | Scored deals (populates with recurring data) |
| `waitlist` | ~30 | Waitlist signups with zip codes |

---

## Running the Pipeline End to End

Full reset and rebuild sequence:
```bash
# 1. Canonicalize all product names
PYTHONUTF8=1 PYTHONPATH=. python scripts/recanonicalize.py

# 2. Backfill brand detection
PYTHONUTF8=1 PYTHONPATH=. python scripts/backfill_brands.py

# 3. Import new OSM store locations
PYTHONUTF8=1 PYTHONPATH=. python scripts/import_unmatched_retailers.py

# 4. Match deals to store locations
PYTHONUTF8=1 PYTHONPATH=. python scripts/backfill_store_matching.py

# 5. Build price history
PYTHONUTF8=1 PYTHONPATH=. python scripts/backfill_price_history.py

# 6. Compute deal deltas
PYTHONUTF8=1 PYTHONPATH=. python scripts/run_deal_delta.py

# 7. Score deals
PYTHONUTF8=1 PYTHONPATH=. python scripts/run_scorer.py

# 8. Start API server
PYTHONUTF8=1 PYTHONPATH=. uvicorn api.main:app --reload --port 8000
```

---

## Key Files

| File | Purpose |
|---|---|
| `api/main.py` | FastAPI endpoints |
| `services/cross_retailer_service.py` | Core compare logic, size matching, PPU mode, geography filtering |
| `services/store_matching.py` | Retailer alias table, store matching logic |
| `scoring/product_normalizer.py` | Canonical name builder, brand detection |
| `scripts/backfill_brands.py` | Brand detection backfill |
| `scripts/backfill_store_matching.py` | Store matching backfill |
| `scripts/import_unmatched_retailers.py` | OSM store location import |
| `scripts/backfill_price_history.py` | Price history backfill |
| `scripts/run_deal_delta.py` | Deal delta computation |
| `scripts/run_scorer.py` | Deal scoring |
| `scripts/recanonicalize.py` | Re-run canonicalization |
| `index.html` | Validation UI |
| `config/supabase.py` | Supabase client config |

---

## Phase Status

| Phase | Status | Notes |
|---|---|---|
| Phase 1 — Data ingestion | ✅ Complete | Raw data in Supabase |
| Phase 2 — Canonicalization + matching | ✅ Complete | 98% store match, 72.4% brand coverage |
| Phase 3 — Compare engine + API | ✅ Complete | Size matching, PPU mode, geography, explainability |
| Phase 4 — Push notification intelligence | 🔄 In design | Scoring model outlined, ready for implementation |
| Phase 5 — Store location data quality | 🔄 In progress | See section below |

---

## Phase 5: Store Location Data Quality Audit

### Overview

The `store_locations` table is the backbone of the `/compare` endpoint's geography filtering. Every retailer row shown in a price comparison is linked to a specific `store_locations` entry with real lat/lon coordinates. Entries with `geocode_confidence IN ('zip_centroid', 'zip')` are excluded from the cache and treated as placeholders only.

This phase audited all 54,848 store_locations rows across 213 distinct retailers (as seen in `test_flyer_deals_duplicate`), identified bad/missing GPS data, and fixed it.

### How Store Location Lookup Works

`services/cross_retailer_service.py` loads all non-centroid store locations into an in-memory dict at startup via `_load_store_locations()`. The cache is keyed by `(retailer_key, zip_key)` where:
- `zip_key = zip_code` if the entry has a zip code
- `zip_key = f"_geo_{lat:.4f}_{lng:.4f}"` if zip is NULL (e.g., Trader Joe's OSM entries)

When `/compare` is called with a user lat/lng, `_get_store_info(retailer_key, user_lat, user_lng)` scans all non-centroid entries for that retailer and returns the nearest store by Haversine distance. This is the primary path for accurate map pins.

### Critical Bug Fixed: Trader Joe's 634 Entries Collapsing

All 634 `trader_joes` OSM entries had `zip_code = NULL`. Before the fix, all 634 were keyed as `("trader_joes", "")` — only the last one survived in the dict. After the fix (commit `b4df9a1`), each entry gets a unique lat/lng-based key. The cache grew from 76,851 → 78,494 entries.

### Bad Geography Data Neutralized

Several retailers had entries in geographically impossible locations (NE/NYC-only chains appearing in CA, WA, FL; Canadian addresses). These were set to `lat=NULL, lng=NULL, geocode_confidence='zip_centroid'` to exclude them from the cache. Deletion is blocked by FK constraint (`flyer_deals.store_id` references `store_locations.id`).

| Retailer | Entry IDs | Problem | Action |
|---|---|---|---|
| Stop & Shop | 23666, 23472, 23504 | CA, WA, BC Canada (NE chain only) | Neutralized |
| Key Food | 70663–70672 | FL, MI, OH (NYC chain only) | Neutralized |
| Western Beef | 63917 | Ottawa, Canada (NYC chain only) | Neutralized |
| ShopRite | 22710 | Oakland CA (NE chain only) | Neutralized |

### Kroger Company in California

Initially neutralized 4 Kroger CA entries thinking Kroger doesn't operate in CA. Restored after confirming Kroger Company operates Ralphs (295 stores), Food4Less, and FoodsCo in California.

| ID | Location | Status |
|---|---|---|
| 4618 | Studio City CA | Restored (lat=34.1440673, lng=-118.4131366) |
| 4639 | Torrance CA | Restored (lat=33.8300147, lng=-118.3109876) |
| 4699 | Los Angeles CA | Restored (lat=34.0350253, lng=-118.4492796) |
| 4608 | Ventura CA | Restored (lat=34.2580358, lng=-119.208935) |

### GPS Coverage by Retailer (Post-Fixes)

| Retailer Key | Total Rows | Real GPS | Notes |
|---|---|---|---|
| walmart | 4174 | 4060 | ✅ |
| kroger | 4212 | 4193 | ✅ Includes CA (Ralphs/Food4Less/FoodsCo banner) |
| target | 1997 | 1907 | ✅ |
| aldi | 2409 | 2318 | ✅ |
| cvs | 5365+ | 5098+ | ✅ |
| publix | 970 | 953 | ✅ |
| traderjoes | 634 (trader_joes) + 654 (traderjoes) | 569+ | ✅ Collapse bug fixed |
| food4less | 156 | 117 | ✅ 75% coverage |
| hmart | 187 | 138 | ✅ 74% coverage |
| vallarta | 73 | 41 | ✅ 56% coverage |
| giantfood | 65 | 49 | ✅ 75% coverage |
| gelsons | 45 | 19 | ✅ OSM re-import added 3 entries |
| northgate | 54 | 26 | 48% coverage, OSM limited |
| superiorgrocers | 41 | 12 | 29% — OSM has limited data for this chain |
| bristolfarms | 35 | 7 | Only ~12 actual locations, 7 in OSM |
| restaurantdepot | 100 | 28 | OSM re-import added 2 entries |
| erewhon | 17 | 7 | ~8 total locations, 7 in OSM |

### Retailer Alias System

`services/store_matching.py:RETAILER_ALIASES` maps display names to `retailer_key` values. Some notable mappings relevant to the data:

- `FoodsCo`, `FoodMaxx` → `kroger` (Kroger CA brands — share kroger GPS)
- `Ralphs Delivery Now`, `Kroger Delivery Now`, `ALDI Express` → parent brand key
- All delivery/express variants strip suffix and resolve to parent
- `CVS®` → `cvs` (encoding variants)

### Centroid Entries and the Nearest-Store Fallback

Many entries in `store_locations` have `geocode_confidence = 'zip_centroid'` — these have real lat/lon (the geographic center of the zip code area) but are excluded from the compare engine cache because they represent guesses, not actual store coordinates.

When `_get_store_info` can't find an exact zip match in the cache, it falls back to scanning all real-GPS entries for that retailer and returning the nearest by Haversine distance. So even if a retailer has 30 centroid entries and only 7 real ones, a user in that area will still get a real store location — the nearest of the 7.

The remaining centroid entries are not a blocker. They represent deals scraped at those zip codes where no OSM store data exists for that exact zip. The system handles this gracefully via nearest-store fallback.

### Scripts Written This Phase

| Script | Purpose |
|---|---|
| `scripts/audit_store_locations.py` | Full table audit — counts per retailer_key, confidence breakdown |
| `scripts/fix_bad_store_data.py` | Neutralized wrong-geography entries (Stop & Shop CA, Key Food FL/MI, etc.) |
| `scripts/fix_kroger_ca.py` | Initial (incorrect) neutralization of Kroger CA — superseded by restore |
| `scripts/restore_kroger_ca.py` | Restored Kroger CA entries after confirming Ralphs/Food4Less/FoodsCo are Kroger |
| `scripts/fix_centroid_gps.py` | Re-imported OSM data for Bristol Farms, Gelson's, Superior Grocers, Northgate, Restaurant Depot, Erewhon |
| `scripts/full_retailer_audit.py` | Cross-reference all 213 retailers in flyer_deals vs store_locations GPS coverage |
| `scripts/check_problem_retailers.py` | Detailed per-retailer check for specific chains with coverage issues |
| `scripts/test_store_resolution.py` | End-to-end test of `_get_store_info` for 40+ retailers near LA |

### How to Continue This Work

**To check coverage for any retailer:**
```python
# In check_problem_retailers.py — add the retailer_key to check()
check("retailer_key_here", "Display Name")
```

**To re-run the full coverage audit:**
```bash
PYTHONUTF8=1 PYTHONPATH=. python scripts/full_retailer_audit.py
```

**To import OSM data for a new retailer:**
1. Add to `IMPORT_TARGETS` in `scripts/import_unmatched_retailers.py`
2. Add to `RETAILER_ALIASES` and `_LOADED_RETAILERS` in `services/store_matching.py`
3. Run: `PYTHONUTF8=1 PYTHONPATH=. python scripts/import_unmatched_retailers.py`

**To fix centroid-heavy retailers with poor OSM coverage** (Superior Grocers, Northgate Market):
These chains have ~80+ physical locations but only 12-26 in OSM. Alternative data sources:
- Company's store finder page (scrape and import manually)
- Google Places API (paid)
- Overpass with broader name matching: try partial name, e.g. `"Superior"` or `"Northgate"`

**To reload the cache after any data changes:**
```
POST https://prox-api-production.up.railway.app/admin/reload-cache
```
Or the app auto-reloads on Railway deploy.

### Priority Remaining Work

1. **Superior Grocers** (12/41 real GPS) — ~80 CA locations, OSM only has 12. Consider scraping their store finder at `superiorgrocers.com`.
2. **Northgate Market** (26/54 real GPS) — ~40 SoCal locations. Try broader OSM query `"Northgate"`.
3. **Bristol Farms** (7/35 real GPS) — only ~12 actual stores exist, 7 in OSM. The 28 centroid rows are phantom entries from deals matched to area zip codes without real stores. Low priority.
4. **Rouses Markets** (1/1 real GPS) — Gulf Coast chain. Needs OSM import.

---

## Pending Dependencies

- **Charlotte Qin brand pipeline** — ML-based brand/category classification with `brand_confidence`, `category_confidence`, `is_store_brand` columns. 8,870/45,905 rows processed. Integration pending coordination.
- **Scraper size coverage** — `base_amount`/`base_unit` populated by scraper at collection time. 89.1% coverage on packaged goods. Remaining 10.9% mostly Costco bulk and produce.
- **Dollar Tree store locations** — Zero rows in OSM. On roadmap for alternative data source.
- **Recurring scraper runs** — `score_snapshot` and meaningful `deal_delta` data requires multiple days of price history. Currently one day of data.
