import { useCallback, useEffect, useMemo, useRef, useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";

import type { OptimizedCartItem } from "@/components/cart-optimizer/types";
import { useCart } from "@/contexts/CartContext";
import { useAuth } from "@/contexts/AuthContext";
import {
  DEAL_IMAGE_PLACEHOLDER,
  normalizeDealImageUrl,
} from "@/lib/dealImages";
import { getLastWednesdayPST, formatDistance } from "@/lib/dateUtils";
import { getErrorMessage } from "@/lib/error";
import { hapticImpact, ImpactStyle } from "@/lib/haptics";
import type { DealMenuItem } from "@/lib/searchDeals";
import { useResolvedDefaultZip } from "@/hooks/useResolvedDefaultZip";
import { normalizePreferredRetailers } from "@/lib/preferredRetailers";
import { useGuestStore } from "@/stores/guestStore";
import { useSearchContextStore } from "@/stores/searchContextStore";
import {
  buildFeaturedByCategory,
  DEPARTMENT_FILTER_KEYS,
  FEATURED_CATEGORY_KEYS,
  FEATURED_SECTION_TITLE_BY_KEY,
  getDealItemId,
} from "@/pages/deals/catalog";
import { fetchFlyerDeals } from "@/pages/deals/fetchFlyerDeals";
import {
  buildBrowseDealsPool,
  buildDealsBrowseSections,
  deriveFeaturedByCategoryForBrowse,
  deriveSavingsFromStaplePrices,
  getActiveDealsCategoryKeys,
  hasFeaturedDealsForCategories,
  type SavingsSnapshot,
} from "@/pages/deals/browseDerivations";
import {
  deriveSingleItemDeals,
  getPaginatedSingleItemDeals,
} from "@/pages/cart-finder/singleItemDerivations";
import {
  toPersistedRefineSelection,
  type PersistedDealsViewState,
  type PersistedDealsSortOption,
} from "@/pages/deals/persistence";
import {
  buildDealsRefineOptionsByName,
  syncDealsRefineSelections,
  type DealsRefineSelection,
} from "@/pages/deals/refine";
import {
  getEffectiveSelectedRetailers,
} from "@/pages/deals/retailerSelection";
import {
  getRetailersWithStaples,
  type StaplePriceGrid,
} from "@/lib/matchStaplePrices";
import { fetchStaplePrices } from "@/lib/fetchStaplePrices";
import { buildDealsSectionUrl } from "@/pages/deals/sectionRoute";
import { useDealsFeaturedFeed } from "@/pages/deals/useDealsFeaturedFeed";
import { useDealsLocationPanel } from "@/pages/deals/useDealsLocationPanel";
import {
  useDealsPersistedViewState,
  usePersistDealsViewState,
} from "@/pages/deals/useDealsViewPersistence";
import { useDealsSearchFlow } from "@/pages/deals/useDealsSearchFlow";
import { proxSearchSingleItem } from "@/lib/proxSearch";
import {
  buildSearchEditSummary,
  findMatchingSearchItem,
  saveSuccessfulQueryPreferences,
  serializeRefineSelections,
  serializeSearchItems,
  useAnalyticsSearchMission,
} from "@/lib/analytics/useSearchMission";

type EditableCartItem = {
  name: string;
  brand: string;
  size: string;
  details: string;
};

const GUEST_DEALS_QUERY_LIMIT = 1;
const ITEMS_PER_PAGE = 12;
const STAPLE_NAMES = ["Chicken Breast", "Ground Beef", "Large Eggs", "Whole Milk", "Cheddar Cheese"];

export function useDealsPageState() {
  const navigate = useNavigate();
  const { user } = useAuth();
  const { addToCart, items } = useCart();
  const { dealsQueriesUsed, setGuestDealsQueriesUsed } = useGuestStore();

  const {
    guestLimitDialogOpen,
    setGuestLimitDialogOpen,
    blockWhenGuestDealsLimitReached,
    runSingleItemDealsSearch,
  } = useDealsSearchFlow({
    user,
    dealsQueriesUsed,
    setGuestDealsQueriesUsed,
    guestLimitCount: GUEST_DEALS_QUERY_LIMIT,
    runSearch: proxSearchSingleItem,
  });

  const persistedViewState = useDealsPersistedViewState(DEPARTMENT_FILTER_KEYS);

  const [searchQuery, setSearchQuery] = useState(
    persistedViewState?.searchQuery ?? ""
  );
  const [zipcode, setZipcode] = useState(persistedViewState?.zipcode ?? "");
  const [radius, setRadius] = useState(persistedViewState?.radius ?? "10");

  const sharedZip = useSearchContextStore((s) => s.effectiveZip);
  const sharedRadius = useSearchContextStore((s) => s.radius);
  const setSharedSearchContext = useSearchContextStore((s) => s.setSearchContext);

  useEffect(() => {
    if (!sharedZip || !/^\d{5}$/.test(sharedZip)) return;
    if (zipcode.trim() === sharedZip) return;
    setZipcode(sharedZip);
  }, [sharedZip]);

  useEffect(() => {
    if (!sharedRadius) return;
    if (radius === sharedRadius) return;
    setRadius(sharedRadius);
  }, [sharedRadius]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [initialSearchDone, setInitialSearchDone] = useState(
    persistedViewState?.initialSearchDone ?? false
  );
  const [editableCartItems, setEditableCartItems] = useState<EditableCartItem[]>(
    persistedViewState?.editableCartItems ?? []
  );
  const [singleItemDeals, setSingleItemDeals] = useState<OptimizedCartItem[]>(
    persistedViewState?.singleItemDeals ?? []
  );
  const [refineOpen, setRefineOpen] = useState(
    persistedViewState?.refineOpen ?? false
  );
  const [addedItems, setAddedItems] = useState<Set<string>>(new Set());
  const [itemSavedModalOpen, setItemSavedModalOpen] = useState(false);
  const [itemSavedModalDescription, setItemSavedModalDescription] = useState("");
  const [singleItemPage, setSingleItemPage] = useState(
    persistedViewState?.singleItemPage ?? 1
  );
  const [sortOption, setSortOption] = useState<PersistedDealsSortOption>(
    persistedViewState?.sortOption ?? "none"
  );
  const [availableRetailers, setAvailableRetailers] = useState<string[]>(
    persistedViewState?.availableRetailers ?? []
  );
  const [selectedRetailers, setSelectedRetailers] = useState<Set<string>>(
    new Set(persistedViewState?.selectedRetailers ?? [])
  );
  // Track whether the user has explicitly changed the retailer filter.
  // When false, selectedRetailers stays empty and the derivation layer
  // treats empty as "all stores".  Search results and featured-feed
  // refreshes must NOT auto-populate selectedRetailers.
  const userModifiedRetailersRef = useRef(
    (persistedViewState?.selectedRetailers ?? []).length > 0
  );
  const [dealMenuCache, setDealMenuCache] = useState<DealMenuItem[]>(
    persistedViewState?.dealMenuCache ?? []
  );
  const [retailersOpenPanel, setRetailersOpenPanel] = useState(false);
  const [activeDepartment, setActiveDepartment] = useState(
    persistedViewState?.activeDepartment ?? "all"
  );
  const [refineSelected, setRefineSelected] = useState<DealsRefineSelection[]>(
    (persistedViewState?.refineSelected ?? []).map((selection) => ({
      brands: new Set(selection.brands),
      sizes: new Set(selection.sizes),
      details: new Set(selection.details),
    }))
  );
  const [refineDropdownOpen, setRefineDropdownOpen] = useState<
    Record<string, boolean>
  >({});
  const dealsSearchMission = useAnalyticsSearchMission();
  const previousDealsSearchSnapshotRef = useRef<{
    filtersSnapshot: Record<string, unknown>;
    itemsSnapshot: Array<Record<string, unknown>>;
    radiusMiles: number | null;
    zipcode: string | null;
  } | null>(null);

  const cartTotal = useMemo(
    () => items.reduce((sum, item) => sum + (Number(item?.price) || 0), 0),
    [items]
  );

  const preferredStaplesStores = useMemo(() => {
    return normalizePreferredRetailers(user?.user_metadata?.preferred_retailers);
  }, [user?.user_metadata?.preferred_retailers]);

  const setRefineOpenKey = (key: string, value: boolean) =>
    setRefineDropdownOpen((prev) => ({ ...prev, [key]: value }));

  const resolvedDefaultZip = useResolvedDefaultZip(user?.id);
  const effectiveZip = useMemo(() => {
    const nextZip = zipcode.trim();
    if (/^\d{5}$/.test(nextZip)) return nextZip;
    return resolvedDefaultZip;
  }, [zipcode, resolvedDefaultZip]);

  useEffect(() => {
    if (effectiveZip && /^\d{5}$/.test(effectiveZip)) {
      setSharedSearchContext(effectiveZip, radius);
    }
  }, [effectiveZip, radius, setSharedSearchContext]);

  // Wrap setSelectedRetailers for the featured feed: only allow auto-sync
  // if the user hasn't explicitly changed the retailer filter.
  const setSelectedRetailersForFeed: typeof setSelectedRetailers = useCallback(
    (action) => {
      if (!userModifiedRetailersRef.current) return;
      setSelectedRetailers(action);
    },
    []
  );

  const { featuredByCategory, loadingFeatured, refreshFeatured } =
    useDealsFeaturedFeed({
      initialSearchDone,
      effectiveZip,
      buildFeaturedByCategory,
      setAvailableRetailers,
      setSelectedRetailers: setSelectedRetailersForFeed,
      fetchFlyerDeals,
    });

  const [staplePriceGrid, setStaplePriceGrid] = useState<StaplePriceGrid>(new Map());
  const [staplePricesByItem, setStaplePricesByItem] = useState<Map<string, number[]>>(new Map());
  const stapleRequestIdRef = useRef(0);

  const refreshStaplePrices = useCallback(async () => {
    if (!/^\d{5}$/.test(effectiveZip)) {
      setStaplePriceGrid(new Map());
      setStaplePricesByItem(new Map());
      return;
    }
    const radiusMiles = parseInt(radius, 10) || 10;
    const requestId = ++stapleRequestIdRef.current;
    try {
      const { priceGrid, pricesByStaple } = await fetchStaplePrices(
        STAPLE_NAMES, effectiveZip, getLastWednesdayPST(), radiusMiles
      );
      if (requestId === stapleRequestIdRef.current) {
        setStaplePriceGrid(priceGrid);
        setStaplePricesByItem(pricesByStaple);
      }
    } catch {
      if (requestId === stapleRequestIdRef.current) {
        setStaplePriceGrid(new Map());
        setStaplePricesByItem(new Map());
      }
    }
  }, [effectiveZip, radius]);

  useEffect(() => {
    void refreshStaplePrices();
  }, [refreshStaplePrices]);

  const stapleRetailers: string[] = useMemo(
    () => getRetailersWithStaples(staplePriceGrid, preferredStaplesStores),
    [staplePriceGrid, preferredStaplesStores]
  );

  const hasFeaturedDeals = useMemo(() => {
    return hasFeaturedDealsForCategories({
      featuredByCategory,
      featuredCategoryKeys: FEATURED_CATEGORY_KEYS,
    });
  }, [featuredByCategory]);

  const effectiveSelectedRetailers = useMemo(
    () =>
      new Set(
        getEffectiveSelectedRetailers({
          availableRetailers,
          selectedRetailers,
        })
      ),
    [availableRetailers, selectedRetailers]
  );

  const getDealsRadiusMiles = useCallback(() => {
    const parsed = parseInt(radius, 10);
    return Number.isFinite(parsed) && parsed > 0 ? parsed : null;
  }, [radius]);

  const buildDealsSnapshot = useCallback(
    (items: EditableCartItem[]) => ({
      filtersSnapshot: {
        refineSelections: serializeRefineSelections(refineSelected),
        selectedRetailers: Array.from(effectiveSelectedRetailers),
      },
      itemsSnapshot: serializeSearchItems(items),
      radiusMiles: getDealsRadiusMiles(),
      zipcode: effectiveZip || null,
    }),
    [effectiveSelectedRetailers, effectiveZip, getDealsRadiusMiles, refineSelected]
  );

  const derivedFeaturedByCategory = useMemo(() => {
    return deriveFeaturedByCategoryForBrowse({
      featuredByCategory,
      selectedRetailers: effectiveSelectedRetailers,
      initialSearchDone,
    });
  }, [effectiveSelectedRetailers, featuredByCategory, initialSearchDone]);

  const derivedSingleItemDeals = useMemo(() => {
    return deriveSingleItemDeals({
      singleItemDeals,
      selectedRetailers: effectiveSelectedRetailers,
      editableCartItems,
      refineSelected,
      dealMenuCache,
    });
  }, [
    dealMenuCache,
    editableCartItems,
    effectiveSelectedRetailers,
    refineSelected,
    singleItemDeals,
  ]);

  const activeCategoryKeys = useMemo(() => {
    return getActiveDealsCategoryKeys({
      activeDepartment,
      featuredCategoryKeys: FEATURED_CATEGORY_KEYS,
    });
  }, [activeDepartment]);

  const browseDealsPool = useMemo(() => {
    return buildBrowseDealsPool({
      activeCategoryKeys,
      featuredByCategory: derivedFeaturedByCategory,
      getDealItemId,
    });
  }, [activeCategoryKeys, derivedFeaturedByCategory]);

  const browseSections = useMemo(() => {
    return buildDealsBrowseSections({
      activeDepartment,
      activeCategoryKeys,
      browseDealsPool,
      featuredByCategory: derivedFeaturedByCategory,
      sectionTitleByKey: FEATURED_SECTION_TITLE_BY_KEY,
    });
  }, [
    activeCategoryKeys,
    activeDepartment,
    browseDealsPool,
    derivedFeaturedByCategory,
  ]);

  const savingsSnapshot: SavingsSnapshot = useMemo(() => {
    return deriveSavingsFromStaplePrices(staplePricesByItem);
  }, [staplePricesByItem]);

  const paginatedSingleItemDeals = useMemo(() => {
    return getPaginatedSingleItemDeals({
      deals: derivedSingleItemDeals,
      sortOption,
      page: singleItemPage,
      itemsPerPage: ITEMS_PER_PAGE,
    });
  }, [derivedSingleItemDeals, singleItemPage, sortOption]);

  const singleItemTotalPages = useMemo(
    () => Math.ceil(derivedSingleItemDeals.length / ITEMS_PER_PAGE),
    [derivedSingleItemDeals]
  );

  const hasMountedRetailerSelectionRef = useRef(false);
  useEffect(() => {
    if (!hasMountedRetailerSelectionRef.current) {
      hasMountedRetailerSelectionRef.current = true;
      return;
    }

    setSingleItemPage(1);
  }, [selectedRetailers]);

  const persistedState: PersistedDealsViewState = useMemo(
    () => ({
      version: 1,
      searchQuery,
      zipcode,
      radius,
      initialSearchDone,
      editableCartItems,
      singleItemDeals,
      singleItemPage,
      sortOption,
      availableRetailers,
      selectedRetailers: Array.from(selectedRetailers),
      dealMenuCache,
      refineSelected: refineSelected.map(toPersistedRefineSelection),
      refineOpen,
      activeDepartment,
    }),
    [
      searchQuery,
      zipcode,
      radius,
      initialSearchDone,
      editableCartItems,
      singleItemDeals,
      singleItemPage,
      sortOption,
      availableRetailers,
      selectedRetailers,
      dealMenuCache,
      refineSelected,
      refineOpen,
      activeDepartment,
    ]
  );

  usePersistDealsViewState(persistedState);

  const {
    locationPanelOpen,
    locationPanelRef,
    openLocationPanel,
    setLocationPanelOpen,
    toggleLocationPanel,
  } = useDealsLocationPanel({
    retailersOpenPanel,
    setRetailersOpenPanel,
  });

  const handleAddDealToCart = (deal: OptimizedCartItem) => {
    hapticImpact(ImpactStyle.Light);
    addToCart({
      name: deal.product_name,
      size: deal.product_size || "",
      brand: deal.retailer,
      details: "",
      price: deal.product_price,
      retailer: deal.retailer,
      image_url: deal.image_link,
    });

    setItemSavedModalDescription(`${deal.product_name} is in your basket.`);
    setItemSavedModalOpen(true);

    const key = getDealItemId(deal);
    setAddedItems((prev) => new Set(prev).add(key));
    setTimeout(() => {
      setAddedItems((prev) => {
        const next = new Set(prev);
        next.delete(key);
        return next;
      });
    }, 1500);

    const matchedItem =
      findMatchingSearchItem(editableCartItems, deal.searched_item) ?? {
        brand: "",
        details: "",
        name: deal.searched_item,
        size: deal.product_size ?? "",
      };

    void (async () => {
      const didResolve = await dealsSearchMission.resolveMission(
        "added_to_cart",
        [deal.retailer],
      );
      previousDealsSearchSnapshotRef.current = null;

      if (!didResolve) {
        return;
      }

      await saveSuccessfulQueryPreferences({
        items: [matchedItem],
        mode: "deal_lookup",
        selectedRetailers: [deal.retailer],
        surface: "deals",
      });
    })();
  };

  const getUniqueRetailersFromMenu = (dealMenu: DealMenuItem[]) => {
    return Array.from(
      new Set((dealMenu || []).map((deal) => deal.retailer).filter(Boolean))
    ).sort((left, right) => left.localeCompare(right));
  };

  const refineOptionsByName = useMemo(() => {
    return buildDealsRefineOptionsByName(dealMenuCache);
  }, [dealMenuCache]);

  useEffect(() => {
    if (!initialSearchDone) return;
    if (editableCartItems.length === 0) return;

    setRefineSelected((prev) =>
      syncDealsRefineSelections({
        editableCartItems,
        refineOptionsByName,
        previousSelections: prev,
      })
    );
  }, [initialSearchDone, editableCartItems, refineOptionsByName]);

  const handleRunSearch = async (itemsToFind: EditableCartItem[]) => {
    if (blockWhenGuestDealsLimitReached()) {
      return;
    }

    setLoading(true);
    setError(null);
    setSingleItemPage(1);
    setSortOption("none");

    const searchTerms = itemsToFind.map((item) => item.name).filter(Boolean);

    if (searchTerms.length === 0) {
      setError("Please enter an item to search.");
      setLoading(false);
      return;
    }

    if (searchTerms.length > 1) {
      setError(
        "Only one product search is allowed. Please remove semicolons and search for a single item."
      );
      setLoading(false);
      return;
    }

    const zipForRpc = (effectiveZip || "").trim();
    if (!/^\d{5}$/.test(zipForRpc)) {
      setError("Invalid zip code.");
      setLoading(false);
      return;
    }

    const radiusNum = parseInt(radius, 10);
    const snapshot = buildDealsSnapshot(itemsToFind);
    const previousSnapshot = previousDealsSearchSnapshotRef.current;

    dealsSearchMission.ensureMissionStarted({
      itemCount: snapshot.itemsSnapshot.length,
      mode: "deal_lookup",
      radiusMiles: snapshot.radiusMiles,
      selectedRetailers: Array.from(effectiveSelectedRetailers),
      surface: "deals",
      zipcode: snapshot.zipcode,
    });
    const startedAt = Date.now();

    try {
      const minDate = getLastWednesdayPST();
      const { results, filteredMenu } = await runSingleItemDealsSearch({
        searchTerm: searchTerms[0],
        zipCode: zipForRpc,
        radiusMiles: radiusNum,
        minDate,
      });

      setDealMenuCache(filteredMenu);

      if (filteredMenu.length === 0) {
        previousDealsSearchSnapshotRef.current = snapshot;
        void dealsSearchMission.recordAttempt({
          editSummary: buildSearchEditSummary(previousSnapshot, snapshot),
          filtersSnapshot: snapshot.filtersSnapshot,
          itemCount: snapshot.itemsSnapshot.length,
          itemsSnapshot: snapshot.itemsSnapshot,
          latencyMs: Math.max(0, Date.now() - startedAt),
          mode: "deal_lookup",
          partialResults: false,
          radiusMiles: snapshot.radiusMiles,
          requestId: null,
          resultsCount: 0,
          retailersReturnedCount: 0,
          selectedRetailers: Array.from(effectiveSelectedRetailers),
          surface: "deals",
          zipcode: snapshot.zipcode,
          zeroResults: true,
        });
        setError(
          "No recent deals found for this combination. Try broadening your search."
        );
        return;
      }

      const uniqueRetailers = getUniqueRetailersFromMenu(filteredMenu);
      setAvailableRetailers(uniqueRetailers);
      // Only auto-set selected retailers if user hasn't explicitly changed them
      if (!userModifiedRetailersRef.current) {
        setSelectedRetailers(new Set());
      }
      setSingleItemDeals(results);

      previousDealsSearchSnapshotRef.current = snapshot;
      void dealsSearchMission.recordAttempt({
        editSummary: buildSearchEditSummary(previousSnapshot, snapshot),
        filtersSnapshot: snapshot.filtersSnapshot,
        itemCount: snapshot.itemsSnapshot.length,
        itemsSnapshot: snapshot.itemsSnapshot,
        latencyMs: Math.max(0, Date.now() - startedAt),
        mode: "deal_lookup",
        partialResults: false,
        radiusMiles: snapshot.radiusMiles,
        requestId: null,
        resultsCount: results.length,
        retailersReturnedCount: uniqueRetailers.length,
        selectedRetailers: Array.from(effectiveSelectedRetailers),
        surface: "deals",
        zipcode: snapshot.zipcode,
        zeroResults: filteredMenu.length === 0,
      });
    } catch (err: unknown) {
      console.error("Search Error:", err);
      setError(getErrorMessage(err, "Failed to search deals."));
    } finally {
      setLoading(false);
    }
  };

  const parseSearchTerms = (query: string) => {
    const cleaned = query.replace(/;/g, " ").trim();
    return cleaned.length > 0 ? [cleaned] : [];
  };

  const resetToBrowseMode = () => {
    previousDealsSearchSnapshotRef.current = null;
    void dealsSearchMission.resolveMission(
      "abandoned",
      Array.from(effectiveSelectedRetailers)
    );
    setInitialSearchDone(false);
    setEditableCartItems([]);
    setSingleItemDeals([]);
    setDealMenuCache([]);
    setRefineSelected([]);
    setRefineDropdownOpen({});
    setRefineOpen(false);
    setSingleItemPage(1);
    setSortOption("none");
    setError(null);
    setLocationPanelOpen(false);
    setSelectedRetailers(new Set());
    userModifiedRetailersRef.current = false;
  };

  const submitSearch = async () => {
    const searchTerms = parseSearchTerms(searchQuery);

    if (searchTerms.length === 0) {
      resetToBrowseMode();
      return;
    }

    if (blockWhenGuestDealsLimitReached()) return;

    const initialItems: EditableCartItem[] = searchTerms.map((name) => ({
      name,
      brand: "",
      size: "",
      details: "",
    }));

    setEditableCartItems(initialItems);
    setInitialSearchDone(true);
    // Reset retailer filter so each new search shows results for all retailers
    // (per spec: changing the searched products clears any prior retailer pick).
    setSelectedRetailers(new Set());
    userModifiedRetailersRef.current = false;
    setRefineOpen(false);
    setRefineSelected(
      initialItems.map(() => ({
        brands: new Set<string>(),
        sizes: new Set<string>(),
        details: new Set<string>(),
      }))
    );

    await handleRunSearch(initialItems);
    setLocationPanelOpen(false);
  };

  const handleSearch = async (event: FormEvent) => {
    event.preventDefault();
    await submitSearch();
  };

  const handleReRunSearch = async () => {
    await handleRunSearch(editableCartItems);
  };

  const openBrowseSection = (section: {
    key: string;
    title: string;
    items: OptimizedCartItem[];
  }) => {
    navigate(
      buildDealsSectionUrl({
        sectionKey: section.key,
        zipCode: effectiveZip,
        selectedRetailers: effectiveSelectedRetailers,
      }),
      {
        state: {
          sectionKey: section.key,
          sectionTitle: section.title,
          items: section.items,
        },
      }
    );
  };

  return {
    addedItems,
    availableRetailers,
    browseSections,
    cartTotal,
    dealImagePlaceholder: DEAL_IMAGE_PLACEHOLDER,
    derivedSingleItemDeals,
    editableCartItems,
    effectiveZip,
    error,
    formatDistance,
    guestLimitDialogOpen,
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
    setGuestLimitDialogOpen,
    setItemSavedModalOpen,
    setLocationPanelOpen,
    setRefineOpen,
    setRefineOpenKey,
    setRefineSelected,
    setRetailersOpenPanel,
    setSearchQuery,
    setSelectedRetailers: ((action: Set<string> | ((prev: Set<string>) => Set<string>)) => {
      userModifiedRetailersRef.current = true;
      setSelectedRetailers(action);
    }) as typeof setSelectedRetailers,
    setSingleItemPage,
    setSortOption,
    setZipcode,
    setRadius,
    singleItemPage,
    singleItemTotalPages,
    sortOption,
    toggleLocationPanel,
    zipcode,
    activeDepartment,
  };
}
