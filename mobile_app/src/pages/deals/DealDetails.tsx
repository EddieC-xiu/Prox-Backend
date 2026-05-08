import React, { useEffect, useState } from "react";
import { useParams, useNavigate, useSearchParams } from "react-router-dom";
import { ChevronLeft, MapPin, TrendingDown } from "lucide-react";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
} from "recharts";
import {
  getDealDetails,
  getPriceHistory,
  type DealDetails as DealDetailsType,
  type PriceHistory,
} from "@/services/proxApi";

const USD = new Intl.NumberFormat("en-US", {
  style: "currency",
  currency: "USD",
  minimumFractionDigits: 2,
});

function PriceTag({ label, price, highlight }: { label: string; price: number; highlight?: boolean }) {
  return (
    <div className={`flex flex-col items-center rounded-xl p-3 ${highlight ? "bg-green-50 border border-green-200" : "bg-gray-50"}`}>
      <span className="text-xs text-gray-500 mb-1">{label}</span>
      <span className={`font-bold text-lg ${highlight ? "text-green-700" : "text-gray-800"}`}>
        {USD.format(price)}
      </span>
    </div>
  );
}

export function DealDetails() {
  const { matchKey } = useParams<{ matchKey: string }>();
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const zipCode = searchParams.get("zip") ?? undefined;

  const [deal, setDeal] = useState<DealDetailsType | null>(null);
  const [history, setHistory] = useState<PriceHistory | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!matchKey) return;
    setLoading(true);
    setError(null);

    const decoded = decodeURIComponent(matchKey);

    Promise.all([
      getDealDetails(decoded, { zipCode, radiusMiles: 15 }),
      getPriceHistory(decoded, 90).catch(() => null),
    ])
      .then(([dealData, historyData]) => {
        setDeal(dealData);
        setHistory(historyData);
      })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [matchKey, zipCode]);

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-green-600" />
      </div>
    );
  }

  if (error || !deal) {
    return (
      <div className="flex flex-col items-center justify-center min-h-screen gap-4 px-6">
        <p className="text-gray-500 text-center">Could not load deal details.</p>
        <button onClick={() => navigate(-1)} className="text-green-700 font-medium">Go back</button>
      </div>
    );
  }

  const chartData = history?.history.map((p) => ({
    date: p.date.slice(5),
    price: p.min_price,
  })) ?? [];

  const savingsPct = deal.price_summary.median > 0
    ? Math.round(((deal.price_summary.median - deal.price_summary.min) / deal.price_summary.median) * 100)
    : 0;

  return (
    <div className="min-h-screen bg-white pb-24">
      {/* Header */}
      <div className="sticky top-0 z-10 bg-white border-b px-4 py-3 flex items-center gap-3">
        <button onClick={() => navigate(-1)} className="text-gray-700">
          <ChevronLeft size={24} />
        </button>
        <h1 className="font-semibold text-gray-900 capitalize truncate">
          {deal.canonical_name ?? "Deal Details"}
        </h1>
      </div>

      <div className="px-4 py-4 space-y-5">
        {/* Product image + basic info */}
        {deal.image_url && (
          <div className="flex justify-center">
            <img
              src={deal.image_url}
              alt={deal.canonical_name ?? "Product"}
              className="h-40 w-40 object-contain rounded-xl"
              onError={(e) => { (e.target as HTMLImageElement).style.display = "none"; }}
            />
          </div>
        )}

        <div>
          <p className="text-sm text-gray-500 uppercase tracking-wide">
            {deal.category ?? ""}{deal.brand ? ` · ${deal.brand}` : ""}
            {deal.display_size ? ` · ${deal.display_size}` : ""}
          </p>
          {deal.coupon_detail && (
            <span className="inline-block mt-1 px-2 py-0.5 bg-green-100 text-green-800 text-xs font-semibold rounded-full">
              {deal.coupon_detail}
            </span>
          )}
        </div>

        {/* Price summary */}
        <div className="grid grid-cols-3 gap-2">
          <PriceTag label="Best Nearby" price={deal.nearby_stores.length > 0 ? deal.nearby_stores[0].product_price : deal.price_summary.min} highlight />
          <PriceTag label="Avg Nationwide" price={deal.price_summary.median} />
          <PriceTag label="Most Expensive" price={deal.price_summary.max} />
        </div>

        {savingsPct > 0 && (
          <div className="flex items-center gap-2 bg-green-50 rounded-xl px-4 py-3">
            <TrendingDown size={18} className="text-green-600" />
            <p className="text-sm text-green-800 font-medium">
              {savingsPct}% below the national average at {deal.all_retailer_count} retailers
            </p>
          </div>
        )}

        {/* Nearby stores */}
        {deal.nearby_stores.length > 0 && (
          <div>
            <h2 className="font-semibold text-gray-900 mb-3">Available Nearby</h2>
            <div className="space-y-2">
              {deal.nearby_stores.map((store, i) => (
                <div
                  key={i}
                  className="flex items-center justify-between bg-gray-50 rounded-xl px-4 py-3"
                >
                  <div>
                    <p className="font-medium text-gray-900 text-sm">{store.retailer}</p>
                    <div className="flex items-center gap-1 text-xs text-gray-500 mt-0.5">
                      <MapPin size={11} />
                      <span>
                        {store.distance_miles != null
                          ? `${store.distance_miles.toFixed(1)} mi away`
                          : store.city ?? ""}
                      </span>
                    </div>
                  </div>
                  <div className="text-right">
                    <p className="font-bold text-gray-900">{USD.format(store.product_price)}</p>
                    {i === 0 && deal.nearby_stores.length > 1 && (
                      <p className="text-xs text-green-600 font-medium">Best nearby</p>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Price history chart */}
        {chartData.length > 1 && (
          <div>
            <h2 className="font-semibold text-gray-900 mb-1">Price History</h2>
            {history && (
              <p className="text-xs text-gray-500 mb-3">
                All-time low {USD.format(history.all_time_low)} · High {USD.format(history.all_time_high)}
              </p>
            )}
            <div className="bg-gray-50 rounded-xl p-3">
              <ResponsiveContainer width="100%" height={160}>
                <LineChart data={chartData}>
                  <XAxis dataKey="date" tick={{ fontSize: 10 }} tickLine={false} axisLine={false} />
                  <YAxis
                    tick={{ fontSize: 10 }}
                    tickLine={false}
                    axisLine={false}
                    tickFormatter={(v) => `$${v}`}
                    width={40}
                  />
                  <Tooltip formatter={(v: number) => USD.format(v)} labelFormatter={(l) => `Date: ${l}`} />
                  <Line
                    type="monotone"
                    dataKey="price"
                    stroke="#16a34a"
                    strokeWidth={2}
                    dot={false}
                    activeDot={{ r: 4 }}
                  />
                </LineChart>
              </ResponsiveContainer>
            </div>
            {chartData.length < 14 && (
              <p className="text-xs text-gray-400 mt-2 text-center">
                More history builds each week as prices are tracked
              </p>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
