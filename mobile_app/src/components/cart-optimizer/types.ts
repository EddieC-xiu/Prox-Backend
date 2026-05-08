export type OptimizedCartItem = {
  searched_item: string;
  product_name: string;
  product_price: number;
  retailer: string;
  zip_code: string;
  distance_m: number;
  product_size: string | null;
  image_link: string | null;
  retailer_logo_url: string | null;
  /** Physical store identifier from flyer_deals.store_id → store_locations.store_id */
  store_id?: string | null;
  /** Enriched columns sourced from flyer_deals — null when the row has no value. */
  brand?: string | null;
  category?: string | null;
  is_store_brand?: boolean | null;
  is_organic?: boolean | null;
  base_amount?: number | null;
  base_unit?: string | null;
  match_key?: string | null;
};

export type SingleStoreResult = {
  retailer: string;
  zip_code: string;
  total_cart_price: number;
  items_found_count: number;
  distance_m: number;
  items_found: OptimizedCartItem[];
  retailer_logo_url: string | null;
  /** Physical store identifier — first store_id found for this retailer+zip group */
  store_id?: string | null;
};

export type OptimizedCart = {
  stores: string[];
  total_cart_price: number;
  items_found: OptimizedCartItem[];
  items_missing: string[];
};

export type ZipCentroid = { lat: number; lng: number } | null;

export type SortOption = "none" | "price-asc" | "price-desc";

export type EditableCartItem = {
  name: string;
  brand: string;
  size: string;
  details: string;
};

export type RefineOptionBucket = {
  brands: string[];
  sizes: string[];
  details: string[];
};

export type RefineSelection = {
  brands: Set<string>;
  sizes: Set<string>;
  details: Set<string>;
};

export type CartFinderLaunchState = {
  optimizeCustomCart?: {
    retailerCountLimit: number;
    items: EditableCartItem[];
  };
};
