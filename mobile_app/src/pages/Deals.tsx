import React, { useState } from "react";
import { Button } from "@/components/ui/button";
import { useNavigate } from "react-router-dom";
import {
  Info,
  ShoppingCart,
} from "lucide-react";
import { BottomNav } from "@/components/BottomNav";
import { useIosPageBackground } from "@/hooks/useIosPageBackground";
import {
  CART_OPTIMIZER_PHONE_OUTER_LANDING_CLASS,
  CART_OPTIMIZER_PHONE_SHELL_CLASS,
} from "@/components/cart-optimizer/phoneShell";
import {
  Popover,
  PopoverTrigger,
  PopoverContent,
} from "@/components/ui/popover";
import type { OptimizedCartItem } from "@/components/cart-optimizer/types";
import {
  DEPARTMENT_FILTERS,
  getDealItemId,
} from "@/pages/deals/catalog";
import { DealsBrowseView } from "@/pages/deals/DealsBrowseView";
import { DealsGuestLimitDialog } from "@/pages/deals/DealsGuestLimitDialog";
import { DealsItemSavedModal } from "@/pages/deals/DealsItemSavedModal";
import { DealsItemsView } from "@/pages/deals/DealsItemsView";
import { DealsSearchResultsView } from "@/pages/deals/DealsSearchResultsView";
import { useDealsPageState } from "@/pages/deals/useDealsPageState";
import { DealsSearchComposer } from "@/pages/deals/DealsSearchComposer";
import type { SavingsSnapshot } from "@/pages/deals/browseDerivations";

const USD = new Intl.NumberFormat("en-US", {
  style: "currency",
  currency: "USD",
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
});

const DEPARTMENT_PASTEL_COLORS: Record<string, string> = {
  all: "#E8E8E8",
  produce: "#C8E6C9",
  meat_seafood: "#F2C4C4",
  pantry: "#FFE0B2",
  beverages: "#B2EBF2",
  dairy_eggs: "#FFF9C4",
  snacks: "#E1BEE7",
  frozen: "#BBDEFB",
  bakery: "#FFE4B5",
  deli_prepared: "#D7CCC8",
  desserts: "#F8BBD0",
  non_dairy_milks: "#E8F5E9",
  household: "#CFD8DC",
  pet: "#FFCCBC",
  health_beauty: "#E1F5FE",
  baby: "#FFE5EC",
};

function getDepartmentPastelColor(department: { key: string; label: string }) {
  const key = department.key.toLowerCase();
  return DEPARTMENT_PASTEL_COLORS[key] ?? DEPARTMENT_PASTEL_COLORS.all;
}

function SavingsInfoPopover({ savingsSnapshot }: { savingsSnapshot: SavingsSnapshot }) {
  const [open, setOpen] = useState(false);

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <button
          type="button"
          aria-label="More info about savings"
          className="inline-flex items-center justify-center min-w-[24px] min-h-[24px] text-[#8a9399] hover:text-[#637076] transition-colors"
          onClick={(e) => e.stopPropagation()}
        >
          <Info size={12} />
        </button>
      </PopoverTrigger>
      <PopoverContent className="clay-card-sm w-80 p-4" side="bottom" align="start">
        {savingsSnapshot.hasEnoughData ? (
          <div className="space-y-3">
            <p className="text-xs font-semibold text-[#111827]">How we calculated this</p>
            <p className="text-[11px] text-[#6b7280] leading-relaxed">
              Based on nearby prices for common grocery staples in your area this week.
            </p>
            <div className="space-y-1.5">
              {savingsSnapshot.breakdown.map((item) => (
                <div key={item.staple} className="flex items-center justify-between text-[11px]">
                  <span className="text-[#374151] font-medium truncate mr-2">{item.staple}</span>
                  <span className="text-[#6b7280] whitespace-nowrap">
                    {USD.format(item.lowestPrice)} vs {USD.format(item.medianPrice)}
                    <span className="ml-1 font-semibold text-[#1f7a4f]">
                      save {USD.format(item.savings)}
                    </span>
                  </span>
                </div>
              ))}
            </div>
            <div className="border-t border-[#e5e7eb] pt-2 flex items-center justify-between text-[11px]">
              <span className="font-semibold text-[#111827]">Total potential savings</span>
              <span className="font-bold text-[#1f7a4f]">
                {USD.format(savingsSnapshot.amount)} ({savingsSnapshot.percent}%)
              </span>
            </div>
            <p className="text-[10px] text-[#9ca3af] leading-relaxed">
              Based on stores near your selected ZIP code and radius this week.
            </p>
          </div>
        ) : (
          <div className="space-y-2">
            <p className="text-xs font-semibold text-[#111827]">Savings estimate</p>
            <p className="text-[11px] text-[#6b7280] leading-relaxed">
              We don&apos;t have enough nearby staple pricing data to estimate savings
              for this area yet. Try another ZIP code or radius, or check back as
              more deals are added.
            </p>
          </div>
        )}
      </PopoverContent>
    </Popover>
  );
}

