// v2
import React from "react";
import { Check, Plus } from "lucide-react";
import { Button } from "@/components/ui/button";
import { getRetailerLogo } from "@/lib/retailerLogos";
import type { OptimizedCartItem } from "@/components/cart-optimizer/types";

const dealCardPerfStyle = {
  contentVisibility: "auto",
  containIntrinsicSize: "220px",
} as React.CSSProperties;

type GetDealItemId = (
  deal: Pick<
    OptimizedCartItem,
    "product_name" | "retailer" | "zip_code" | "product_price"
  >
) => string;

type DealsItemsViewProps = {
  items: OptimizedCartItem[];
  scopeKey: string;
  layout: "grid" | "carousel";
  addedItems: Set<string>;
  onAddDealToCart: (deal: OptimizedCartItem) => void;
  getDealItemId: GetDealItemId;
  normalizeImageUrl: (url: string | null) => string;
  placeholderImage: string;
  formatDistance: (distanceMeters: number) => string;
  onDealClick?: (deal: OptimizedCartItem) => void;
};

const loggedFailedImageRequests = new Set<string>();

function DealItemCard({
  item,
  idx,
  scopeKey,
  layout,
  addedItems,
  onAddDealToCart,
  onDealClick,
  getDealItemId,
  normalizeImageUrl,
  placeholderImage,
  formatDistance,
}: {
  item: OptimizedCartItem;
  idx: number;
  scopeKey: string;
  layout: "grid" | "carousel";
  addedItems: Set<string>;
  onAddDealToCart: (deal: OptimizedCartItem) => void;
  onDealClick?: (deal: OptimizedCartItem) => void;
  getDealItemId: GetDealItemId;
  normalizeImageUrl: (url: string | null) => string;
  placeholderImage: string;
  formatDistance: (distanceMeters: number) => string;
}) {
  const itemId = getDealItemId(item);
  const key = `${scopeKey}-${itemId}-${idx}`;
  const isAdded = addedItems.has(itemId);
  const retailerLogo = getRetailerLogo(item.retailer);
  const normalizedImageUrl = normalizeImageUrl(item.image_link);
  const badgeText =
    item.distance_m && item.distance_m > 0 ? formatDistance(item.distance_m) : null;

  // Size + unit price priority:
  //  1. base_amount + base_unit → resolvedSizeLabel = "{amount} {unit}"
  //     and unitPriceLine = "$X.XX/{unit}" (shown inline next to price)
  //  2. product_size only → resolvedSizeLabel = product_size, no unit price
  //  3. neither → both null, render nothing
  const hasBase =
    item.base_amount != null && item.base_amount > 0 && !!item.base_unit;
  const resolvedSizeLabel: string | null = hasBase
    ? `${item.base_amount} ${item.base_unit}`
    : item.product_size || null;
  const unitPriceLine: string | null =
    hasBase && item.product_price
      ? `$${(item.product_price / (item.base_amount as number)).toFixed(2)}/${item.base_unit}`
      : null;

  return (
    <li
      key={key}
      className={
        layout === "carousel"
          ? "w-[46%] min-w-[150px] max-w-[178px] shrink-0 snap-start"
          : "min-w-0"
      }
      style={dealCardPerfStyle}
    >
      <div
        className="relative overflow-hidden rounded-3xl border-2 border-[#211B16] bg-[#FDF8F0] shadow-clay-md"
        onClick={() => onDealClick?.(item)}
        style={item.match_key && onDealClick ? { cursor: "pointer" } : undefined}
      >
        {/* Product image */}
        <img
          src={normalizedImageUrl}
          alt={item.product_name}
          className="h-36 w-full object-contain bg-white"
          loading="lazy"
          decoding="async"
          referrerPolicy="no-referrer"
          draggable={false}
          onDragStart={(e) => e.preventDefault()}
          onError={(e) => {
            const failedSrc = e.currentTarget.currentSrc || e.currentTarget.src;
            if (
              import.meta.env.DEV &&
              !failedSrc.includes(placeholderImage) &&
              !loggedFailedImageRequests.has(failedSrc)
            ) {
              loggedFailedImageRequests.add(failedSrc);
              console.warn(
                "[Deals image debug] Image request failed; falling back to placeholder.",
                {
                  product_name: item.product_name,
                  retailer: item.retailer,
                  image_link: item.image_link,
                  normalized_src: normalizedImageUrl,
                  failed_src: failedSrc,
                }
              );
            }
            e.currentTarget.src = placeholderImage;
          }}
        />

        {/* Retailer logo badge — top right */}
        {retailerLogo && (
          <span className="absolute right-1.5 top-1.5 flex h-5 w-5 items-center justify-center rounded-full border border-[#d6dddb] bg-white/95">
            <img
              src={retailerLogo}
              alt={`${item.retailer} logo`}
              className="h-3 w-3 object-contain"
              decoding="async"
              draggable={false}
              onDragStart={(e) => e.preventDefault()}
            />
          </span>
        )}

        {/* Organic badge — top left */}
        {item.is_organic && (
          <span className="absolute left-1.5 top-1.5 inline-flex items-center rounded-full bg-[#d1fae5] px-1.5 py-0.5 text-[9px] font-semibold uppercase tracking-[0.04em] text-[#065f46]">
            Organic
          </span>
        )}

        {/* + Add / ✓ Added button — bottom right */}
        <Button
          radius="pill"
          className="absolute bottom-1.5 right-1.5 flex h-8 items-center gap-1 whitespace-nowrap bg-[#175C43] px-3 text-[12px] font-semibold text-white shadow-md transition hover:bg-[#14523C] active:scale-95"
          onClick={() => onAddDealToCart(item)}
          aria-label={`Add ${item.product_name} to cart`}
        >
          {isAdded ? (
            <>
              <Check className="h-3 w-3" />
              <span>Added</span>
            </>
          ) : (
            <>
              <Plus className="h-3 w-3" />
              <span>Add</span>
            </>
          )}
        </Button>
      </div>

      <div className="mt-1.5 space-y-0.5 px-0.5">
        {/* Distance badge */}
        {badgeText && (
          <span className="inline-flex rounded-full bg-[#fdebd3] px-1.5 py-0.5 text-[9px] font-semibold uppercase tracking-[0.04em] text-[#bc6b1f]">
            {badgeText}
          </span>
        )}

        {/* Product name */}
        <p className="line-clamp-2 text-[12px] font-semibold leading-tight text-[#1f2937]">
          {item.product_name}
        </p>

        {/* Brand */}
        {item.brand && (
          <p className="truncate text-[10px] text-[#70767a]">{item.brand}</p>
        )}

        {/* Size */}
        {resolvedSizeLabel && (
          <p className="truncate text-[10px] text-[#70767a]">
            Size: {resolvedSizeLabel}
          </p>
        )}

        {/* Price row: sale price + unit price */}
        <div className="flex items-baseline gap-1.5">
          <p className="text-[16px] font-bold leading-tight text-[#102d22]">
            ${Number(item.product_price).toFixed(2)}
          </p>
          {unitPriceLine && (
            <p className="text-[10px] text-[#70767a]">{unitPriceLine}</p>
          )}
        </div>

        {/* Retailer logo (preferred) or retailer name */}
        {retailerLogo || item.retailer ? (
          <div className="flex items-center gap-2">
            {retailerLogo ? (
              <img
                src={retailerLogo}
                alt={`${item.retailer} logo`}
                className="h-4 w-auto object-contain"
                decoding="async"
              />
            ) : null}
            {!retailerLogo && item.retailer ? (
              <p className="truncate text-[10px] text-[#70767a]">
                {item.retailer}
              </p>
            ) : null}
          </div>
        ) : null}
      </div>
    </li>
  );
}

