-- 006_create_kroger_tokens.sql
--
-- Per-user Kroger OAuth token storage for the cart-fill workflow.
--
-- NOT YET APPLIED. This is provided so the Kroger workflow can move from the
-- local-JSON demo store to Supabase once Alston approves. To go live:
--   1. Review this file.
--   2. Apply it to the Prox Supabase project.
--   3. Set env KROGER_TOKEN_STORE=supabase (default is "local").
--
-- One row per Prox user. access_token/refresh_token are sensitive; this table
-- must stay service-role only (no anon access). RLS is enabled with no public
-- policy so only the backend service key can read/write it.

create table if not exists public.kroger_tokens (
    user_id       text primary key,
    access_token  text        not null,
    refresh_token text,
    expires_at    double precision not null,   -- unix epoch seconds
    scope         text,
    updated_at    timestamptz not null default now()
);

comment on table public.kroger_tokens is
    'Per-user Kroger OAuth tokens for cart-fill handoff. Service-role only.';

-- Lock the table down: enable RLS and add NO policies, so anon/auth roles get
-- zero access. The backend uses the service-role key which bypasses RLS.
alter table public.kroger_tokens enable row level security;
