-- Global Manufacturers Database — canonical schema
-- PostgreSQL 16+

CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE EXTENSION IF NOT EXISTS pgcrypto;
CREATE EXTENSION IF NOT EXISTS unaccent;

-- ──────────────────────────────────────────────────────────────────────
-- entities: canonical record per company (after dedupe)
-- ──────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS entities (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    lei             TEXT UNIQUE,
    name            TEXT NOT NULL,
    name_normalized TEXT NOT NULL,
    country_iso2    CHAR(2),
    status          TEXT,
    legal_form      TEXT,
    founded_date    DATE,
    website         TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_entities_country
    ON entities(country_iso2);
CREATE INDEX IF NOT EXISTS idx_entities_name_trgm
    ON entities USING gin (name_normalized gin_trgm_ops);

-- ──────────────────────────────────────────────────────────────────────
-- entity_sources: raw record per source (1 entity → N source rows)
-- ──────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS entity_sources (
    id          BIGSERIAL PRIMARY KEY,
    entity_id   UUID REFERENCES entities(id) ON DELETE CASCADE,
    source      TEXT NOT NULL,
    source_id   TEXT NOT NULL,
    raw         JSONB NOT NULL,
    fetched_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (source, source_id)
);

CREATE INDEX IF NOT EXISTS idx_entity_sources_entity
    ON entity_sources(entity_id);
CREATE INDEX IF NOT EXISTS idx_entity_sources_source
    ON entity_sources(source);

-- ──────────────────────────────────────────────────────────────────────
-- entity_identifiers: country-specific IDs (БИН, ИНН, EIN, CRN, …)
-- ──────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS entity_identifiers (
    entity_id   UUID NOT NULL REFERENCES entities(id) ON DELETE CASCADE,
    scheme      TEXT NOT NULL,
    value       TEXT NOT NULL,
    PRIMARY KEY (scheme, value)
);

CREATE INDEX IF NOT EXISTS idx_entity_identifiers_entity
    ON entity_identifiers(entity_id);

-- ──────────────────────────────────────────────────────────────────────
-- entity_addresses
-- ──────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS entity_addresses (
    id            BIGSERIAL PRIMARY KEY,
    entity_id     UUID NOT NULL REFERENCES entities(id) ON DELETE CASCADE,
    address_type  TEXT,
    country_iso2  CHAR(2),
    region        TEXT,
    city          TEXT,
    street        TEXT,
    postal_code   TEXT,
    raw_address   TEXT,
    source        TEXT
);

CREATE INDEX IF NOT EXISTS idx_entity_addresses_entity
    ON entity_addresses(entity_id);

-- ──────────────────────────────────────────────────────────────────────
-- entity_contacts: phones, emails, fax
-- ──────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS entity_contacts (
    entity_id    UUID NOT NULL REFERENCES entities(id) ON DELETE CASCADE,
    contact_type TEXT NOT NULL,
    value        TEXT NOT NULL,
    source       TEXT,
    PRIMARY KEY (entity_id, contact_type, value)
);

-- ──────────────────────────────────────────────────────────────────────
-- entity_officers: directors, officers, beneficial owners
-- ──────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS entity_officers (
    id          BIGSERIAL PRIMARY KEY,
    entity_id   UUID NOT NULL REFERENCES entities(id) ON DELETE CASCADE,
    role        TEXT,
    name        TEXT NOT NULL,
    appointed   DATE,
    resigned    DATE,
    source      TEXT
);

CREATE INDEX IF NOT EXISTS idx_entity_officers_entity
    ON entity_officers(entity_id);

-- ──────────────────────────────────────────────────────────────────────
-- entity_financials: yearly metrics (revenue, employees, …)
-- ──────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS entity_financials (
    entity_id     UUID NOT NULL REFERENCES entities(id) ON DELETE CASCADE,
    fiscal_year   INT NOT NULL,
    metric        TEXT NOT NULL,
    value_numeric NUMERIC,
    currency      CHAR(3),
    source        TEXT,
    PRIMARY KEY (entity_id, fiscal_year, metric)
);

-- ──────────────────────────────────────────────────────────────────────
-- entity_products: product catalog (what the entity manufactures)
-- ──────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS entity_products (
    id           BIGSERIAL PRIMARY KEY,
    entity_id    UUID NOT NULL REFERENCES entities(id) ON DELETE CASCADE,
    product_name TEXT NOT NULL,
    hs_code      TEXT,
    category     TEXT,
    source       TEXT
);

CREATE INDEX IF NOT EXISTS idx_entity_products_entity
    ON entity_products(entity_id);
CREATE INDEX IF NOT EXISTS idx_entity_products_hs
    ON entity_products(hs_code);

-- ──────────────────────────────────────────────────────────────────────
-- trade_flows: aggregate import/export from UN Comtrade
-- (not linked to specific entities — country×HS×year aggregates)
-- ──────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS trade_flows (
    id              BIGSERIAL PRIMARY KEY,
    reporter_iso2   CHAR(2) NOT NULL,
    partner_iso2    CHAR(2),
    flow            TEXT NOT NULL CHECK (flow IN ('import', 'export', 're-import', 're-export')),
    hs_code         TEXT NOT NULL,
    year            INT NOT NULL,
    trade_value_usd NUMERIC,
    net_weight_kg   NUMERIC,
    UNIQUE (reporter_iso2, partner_iso2, flow, hs_code, year)
);

CREATE INDEX IF NOT EXISTS idx_trade_flows_hs_year
    ON trade_flows(hs_code, year);
CREATE INDEX IF NOT EXISTS idx_trade_flows_reporter
    ON trade_flows(reporter_iso2, year);

-- ──────────────────────────────────────────────────────────────────────
-- entity_matches: dedupe candidate pairs (output of Splink)
-- ──────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS entity_matches (
    entity_a    UUID NOT NULL REFERENCES entities(id) ON DELETE CASCADE,
    entity_b    UUID NOT NULL REFERENCES entities(id) ON DELETE CASCADE,
    match_score FLOAT NOT NULL,
    reviewed    BOOLEAN NOT NULL DEFAULT FALSE,
    is_match    BOOLEAN,
    PRIMARY KEY (entity_a, entity_b),
    CHECK (entity_a < entity_b)
);

-- ──────────────────────────────────────────────────────────────────────
-- ingestion_runs: provenance of pipeline runs (for monitoring)
-- ──────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS ingestion_runs (
    id              BIGSERIAL PRIMARY KEY,
    source          TEXT NOT NULL,
    started_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    finished_at     TIMESTAMPTZ,
    status          TEXT NOT NULL DEFAULT 'running'
                    CHECK (status IN ('running', 'success', 'error')),
    records_ingested INT NOT NULL DEFAULT 0,
    error_message   TEXT
);

CREATE INDEX IF NOT EXISTS idx_ingestion_runs_source_started
    ON ingestion_runs(source, started_at DESC);
