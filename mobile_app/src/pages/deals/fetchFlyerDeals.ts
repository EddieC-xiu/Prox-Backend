import type { FlyerDealRow } from "@/pages/deals/flyerDeals";

const PROX_API = "https://prox-api.fly.dev";

export async function fetchFlyerDeals(
  _zipCode: string,
  _minDate: string
): Promise<{ data: FlyerDealRow[] | null; error: unknown }> {
  try {
    // Use best-deals API — works nationwide regardless of which zip codes were scraped
    const params = new URLSearchParams({
      limit: "100",
      min_savings: "5",
      min_retailers: "2",
      min_days: "1",
    });
    const res = await fetch(`${PROX_API}/best-deals?${params}`);
    if (!res.ok) throw new Error(`API error ${res.status}`);
    const json = await res.json();

    const data: FlyerDealRow[] = (json.deals ?? []).map((d: Record<string, unknown>) => ({
      product_name:      d.canonical_product_name as string ?? null,
      product_price:     d.best_price as number ?? null,
      retailer:          `${d.retailer_count} retailers`,
      zip_code:          _zipCode,
      product_size:      null,
      image_link:        null,
      retailer_logo_url: null,
      brand:             d.brand as string ?? null,
      category:          null,
      is_store_brand:    null,
      is_organic:        null,
      base_amount:       null,
      base_unit:         null,
      match_key:         d.match_key as string ?? null,
    }));

    return { data, error: null };
  } catch (error) {
    return { data: null, error };
  }
}
