# Mobile App Integration Files

These are the files added/modified in the `atc5nc/mobile_app` repo (branch: `ui_testing`)
to wire in the Prox Backend API.

## New Files
- `src/services/proxApi.ts` — typed API client for https://prox-api.fly.dev
- `src/pages/deals/DealDetails.tsx` — Deal Details screen (nearby stores, price history chart, savings)

## Modified Files
- `src/App.tsx` — added `/deals/:matchKey` route
- `src/pages/Deals.tsx` — added `handleDealClick` navigation
- `src/pages/deals/DealsItemsView.tsx` — made deal cards clickable, added `onDealClick` prop
- `src/pages/deals/flyerDeals.ts` — added `match_key` to `FlyerDealRow` type
- `src/pages/deals/fetchFlyerDeals.ts` — added `match_key` to Supabase select
- `src/components/cart-optimizer/types.ts` — added optional `match_key` to `OptimizedCartItem`

## Status
These changes are tested locally against a clone of `atc5nc/mobile_app`.
Ready to be reviewed and merged into `ui_testing` when Alston gives the go-ahead.
