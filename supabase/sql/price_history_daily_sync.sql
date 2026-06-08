-- Required for idempotent price_history writes.
-- Re-running the function for the same date updates existing rows instead of
-- inserting duplicates.
create unique index if not exists price_history_match_store_date_uidx
on public.price_history (match_key, store_id, observed_date);

-- Supports the Edge Function's daily fetch:
-- processed_at date window + keyset pagination by id.
create index concurrently if not exists idx_flyer_deals_price_history_processed_at_id
on public.flyer_deals (processed_at, id)
where match_key is not null
  and store_id is not null
  and product_price is not null
  and product_price > 0;

create or replace function public.sync_price_history_for_date(p_target_date date)
returns table (
  synced_date date,
  rows_written bigint
)
language plpgsql
security definer
as $$
begin
  insert into public.price_history (
    match_key,
    store_id,
    brand,
    canonical_product_name,
    size_oz,
    product_price,
    observed_at,
    observed_date
  )
  select
    fd.match_key,
    fd.store_id,
    (array_agg(fd.brand order by fd.product_price asc))[1] as brand,
    (array_agg(fd.canonical_product_name order by fd.product_price asc))[1] as canonical_product_name,
    (array_agg(
      case
        when fd.base_amount is null or fd.base_unit is null then null
        when lower(replace(replace(fd.base_unit, ' ', ''), '.', '')) in ('oz', 'floz') then fd.base_amount
        when lower(fd.base_unit) in ('lb', 'lbs', 'pound', 'pounds') then fd.base_amount * 16
        when lower(fd.base_unit) in ('g', 'gram', 'grams') then fd.base_amount * 0.035274
        when lower(fd.base_unit) = 'ml' then fd.base_amount * 0.033814
        when lower(fd.base_unit) in ('l', 'liter') then fd.base_amount * 33.814
        else null
      end
      order by fd.product_price asc
    ))[1] as size_oz,
    min(fd.product_price) as product_price,
    now() as observed_at,
    p_target_date as observed_date
  from public.flyer_deals fd
  where fd.processed_at >= p_target_date::timestamptz
    and fd.processed_at < (p_target_date + interval '1 day')::timestamptz
    and fd.match_key is not null
    and fd.store_id is not null
    and fd.product_price is not null
    and fd.product_price > 0
  group by
    fd.match_key,
    fd.store_id
  on conflict (match_key, store_id, observed_date)
  do update set
    brand = excluded.brand,
    canonical_product_name = excluded.canonical_product_name,
    size_oz = excluded.size_oz,
    product_price = excluded.product_price,
    observed_at = excluded.observed_at;

  return query
  select
    p_target_date as synced_date,
    count(*)::bigint as rows_written
  from public.price_history ph
  where ph.observed_date = p_target_date;
end;
$$;

-- Optional: schedule the Edge Function once per day after flyer ingestion.
-- Replace YOUR_PROJECT_REF and YOUR_SERVICE_ROLE_KEY before running.
--
-- select cron.schedule(
--   'daily-price-history-sync',
--   '0 3 * * *',
--   $$
--   select net.http_post(
--     url := 'https://YOUR_PROJECT_REF.supabase.co/functions/v1/sync-price-history',
--     headers := jsonb_build_object(
--       'Authorization', 'Bearer YOUR_SERVICE_ROLE_KEY',
--       'Content-Type', 'application/json'
--     ),
--     body := jsonb_build_object('target_date', current_date - 1)
--   );
--   $$
-- );
