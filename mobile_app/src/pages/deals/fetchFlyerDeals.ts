import type { FlyerDealRow } from "@/pages/deals/flyerDeals";

const PROX_API = "https://prox-api.fly.dev";

export async function fetchFlyerDeals(
  zipCode: string,
  _minDate: string
): Promise<{ data: FlyerDealRow[] | null; error: unknown }> {
  try {
    const params = new URLSearchParams({
      zip_code: zipCode,
      radius: "15",
      limit: "500",
    });
    const res = await fetch(`${PROX_API}/search/deals?${params}`);
    if (!res.ok) throw new Error(`API error ${res.status}`);
    const json = await res.json();

    const data: FlyerDealRow[] = (json.deals ?? []).map((d: Record<string, unknown>) => ({
      product_name:      d.product_name as string ?? null,
      product_price:     d.product_price as number ?? null,
      retailer:          (d.retailer as string) ?? (d.retailer_key as string) ?? null,
      zip_code:          zipCode,
      product_size:      d.display_size as string ?? null,
      image_link:        d.image_link as string ?? null,
      retailer_logo_url: null,
      brand:             d.brand as string ?? null,
      category:          d.category as string ?? null,
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
