-- Required for idempotent price_history writes.
-- Re-running the function for the same date updates existing rows instead of
-- inserting duplicates.
create unique index if not exists price_history_match_store_date_uidx
on public.price_history (match_key, store_id, observed_date);

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
