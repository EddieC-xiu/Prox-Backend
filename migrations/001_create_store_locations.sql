CREATE TABLE IF NOT EXISTS store_locations (
    id          SERIAL PRIMARY KEY,
    retailer    TEXT NOT NULL,
    retailer_key TEXT,
    address     TEXT,
    zip_code    TEXT,
    lat         DOUBLE PRECISION,
    lng         DOUBLE PRECISION,
    geocoded_at TIMESTAMP WITH TIME ZONE,
    geocode_source TEXT DEFAULT 'nominatim',
    created_at  TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE (retailer_key, address)
);