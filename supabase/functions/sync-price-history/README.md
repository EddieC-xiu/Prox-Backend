# sync-price-history

Daily Supabase Edge Function that syncs one day of eligible `flyer_deals` rows
into `price_history`.

## What It Processes

By default the function processes yesterday's records in UTC. You can pass a
specific date for manual recovery:

```json
{
  "target_date": "2026-06-04"
}
```

Eligible source rows:

- `match_key` is not null
- `store_id` is not null
- `product_price` is greater than 0
- `processed_at` falls on `target_date`

The function groups by:

```text
match_key + store_id + observed_date
```

If multiple flyer rows exist for the same product/store/processed day, it keeps
the lowest price and upserts one row into `price_history`.

## Local/Manual Test

```bash
supabase functions serve sync-price-history --env-file .env
```

```bash
curl -X POST http://127.0.0.1:54321/functions/v1/sync-price-history \
  -H "Authorization: Bearer $SUPABASE_SERVICE_ROLE_KEY" \
  -H "Content-Type: application/json" \
  -d '{"target_date":"2026-06-04","dry_run":true}'
```

## Deploy

```bash
supabase functions deploy sync-price-history
supabase secrets set SUPABASE_SERVICE_ROLE_KEY=...
```

`SUPABASE_URL` is normally available in Supabase Edge Functions. The function
also accepts `SUPABASE_KEY`, but `SUPABASE_SERVICE_ROLE_KEY` is preferred.
