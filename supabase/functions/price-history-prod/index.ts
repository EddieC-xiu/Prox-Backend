type FlyerDealRow = {
  id: number;
  match_key: string | null;
  brand: string | null;
  canonical_product_name: string | null;
  product_price: number | string | null;
  base_amount: number | string | null;
  base_unit: string | null;
  store_id: number | string | null;
  date_added: string | null;
  created_at: string | null;
  processed_at: string | null;
};

type PriceHistoryRow = {
  match_key: string;
  store_id: number | string;
  brand: string | null;
  canonical_product_name: string | null;
  size_oz: number | null;
  product_price: number;
  observed_at: string;
  observed_date: string;
};

type UpsertResult = {
  written: number;
  batches: number;
};

type SyncRpcRow = {
  synced_date: string;
  rows_written: number | string;
};

const SOURCE_TABLE = "flyer_deals";
const TARGET_TABLE = "price_history";
const FETCH_BATCH = 1000;
const WRITE_BATCH = 2000;
const MAX_RETRIES = 3;
const MAX_PRICE = 999999;
const MIN_REAL_SIZE_OZ = 1.5;

const SIZE_IN_NAME_RE = /(\d+(?:\.\d+)?)\s*(oz|fl\.?\s*oz|g|gram|lb|pound|ml|liter)\b/gi;

Deno.serve(async (req) => {
  const startedAt = new Date();

  try {
    const body = await readJson(req);
    const targetDate = normalizeTargetDate(body?.target_date) ?? yesterdayUtc();
    const dryRun = body?.dry_run === true;

    if (dryRun) {
      return jsonResponse({
        ok: true,
        dry_run: true,
        target_date: targetDate,
        note: "Dry run is not available in RPC mode. Run without dry_run to sync idempotently.",
        duration_ms: Date.now() - startedAt.getTime(),
      });
    }

    const result = await syncPriceHistoryForDate(targetDate);

    return jsonResponse({
      ok: true,
      dry_run: false,
      target_date: result.synced_date || targetDate,
      rows_written: Number(result.rows_written ?? 0),
      duration_ms: Date.now() - startedAt.getTime(),
    });
  } catch (error) {
    console.error("sync-price-history failed", error);
    return jsonResponse(
      {
        ok: false,
        error: error instanceof Error ? error.message : String(error),
      },
      500,
    );
  }
});

async function readJson(req: Request): Promise<Record<string, unknown>> {
  if (req.method === "GET") {
    const url = new URL(req.url);
    return {
      target_date: url.searchParams.get("target_date") ?? undefined,
      dry_run: url.searchParams.get("dry_run") === "true",
    };
  }

  try {
    return await req.json();
  } catch {
    return {};
  }
}

function normalizeTargetDate(value: unknown): string | null {
  if (typeof value !== "string" || !value.trim()) {
    return null;
  }
  const match = value.trim().match(/^(\d{4}-\d{2}-\d{2})/);
  return match ? match[1] : null;
}

function yesterdayUtc(): string {
  const d = new Date();
  d.setUTCDate(d.getUTCDate() - 1);
  return d.toISOString().slice(0, 10);
}

function nextDate(date: string): string {
  const d = new Date(`${date}T00:00:00.000Z`);
  d.setUTCDate(d.getUTCDate() + 1);
  return d.toISOString().slice(0, 10);
}

function supabaseConfig(): { url: string; key: string } {
  const url = Deno.env.get("SUPABASE_URL")?.replace(/\/$/, "");
  const key =
    Deno.env.get("SUPABASE_SERVICE_ROLE_KEY") ??
    Deno.env.get("SUPABASE_KEY");

  if (!url || !key) {
    throw new Error("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set.");
  }

  return { url, key };
}

function baseHeaders(extra?: HeadersInit): HeadersInit {
  const { key } = supabaseConfig();
  return {
    apikey: key,
    Authorization: `Bearer ${key}`,
    "Content-Type": "application/json",
    ...extra,
  };
}

async function syncPriceHistoryForDate(targetDate: string): Promise<SyncRpcRow> {
  const { url } = supabaseConfig();
  const res = await retry(async () => {
    const response = await fetch(`${url}/rest/v1/rpc/sync_price_history_for_date`, {
      method: "POST",
      headers: baseHeaders({
        Prefer: "return=representation",
      }),
      body: JSON.stringify({
        p_target_date: targetDate,
      }),
    });

    if (!response.ok) {
      throw new Error(`rpc sync failed: ${response.status} ${await response.text()}`);
    }

    return response;
  }, `sync_price_history_for_date ${targetDate}`);

  const data = await res.json();
  if (Array.isArray(data) && data.length > 0) {
    return data[0] as SyncRpcRow;
  }
  if (data && typeof data === "object") {
    return data as SyncRpcRow;
  }
  throw new Error(`rpc sync returned unexpected response: ${JSON.stringify(data)}`);
}

async function fetchAllRows(targetDate: string): Promise<FlyerDealRow[]> {
  const rows: FlyerDealRow[] = [];
  let lastSeenId = 0;

  while (true) {
    const batch = await retry(
      () => fetchRowsPage(targetDate, lastSeenId),
      `fetch processed_at after id ${lastSeenId}`,
    );

    rows.push(...batch);

    if (batch.length > 0) {
      lastSeenId = Math.max(...batch.map((row) => row.id));
      console.info(
        `fetched ${rows.length} flyer_deals rows for ${targetDate}; last_seen_id=${lastSeenId}`,
      );
    }

    if (batch.length < FETCH_BATCH) {
      break;
    }
  }

  return rows;
}