export function DealsItemsView({
  items,
  scopeKey,
  layout,
  addedItems,
  onAddDealToCart,
  getDealItemId,
  normalizeImageUrl,
  placeholderImage,
  formatDistance,
  onDealClick,
}: DealsItemsViewProps) {
  if (layout === "grid") {
    return (
      <ul className="grid grid-cols-2 gap-x-2 gap-y-3">
        {items.map((item, idx) => (
          <DealItemCard
            key={`${scopeKey}-${getDealItemId(item)}-${idx}`}
            item={item}
            idx={idx}
            scopeKey={scopeKey}
            layout="grid"
            addedItems={addedItems}
            onAddDealToCart={onAddDealToCart}
            onDealClick={onDealClick}
            getDealItemId={getDealItemId}
            normalizeImageUrl={normalizeImageUrl}
            placeholderImage={placeholderImage}
            formatDistance={formatDistance}
          />
        ))}
      </ul>
    );
  }

  return (
    <ul
      className="flex snap-x snap-proximity gap-2 overflow-x-auto pb-1 pr-0.5 touch-auto select-none [scrollbar-width:none] [-ms-overflow-style:none] [&::-webkit-scrollbar]:hidden"
      aria-label={`${scopeKey}-carousel`}
    >
      {items.map((item, idx) => (
        <DealItemCard
          key={`${scopeKey}-${getDealItemId(item)}-${idx}`}
          item={item}
          idx={idx}
          scopeKey={scopeKey}
          layout="carousel"
          addedItems={addedItems}
          onAddDealToCart={onAddDealToCart}
          onDealClick={onDealClick}
          getDealItemId={getDealItemId}
          normalizeImageUrl={normalizeImageUrl}
          placeholderImage={placeholderImage}
          formatDistance={formatDistance}
        />
      ))}
    </ul>
  );
}
