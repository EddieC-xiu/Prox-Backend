import { supabase } from "@/integrations/supabase/client";
import type { FlyerDealRow } from "@/pages/deals/flyerDeals";

const BROWSE_FETCH_LIMIT = 2000;

export async function fetchFlyerDeals(
  zipCode: string,
  minDate: string
): Promise<{ data: FlyerDealRow[] | null; error: unknown }> {
  return supabase
    .from("flyer_deals")
    .select("product_name, product_price, retailer, zip_code, product_size, image_link, brand, category, is_store_brand, is_organic, base_amount, base_unit, match_key")
    .eq("zip_code", zipCode)
    .not("product_price", "is", null)
    .order("product_price", { ascending: true })
    .limit(BROWSE_FETCH_LIMIT);
}
