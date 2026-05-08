import type { OptimizedCartItem } from "@/components/cart-optimizer/types";

export type FlyerDealRow = {
  product_name: string | null;
  product_price: number | null;
  retailer: string | null;
  zip_code: string | null;
  product_size: string | null;
  image_link: string | null;
  retailer_logo_url: string | null;
  brand?: string | null;
  category?: string | null;
  is_store_brand?: boolean | null;
  is_organic?: boolean | null;
  base_amount?: number | null;
  base_unit?: string | null;
  match_key?: string | null;
};

export function normalizeFlyerDeals(
  rawDeals: FlyerDealRow[],
  effectiveZip: string
): OptimizedCartItem[] {
  return rawDeals
    .filter(
      (deal): deal is FlyerDealRow & { product_name: string; product_price: number } =>
        typeof deal.product_name === "string" &&
        deal.product_price !== null &&
        !Number.isNaN(Number(deal.product_price)) &&
        Number(deal.product_price) > 0
    )
    .map((deal) => ({
      searched_item: "",
      product_name: deal.product_name,
      product_price: Number(deal.product_price),
      retailer: deal.retailer ?? "",
      zip_code: deal.zip_code ?? effectiveZip,
      distance_m: 0,
      product_size: deal.product_size ?? null,
      image_link: deal.image_link ?? null,
      retailer_logo_url: deal.retailer_logo_url ?? null,
      brand: deal.brand ?? null,
      category: deal.category ?? null,
      is_store_brand: deal.is_store_brand ?? null,
      is_organic: deal.is_organic ?? null,
      base_amount: deal.base_amount ?? null,
      base_unit: deal.base_unit ?? null,
      match_key: deal.match_key ?? null,
    }));
}
