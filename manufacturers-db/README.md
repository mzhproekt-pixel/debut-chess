# Global Manufacturers DB — MVP

Aggregated database of manufacturers worldwide, built from **free open sources**:
GLEIF, SEC EDGAR, UN Comtrade (and more — see roadmap).

Output: PostgreSQL + CSV exports. No web UI, no bot — pure data pipeline.

> **Status: scaffolded MVP.** GLEIF, SEC EDGAR, and UN Comtrade connectors
> are wired end-to-end. Other sources from the plan (Companies House,
> ЕГРЮЛ РФ, egov.kz, Wikidata, OpenSanctions, OpenCorporates) are stubbed
> in the directory layout but not yet implemented.

---

## Quick start

```bash
# 1. Install dependencies
python3.11 -m venv .venv
source .venv/bin/activate
pip install -e .                 # core
pip install -e ".[dev,resolve]"  # for tests + Splink dedupe

# 2. Configure
cp .env.example .env
# Edit .env — at minimum set HTTP_USER_AGENT to your real contact email.
# (SEC EDGAR will reject requests with the default placeholder.)

# 3. Start PostgreSQL locally
docker compose up -d
# Adminer UI: http://localhost:8080  (server=postgres user=mdb pw=mdb db=manufacturers)

# 4. Apply schema
python -m src init-db

# 5. Smoke test — pull 1000 LEI records from Kazakhstan
python -m src ingest gleif --country KZ --limit 1000
python -m src normalize gleif

# 6. Pull a few US public companies (SEC EDGAR)
python -m src ingest sec --limit 50
python -m src normalize sec

# 7. Pull aggregate import data for Kazakhstan, 2022-2024
python -m src trade --years 2022 --years 2023 --years 2024 --reporter 398

# 8. Export to CSV
python -m src export-list
python -m src export manufacturers_basic
ls -lh exports/
```

---

## Architecture

```
            ┌─────────────┐
            │  Connectors │  (one per source — pulls raw JSON)
            └──────┬──────┘
                   ▼
      ┌────────────────────────┐
      │  entity_sources (raw)  │   ← idempotent upsert by (source, source_id)
      └──────────┬─────────────┘
                 ▼
            ┌──────────┐
            │Normalizer│  (maps raw → canonical tables per source)
            └────┬─────┘
                 ▼
   ┌──────────────────────────────────┐
   │  entities + entity_addresses +   │
   │  entity_contacts + financials +  │
   │  identifiers + products + …      │
   └──────────┬───────────────────────┘
              ▼
       ┌────────────┐         ┌─────────────┐
       │  Resolve   │────────▶│ Export → CSV│
       │  (Splink)  │         └─────────────┘
       └────────────┘
```

### Pipeline stages

| Stage | Command | What it does |
|-------|---------|---|
| **Ingest** | `mdb ingest <source>` | Fetch raw JSON, store in `entity_sources` (idempotent) |
| **Normalize** | `mdb normalize <source>` | Map source schema → canonical tables |
| **Resolve** | _not implemented yet_ | Splink dedupe across sources, populate `entity_matches` |
| **Trade** | `mdb trade --years YYYY` | Pull UN Comtrade aggregate flows into `trade_flows` |
| **Export** | `mdb export <view>` | Run a SQL view from `sql/exports/` and write CSV |

---

## Schema

Defined in [`sql/schema.sql`](sql/schema.sql). Highlights:

- **`entities`** — canonical company (after dedupe). Unique by LEI when present.
- **`entity_sources`** — raw JSONB per source, links back to entity for provenance.
- **`entity_identifiers`** — country-specific IDs (БИН, ИНН, EIN, CRN, ticker, LEI…).
- **`entity_addresses`**, **`entity_contacts`**, **`entity_officers`**,
  **`entity_financials`**, **`entity_products`** — child tables.
- **`trade_flows`** — country×HS×year aggregates from UN Comtrade.
- **`entity_matches`** — dedupe candidate pairs (Splink output).
- **`ingestion_runs`** — provenance/observability.

---

## Implemented connectors

| Source | Status | Coverage | Auth |
|--------|--------|----------|------|
| **GLEIF** | ✅ ingest + normalize | 2.5M legal entities globally with LEI | none |
| **SEC EDGAR** | ✅ ingest + normalize | ~30K US public filers | User-Agent only |
| **UN Comtrade** | ✅ direct write to `trade_flows` | bilateral trade, all UN countries | optional key for higher rate |

## Stubs / planned

Per the [plan](../../.claude/plans/snazzy-enchanting-jellyfish.md):

- UK Companies House (free API, requires registration key)
- OpenCorporates (free tier — basic search)
- Kazakhstan egov.kz / stat.gov.kz
- ФНС РФ ЕГРЮЛ open data
- Wikidata SPARQL (enrichment)
- OpenSanctions
- Splink-based entity resolution

Each of these is a roughly self-contained connector module —
add a class under `src/connectors/<name>.py` extending `BaseConnector`
and a matching normalizer under `src/normalize/<name>.py`.

---

## Adding a new connector

1. Create `src/connectors/<source>.py`:
   ```python
   class MySourceConnector(BaseConnector):
       source_name = "my_source"

       def fetch(self, **kwargs):
           # yield (source_id, raw_dict) tuples
           ...
   ```
2. Create `src/normalize/<source>.py`:
   ```python
   class MySourceNormalizer(BaseNormalizer):
       source_name = "my_source"

       def map_one(self, raw):
           return {
               "entity": {"name": ..., "name_normalized": ..., ...},
               "identifiers": [...],
               "addresses": [...],
               # ...
           }
   ```
3. Register in `src/cli.py` (`CONNECTORS` and `NORMALIZERS` dicts).
4. Add tests in `tests/test_normalize_<source>.py`.

---

## Operational notes

- **Rate limits:** GLEIF is generous; SEC enforces 10 req/sec and rejects
  bad User-Agents; UN Comtrade preview tier = 500 calls/day.
- **Storage estimate:** 10M entities ≈ 30–50 GB on Postgres with full JSONB raw retained.
- **Cron:** wire `scripts/cron.sh` to your scheduler — see template.
- **Legal:** all sources here are open / public-domain / freely licensed.
  Do not add scraping of Alibaba/Made-in-China etc. without legal review.

---

## Development

```bash
pip install -e ".[dev]"
pytest             # 6 tests, all DB-free
ruff check src/
mypy src/
```

---

## License

TBD.
