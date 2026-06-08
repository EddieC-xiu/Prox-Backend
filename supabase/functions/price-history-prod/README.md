# sync-price-history

Daily Supabase Edge Function that syncs one day of eligible `flyer_deals` rows
into `price_history` by calling the `sync_price_history_for_date` database RPC.

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

The heavy grouping/upsert work runs inside Postgres through the RPC. This avoids
pulling tens of thousands of `flyer_deals` rows through the Edge Function.

## Local/Manual Test

```bash
supabase functions serve sync-price-history --env-file .env
```

```bash
curl -X POST http://127.0.0.1:54321/functions/v1/sync-price-history \
  -H "Authorization: Bearer $SUPABASE_SERVICE_ROLE_KEY" \
  -H "Content-Type: application/json" \
  -d '{"target_date":"2026-06-04"}'
```

`dry_run` returns a no-op response in RPC mode. Use the SQL RPC directly if you
need to inspect row counts before syncing.

## Deploy

```bash
supabase functions deploy sync-price-history
supabase secrets set SUPABASE_SERVICE_ROLE_KEY=...
```

If production uses a different function name, deploy this same `index.ts` code
to that function name/folder before testing.

`SUPABASE_URL` is normally available in Supabase Edge Functions. The function
also accepts `SUPABASE_KEY`, but `SUPABASE_SERVICE_ROLE_KEY` is preferred.
