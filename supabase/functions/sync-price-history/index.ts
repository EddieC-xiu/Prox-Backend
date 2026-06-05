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

const SOURCE_TABLE = "flyer_deals";
const TARGET_TABLE = "price_history";
const FETCH_BATCH = 1000;
const WRITE_BATCH = 500;
const MAX_RETRIES = 3;
const MAX_PRICE = 999999;
const MIN_REAL_SIZE_OZ = 1.5;

const SIZE_IN_NAME_RE = /(\d+(?:\.\d+)?)\s*(oz|fl\.?\s*oz|g|gram|lb|pound|ml|liter)\b/gi;

Deno.serve(async (req) => {
  const startedAt = new Date();

  try {
    const body = await readJson(req);
    const targetDate = normalizeTargetDate(body?.target_date) ?? yesterdayUtc();
    const observedAt = startedAt.toISOString();

    const grouped = new Map<string, PriceHistoryRow>();
    let fetched = 0;
    let skipped = 0;

    const rows = await fetchAllRows(targetDate);

    for (const row of rows) {
      fetched += 1;

      const record = makePriceHistoryRecord(row, targetDate, observedAt);
      if (!record) {
        skipped += 1;
        continue;
      }

      const key = `${record.match_key}|${record.store_id}|${record.observed_date}`;
      const existing = grouped.get(key);
      if (!existing || record.product_price < existing.product_price) {
        grouped.set(key, record);
      }
    }

    const rowsToWrite = [...grouped.values()];
    const dryRun = body?.dry_run === true;
    const written = dryRun ? rowsToWrite.length : await upsertPriceHistory(rowsToWrite);

    return jsonResponse({
      ok: true,
      dry_run: dryRun,
      target_date: targetDate,
      fetched,
      grouped: rowsToWrite.length,
      written,
      skipped,
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

async function fetchAllRows(targetDate: string): Promise<FlyerDealRow[]> {
  const rows: FlyerDealRow[] = [];

  for (let offset = 0; ; offset += FETCH_BATCH) {
    const batch = await retry(
      () => fetchRowsPage(targetDate, offset),
      `fetch processed_at offset ${offset}`,
    );

    rows.push(...batch);

    if (batch.length < FETCH_BATCH) {
      break;
    }
  }

  return rows;
}

async function fetchRowsPage(
  targetDate: string,
  offset: number,
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
    offset: String(offset),
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

async function upsertPriceHistory(rows: PriceHistoryRow[]): Promise<number> {
  if (!rows.length) {
    return 0;
  }

  const { url } = supabaseConfig();
  let written = 0;

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
  }

  return written;
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