export function Deals() {
  useIosPageBackground("#F4EBDD");

  const navigate = useNavigate();
  const {
    activeDepartment,
    addedItems,
    availableRetailers,
    browseSections,
    cartTotal,
    dealImagePlaceholder,
    derivedSingleItemDeals,
    editableCartItems,
    effectiveZip,
    error,
    formatDistance,
    guestLimitDialogOpen,
    setGuestLimitDialogOpen,
    handleAddDealToCart,
    handleReRunSearch,
    handleSearch,
    hasFeaturedDeals,
    initialSearchDone,
    itemSavedModalDescription,
    itemSavedModalOpen,
    items,
    loading,
    loadingFeatured,
    locationPanelOpen,
    locationPanelRef,
    normalizeDealImageUrl,
    openBrowseSection,
    openLocationPanel,
    paginatedSingleItemDeals,
    preferredStaplesStores,
    staplePriceGrid,
    stapleRetailers,
    radius,
    refineDropdownOpen,
    refineOpen,
    refineOptionsByName,
    refineSelected,
    refreshFeatured,
    retailersOpenPanel,
    savingsSnapshot,
    searchQuery,
    selectedRetailers,
    setActiveDepartment,
    setItemSavedModalOpen,
    setRadius,
    setRefineOpen,
    setRefineOpenKey,
    setRefineSelected,
    setRetailersOpenPanel,
    setSearchQuery,
    setSelectedRetailers,
    setSingleItemPage,
    setSortOption,
    setZipcode,
    singleItemPage,
    singleItemTotalPages,
    sortOption,
    toggleLocationPanel,
    zipcode,
  } = useDealsPageState();

  const handleDealClick = (deal: OptimizedCartItem) => {
    if (deal.match_key) {
      navigate(`/deals/${encodeURIComponent(deal.match_key)}?zip=${deal.zip_code ?? ""}`);
    }
  };

  const renderItemsGrid = (itemsToRender: OptimizedCartItem[], scopeKey: string) => (
    <DealsItemsView
      items={itemsToRender}
      scopeKey={scopeKey}
      layout="grid"
      addedItems={addedItems}
      onAddDealToCart={handleAddDealToCart}
      onDealClick={handleDealClick}
      getDealItemId={getDealItemId}
      normalizeImageUrl={normalizeDealImageUrl}
      placeholderImage={dealImagePlaceholder}
      formatDistance={formatDistance}
    />
  );

  const renderItemsCarousel = (itemsToRender: OptimizedCartItem[], scopeKey: string) => (
    <DealsItemsView
      items={itemsToRender}
      scopeKey={scopeKey}
      layout="carousel"
      addedItems={addedItems}
      onAddDealToCart={handleAddDealToCart}
      onDealClick={handleDealClick}
      getDealItemId={getDealItemId}
      normalizeImageUrl={normalizeDealImageUrl}
      placeholderImage={dealImagePlaceholder}
      formatDistance={formatDistance}
    />
  );

  return (
    <div
      data-testid="deals-page-shell"
      className="h-[100dvh] overflow-hidden flex flex-col bg-[var(--app-bg)] text-[#111827]"
    >
      <DealsGuestLimitDialog
        open={guestLimitDialogOpen}
        onOpenChange={setGuestLimitDialogOpen}
        onSignUp={() => navigate("/auth?mode=signup&source=guest-deals-limit")}
      />
      <DealsItemSavedModal
        open={itemSavedModalOpen}
        onClose={() => setItemSavedModalOpen(false)}
        onViewCart={() => {
          setItemSavedModalOpen(false);
          navigate("/cart");
        }}
        description={itemSavedModalDescription}
      />

      <div
        data-testid="deals-page-scroll"
        className="flex-1 h-[calc(100dvh-env(safe-area-inset-top))] overflow-y-auto overscroll-y-none bg-[var(--app-bg)] pb-[calc(env(safe-area-inset-bottom)+6rem)]"
      >
        <div
          data-testid="deals-page-content"
          className="mx-auto max-w-3xl px-4 pt-4"
        >
          <div className={CART_OPTIMIZER_PHONE_OUTER_LANDING_CLASS}>
            <div className={CART_OPTIMIZER_PHONE_SHELL_CLASS}>
              <div className="clay-card p-3">
          <div className="space-y-3">
            <div className="relative min-h-[56px]">
              <button
                type="button"
                onClick={() => navigate("/deals")}
                className="absolute left-0 top-0 flex h-10 w-10 items-center justify-center overflow-hidden rounded-full focus:outline-none focus:ring-2 focus:ring-green-500/40"
                aria-label="Go to Home"
              >
                <img
                  src="/Icon-01.png"
                  alt="Prox"
                  className="h-10 w-auto object-contain"
                />
              </button>

              <button
                type="button"
                onClick={() => navigate("/cart")}
                className="absolute right-0 top-0 flex flex-col items-end"
                aria-label="Open cart"
              >
                <span className="relative inline-flex h-9 w-9 items-center justify-center rounded-full border-2 border-[#211B16] bg-[#175C43] text-white shadow-btn-primary">
                  <ShoppingCart className="h-4 w-4" />
                  <span className="absolute -right-1 -top-1 min-w-[16px] rounded-full bg-black px-1 text-center text-[9px] font-bold leading-[16px] text-white">
                    {items.length}
                  </span>
                </span>
                <span className="mt-0.5 text-[12px] font-semibold tabular-nums text-[#111827]">
                  ${cartTotal.toFixed(2)}
                </span>
              </button>

              <div className="mx-auto max-w-[320px] px-10 text-center">
                <h1 className="font-primary text-[28px] font-black leading-[0.95] text-[#211B16]">
                  Deals
                </h1>
                <p className="mt-1.5 font-secondary text-[13px] leading-[1.35] text-[#211B16]/55">
                  Browse the best deals at retailers near you
                </p>
              </div>
            </div>

            <div className="clay-card-tinted px-2.5 py-2">
              <div className="flex items-center gap-1">
                <p className="text-[10px] font-semibold text-[#637076]">
                  This week&apos;s potential savings
                </p>
                <SavingsInfoPopover savingsSnapshot={savingsSnapshot} />
              </div>
              <div className="mt-1 flex items-center justify-between gap-2">
                <p className="font-primary text-[26px] font-black leading-none text-[#175C43]">
                  ${savingsSnapshot.amount.toFixed(2)}
                </p>
                <span className="rounded-full bg-[#175C43] px-2 py-0.5 font-secondary text-xs font-semibold text-white">
                  {savingsSnapshot.percent}%
                </span>
              </div>
            </div>

            <DealsSearchComposer
              availableRetailers={availableRetailers}
              editableCartItems={editableCartItems}
              effectiveZip={effectiveZip}
              handleReRunSearch={handleReRunSearch}
              handleSearch={handleSearch}
              initialSearchDone={initialSearchDone}
              loading={loading}
              loadingFeatured={loadingFeatured}
              locationPanelOpen={locationPanelOpen}
              locationPanelRef={locationPanelRef}
              openLocationPanel={openLocationPanel}
              radius={radius}
              refineDropdownOpen={refineDropdownOpen}
              refineOpen={refineOpen}
              refineOptionsByName={refineOptionsByName}
              refineSelected={refineSelected}
              refreshFeatured={refreshFeatured}
              retailersOpenPanel={retailersOpenPanel}
              searchQuery={searchQuery}
              selectedRetailers={selectedRetailers}
              setRadius={setRadius}
              setRefineOpen={setRefineOpen}
              setRefineOpenKey={setRefineOpenKey}
              setRefineSelected={setRefineSelected}
              setRetailersOpenPanel={setRetailersOpenPanel}
              setSearchQuery={setSearchQuery}
              setSelectedRetailers={setSelectedRetailers}
              setZipcode={setZipcode}
              toggleLocationPanel={toggleLocationPanel}
              zipcode={zipcode}
            />

            <div className="flex gap-1.5 overflow-x-auto pb-1 [&::-webkit-scrollbar]:hidden [-ms-overflow-style:none] [scrollbar-width:none]">
              {DEPARTMENT_FILTERS.map((department) => {
                const isActiveDepartment = activeDepartment === department.key;

                return (
                  <button
                    key={department.key}
                    type="button"
                    onClick={() => setActiveDepartment(department.key)}
                    className={`whitespace-nowrap rounded-full border-2 border-[#211B16] px-2.5 py-1 text-[11px] font-black text-[#211B16] shadow-[3px_3px_0_#211B16] transition ${
                      isActiveDepartment ? "ring-2 ring-[#211B16] ring-offset-1" : ""
                    }`}
                    style={{ backgroundColor: getDepartmentPastelColor(department) }}
                  >
                    {department.label}
                  </button>
                );
              })}
            </div>

            {error && <p className="text-xs font-semibold text-red-600">{error}</p>}

          </div>

              <div className="mt-3 space-y-3">
            {!initialSearchDone && (
              <DealsBrowseView
                browseSections={browseSections}
                hasFeaturedDeals={hasFeaturedDeals}
                loadingFeatured={loadingFeatured}
                onOpenBrowseSection={openBrowseSection}
                renderItemsCarousel={renderItemsCarousel}
                staplePriceGrid={staplePriceGrid}
                stapleRetailers={stapleRetailers}
              />
            )}

            {initialSearchDone && (
              <DealsSearchResultsView
                derivedSingleItemDeals={derivedSingleItemDeals}
                effectiveZip={effectiveZip}
                loading={loading}
                paginatedSingleItemDeals={paginatedSingleItemDeals}
                radius={radius}
                renderItemsGrid={renderItemsGrid}
                singleItemPage={singleItemPage}
                singleItemTotalPages={singleItemTotalPages}
                sortOption={sortOption}
                onNextPage={() =>
                  setSingleItemPage((page) => Math.min(singleItemTotalPages, page + 1))
                }
                onPreviousPage={() =>
                  setSingleItemPage((page) => Math.max(1, page - 1))
                }
                onSortChange={(value) => {
                  setSortOption(value);
                  setSingleItemPage(1);
                }}
              />
            )}
              </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <BottomNav current="Deals" />
    </div>
  );
}
