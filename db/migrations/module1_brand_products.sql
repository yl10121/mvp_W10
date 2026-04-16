-- ================================================================
-- MODULE 1: Brand product catalog (live / simulated)
-- Same table for simulated seed data and future brand API payloads.
-- Consumers read by brand + optional data_source; no app code change
-- when switching from simulated rows to API-synced rows.
-- ================================================================

CREATE TABLE IF NOT EXISTS module1_brand_products (
    id              BIGSERIAL PRIMARY KEY,
    run_id          TEXT,
    brand           TEXT        NOT NULL,
    external_id     TEXT        NOT NULL,
    name            TEXT        NOT NULL,
    category        TEXT,
    description     TEXT,
    price_amount    NUMERIC(14, 2),
    currency        TEXT        DEFAULT 'EUR',
    product_url     TEXT        NOT NULL,
    image_urls      JSONB       DEFAULT '[]'::jsonb,
    attributes      JSONB       DEFAULT '{}'::jsonb,
    data_source     TEXT        NOT NULL DEFAULT 'simulated',
    raw_payload     JSONB       DEFAULT '{}'::jsonb,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (brand, external_id)
);

CREATE INDEX IF NOT EXISTS idx_m1_products_brand
    ON module1_brand_products (brand);
CREATE INDEX IF NOT EXISTS idx_m1_products_source
    ON module1_brand_products (data_source);
CREATE INDEX IF NOT EXISTS idx_m1_products_run
    ON module1_brand_products (run_id);

COMMENT ON TABLE module1_brand_products IS
    'M1-sourced brand catalog: simulated, crawler, or brand_api — same columns.';
COMMENT ON COLUMN module1_brand_products.external_id IS
    'Stable brand/SKU id for upserts when syncing from a real API.';
COMMENT ON COLUMN module1_brand_products.data_source IS
    'simulated | brand_api | crawler — informational, schema unchanged.';
COMMENT ON COLUMN module1_brand_products.raw_payload IS
    'Optional full vendor JSON for parity with future API responses.';
