# Kroger Cart-Fill Workflow (MVP)

Implements the workflow Edmond scoped for Alston: connect a user's Kroger
account via OAuth, resolve Prox basket items to Kroger UPCs, and add them to the
user's real Kroger cart. The user completes checkout on Kroger.

This is built as a **local demo first**; it does **not** touch production
Supabase. Token storage defaults to a local JSON file. A Supabase migration is
included but **not applied**; flip one env var to go live later.

---

## What was added

| File | Purpose |
|---|---|
| `services/kroger_service.py` | Core: OAuth URL, token exchange/refresh, product-to-UPC search, cart add |
| `services/kroger_token_store.py` | Pluggable token storage: local JSON (demo) or Supabase (later) |
| `api/kroger.py` | FastAPI routes (`/kroger/...`) |
| `api/main.py` | Wires the Kroger router into the app (2 lines) |
| `migrations/006_create_kroger_tokens.sql` | Token table - **not applied yet** |

## Endpoints

| Method | Route | What it does |
|---|---|---|
| GET | `/kroger/auth/login?user_id=demo` | Redirects the user to Kroger login |
| GET | `/kroger/auth/callback?code=&state=` | Kroger redirects back; we store the token |
| GET | `/kroger/status?user_id=demo` | Is this user connected? |
| GET | `/kroger/products/search?term=milk` | Product-to-UPC lookup (no login needed) |
| POST | `/kroger/cart/add` | Resolve UPCs + add to the user's Kroger cart |
| DELETE | `/kroger/disconnect?user_id=demo` | Forget a user's token |

---

## Setup

1. Add to `.env` (the secret you already have for the store-location scripts):
   ```
   KROGER_CLIENT_ID=proxgrocerysavings-bbcdkn5r
   KROGER_CLIENT_SECRET=<your secret>
   KROGER_REDIRECT_URI=http://localhost:8000/kroger/auth/callback
   # optional:
   # KROGER_TOKEN_STORE=local        # local (default) | supabase
   # KROGER_DEFAULT_MODALITY=PICKUP  # PICKUP | DELIVERY
   ```

2. In the **Kroger developer portal**, on the Prox app (one-time, only you can do this):
   - Enable scope **`cart.basic:write`** (product scope you already have).
   - Register the redirect URI **exactly**: `http://localhost:8000/kroger/auth/callback`.

3. Run the API:
   ```bash
   PYTHONUTF8=1 PYTHONPATH=. uvicorn api.main:app --reload --port 8000
   ```

---

## Demo script for Alston (5 minutes)

**Part A - product-to-UPC (works today, no login):**
```bash
curl "http://localhost:8000/kroger/products/search?term=milk"
```
Shows real Kroger products with UPCs and prices. This proves we can turn a Prox
basket item into a buyable Kroger identifier.

**Part B - connect a Kroger account (needs step 2 above):**
Open in a browser:
```
http://localhost:8000/kroger/auth/login?user_id=demo
```
Log into Kroger, then you're redirected back to a connected page. Verify:
```bash
curl "http://localhost:8000/kroger/status?user_id=demo"
```

**Part C - fill the cart:**
```bash
curl -X POST "http://localhost:8000/kroger/cart/add" \
  -H "Content-Type: application/json" \
  -d '{"user_id":"demo","items":[{"term":"milk","quantity":1},{"term":"eggs","quantity":2}]}'
```
Open the Kroger app/site for that account; the items are in the cart. Response
also lists any items it couldn't match under `unresolved` (no silent drops).

---

## Going live later (after approval)

1. Apply `migrations/006_create_kroger_tokens.sql` to Supabase.
2. Set `KROGER_TOKEN_STORE=supabase`.
3. Set `KROGER_REDIRECT_URI` to the deployed callback URL and register it in the
   Kroger portal.

No code changes needed; only env + the migration.

---

## Honest limitations / notes

- **Checkout still happens on Kroger.** This adds items to the user's Kroger
  cart; Prox does not take payment. (No US grocer offers in-app payment checkout.)
- **Kroger only.** Same-family banners (Ralphs, Food 4 Less) are covered; other
  retailers need their own integration or an aggregator (e.g. Instacart).
- **UPC match quality** depends on Kroger product search. Passing a `location_id`
  improves store-specific accuracy; `resolve_upc` currently takes the best
  in-stock candidate. For checkout we may later want a confidence threshold
  (tie into Kiran's match work) before auto-adding.
- **`user_id`** in the demo is whatever you pass; in production wire it to the
  authenticated Prox user.
- The local token file `.kroger_tokens.json` holds real tokens; it is
  gitignored. Treat it like a secret.