async function fetchRowsPage(
  targetDate: string,
  lastSeenId: number,
): Promise<FlyerDealRow[]> {
  const { url } = supabaseConfig();
  const params = new URLSearchParams({
    select: [
      "id",
      "match_key",
      "brand",
      "canonical_product_name",
      "product_price",
      "base_amount",
      "base_unit",
      "store_id",
      "date_added",
      "created_at",
      "processed_at",
    ].join(","),
    match_key: "not.is.null",
    store_id: "not.is.null",
    product_price: "gt.0",
    processed_at: `gte.${targetDate}T00:00:00+00:00`,
    id: `gt.${lastSeenId}`,
    limit: String(FETCH_BATCH),
    order: "id.asc",
  });
  params.append("processed_at", `lt.${nextDate(targetDate)}T00:00:00+00:00`);

  const res = await fetch(`${url}/rest/v1/${SOURCE_TABLE}?${params}`, {
    headers: baseHeaders(),
  });

  if (!res.ok) {
    throw new Error(`fetch failed: ${res.status} ${await res.text()}`);
  }

  return await res.json();
}

function makePriceHistoryRecord(
  row: FlyerDealRow,
  targetDate: string,
  observedAt: string,
): PriceHistoryRow | null {
  if (!row.match_key || row.store_id === null || row.store_id === undefined) {
    return null;
  }

  const observedDate = (row.processed_at ?? "").slice(0, 10);
  if (observedDate !== targetDate) {
    return null;
  }

  const price = Number(row.product_price);
  if (!Number.isFinite(price) || price <= 0 || price > MAX_PRICE) {
    return null;
  }

  return {
    match_key: row.match_key,
    store_id: row.store_id,
    brand: row.brand,
    canonical_product_name: row.canonical_product_name,
    size_oz: normalizeSizeOz(row.base_amount, row.base_unit, row.canonical_product_name ?? ""),
    product_price: price,
    observed_at: observedAt,
    observed_date: observedDate,
  };
}

function toOz(amount: number, unit: string): number | null {
  const u = unit.toLowerCase().replace(/\s+/g, "").replace(/\./g, "");
  if (u === "oz" || u === "floz") return round(amount);
  if (u === "g" || u === "gram") return round(amount * 0.035274);
  if (u === "lb" || u === "pound") return round(amount * 16);
  if (u === "ml") return round(amount * 0.033814);
  if (u === "l" || u === "liter") return round(amount * 33.814);
  return null;
}

function normalizeSizeOz(
  baseAmount: number | string | null,
  baseUnit: string | null,
  productName: string,
): number | null {
  let dbOz: number | null = null;
  const amount = Number(baseAmount);
  if (Number.isFinite(amount) && baseUnit) {
    dbOz = toOz(amount, baseUnit);
  }

  const nameCandidates: number[] = [];
  for (const match of productName.matchAll(SIZE_IN_NAME_RE)) {
    const oz = toOz(Number(match[1]), match[2]);
    if (oz !== null && oz >= MIN_REAL_SIZE_OZ) {
      nameCandidates.push(oz);
    }
  }

  const nameOz = nameCandidates.length ? Math.max(...nameCandidates) : null;
  if (dbOz !== null && dbOz >= MIN_REAL_SIZE_OZ) return dbOz;
  if (nameOz !== null) return nameOz;
  return dbOz;
}

function round(value: number): number {
  return Math.round(value * 100) / 100;
}

async function upsertPriceHistory(rows: PriceHistoryRow[]): Promise<UpsertResult> {
  if (!rows.length) {
    return { written: 0, batches: 0 };
  }

  const { url } = supabaseConfig();
  let written = 0;
  let batches = 0;

  for (let i = 0; i < rows.length; i += WRITE_BATCH) {
    const batch = rows.slice(i, i + WRITE_BATCH);
    await retry(async () => {
      const res = await fetch(
        `${url}/rest/v1/${TARGET_TABLE}?on_conflict=match_key,store_id,observed_date`,
        {
          method: "POST",
          headers: baseHeaders({
            Prefer: "resolution=merge-duplicates,return=minimal",
          }),
          body: JSON.stringify(batch),
        },
      );

      if (!res.ok) {
        throw new Error(`upsert failed: ${res.status} ${await res.text()}`);
      }
    }, `upsert rows ${i}-${i + batch.length - 1}`);

    written += batch.length;
    batches += 1;
    console.info(
      `upserted ${written}/${rows.length} price_history rows ` +
        `(${batches} batches, batch_size=${batch.length})`,
    );
  }

  return { written, batches };
}

async function retry<T>(fn: () => Promise<T>, label: string): Promise<T> {
  let lastError: unknown;

  for (let attempt = 1; attempt <= MAX_RETRIES; attempt += 1) {
    try {
      return await fn();
    } catch (error) {
      lastError = error;
      if (attempt === MAX_RETRIES) {
        break;
      }

      const delayMs = 500 * 2 ** (attempt - 1);
      console.warn(`${label} failed on attempt ${attempt}; retrying in ${delayMs}ms`, error);
      await new Promise((resolve) => setTimeout(resolve, delayMs));
    }
  }

  throw lastError;
}

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: {
      "Content-Type": "application/json",
    },
  });
}
