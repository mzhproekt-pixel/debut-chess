from abc import ABC, abstractmethod
from typing import Any

from sqlalchemy import text

from src.db import get_connection
from src.logging_config import get_logger

log = get_logger(__name__)


class BaseNormalizer(ABC):
    """Reads raw rows from ``entity_sources`` for a given source and
    materialises them into the canonical tables (``entities``, …).

    Subclasses implement :meth:`map_one` returning a dict with keys:
      - ``entity``: dict of fields for ``entities`` table
      - ``identifiers``: list of {scheme, value}
      - ``addresses``: list of address dicts
      - ``contacts``: list of {contact_type, value}
      - ``officers``: list of officer dicts
      - ``financials``: list of {fiscal_year, metric, value_numeric, currency}
      - ``products``: list of {product_name, hs_code?, category?}
    """

    source_name: str

    @abstractmethod
    def map_one(self, raw: dict[str, Any]) -> dict[str, Any] | None:
        raise NotImplementedError

    def normalize_all(self, batch_size: int = 1000) -> int:
        log.info("normalize.start", source=self.source_name)
        processed = 0

        while True:
            with get_connection() as conn:
                rows = conn.execute(
                    text(
                        """
                        SELECT id, source_id, raw
                          FROM entity_sources
                         WHERE source = :source AND entity_id IS NULL
                         ORDER BY id
                         LIMIT :batch
                        """
                    ),
                    {"source": self.source_name, "batch": batch_size},
                ).fetchall()

                if not rows:
                    break

                for row in rows:
                    es_id, source_id, raw = row
                    mapped = self.map_one(raw)
                    if mapped is None:
                        continue

                    entity_id = self._upsert_entity(conn, mapped["entity"])
                    self._link_source(conn, es_id, entity_id)
                    self._upsert_identifiers(conn, entity_id, mapped.get("identifiers", []))
                    self._insert_addresses(conn, entity_id, mapped.get("addresses", []))
                    self._upsert_contacts(conn, entity_id, mapped.get("contacts", []))
                    self._insert_officers(conn, entity_id, mapped.get("officers", []))
                    self._upsert_financials(conn, entity_id, mapped.get("financials", []))
                    self._insert_products(conn, entity_id, mapped.get("products", []))
                    processed += 1

            log.info("normalize.progress", source=self.source_name, processed=processed)

        log.info("normalize.done", source=self.source_name, processed=processed)
        return processed

    # ── helpers ────────────────────────────────────────────────────────

    def _upsert_entity(self, conn, fields: dict[str, Any]) -> str:
        """Upsert by LEI when present, else insert a new row."""
        lei = fields.get("lei")
        if lei:
            existing = conn.execute(
                text("SELECT id FROM entities WHERE lei = :lei"), {"lei": lei}
            ).scalar_one_or_none()
            if existing:
                conn.execute(
                    text(
                        """
                        UPDATE entities SET
                            name = COALESCE(:name, name),
                            name_normalized = COALESCE(:name_normalized, name_normalized),
                            country_iso2 = COALESCE(:country_iso2, country_iso2),
                            status = COALESCE(:status, status),
                            legal_form = COALESCE(:legal_form, legal_form),
                            founded_date = COALESCE(:founded_date, founded_date),
                            website = COALESCE(:website, website),
                            updated_at = NOW()
                          WHERE id = :id
                        """
                    ),
                    {**fields, "id": existing},
                )
                return existing

        result = conn.execute(
            text(
                """
                INSERT INTO entities
                    (lei, name, name_normalized, country_iso2, status,
                     legal_form, founded_date, website)
                VALUES (:lei, :name, :name_normalized, :country_iso2, :status,
                        :legal_form, :founded_date, :website)
                RETURNING id
                """
            ),
            {
                "lei": fields.get("lei"),
                "name": fields["name"],
                "name_normalized": fields["name_normalized"],
                "country_iso2": fields.get("country_iso2"),
                "status": fields.get("status"),
                "legal_form": fields.get("legal_form"),
                "founded_date": fields.get("founded_date"),
                "website": fields.get("website"),
            },
        )
        return result.scalar_one()

    def _link_source(self, conn, source_row_id: int, entity_id: str) -> None:
        conn.execute(
            text("UPDATE entity_sources SET entity_id = :e WHERE id = :s"),
            {"e": entity_id, "s": source_row_id},
        )

    def _upsert_identifiers(self, conn, entity_id: str, items: list[dict]) -> None:
        for it in items:
            conn.execute(
                text(
                    """
                    INSERT INTO entity_identifiers (entity_id, scheme, value)
                    VALUES (:e, :s, :v)
                    ON CONFLICT (scheme, value) DO NOTHING
                    """
                ),
                {"e": entity_id, "s": it["scheme"], "v": it["value"]},
            )

    def _insert_addresses(self, conn, entity_id: str, items: list[dict]) -> None:
        for it in items:
            conn.execute(
                text(
                    """
                    INSERT INTO entity_addresses
                        (entity_id, address_type, country_iso2, region, city,
                         street, postal_code, raw_address, source)
                    VALUES (:e, :address_type, :country_iso2, :region, :city,
                            :street, :postal_code, :raw_address, :source)
                    """
                ),
                {"e": entity_id, "source": self.source_name, **{
                    k: it.get(k) for k in
                    ("address_type", "country_iso2", "region", "city",
                     "street", "postal_code", "raw_address")
                }},
            )

    def _upsert_contacts(self, conn, entity_id: str, items: list[dict]) -> None:
        for it in items:
            conn.execute(
                text(
                    """
                    INSERT INTO entity_contacts (entity_id, contact_type, value, source)
                    VALUES (:e, :t, :v, :src)
                    ON CONFLICT (entity_id, contact_type, value) DO NOTHING
                    """
                ),
                {"e": entity_id, "t": it["contact_type"], "v": it["value"],
                 "src": self.source_name},
            )

    def _insert_officers(self, conn, entity_id: str, items: list[dict]) -> None:
        for it in items:
            conn.execute(
                text(
                    """
                    INSERT INTO entity_officers
                        (entity_id, role, name, appointed, resigned, source)
                    VALUES (:e, :role, :name, :appointed, :resigned, :src)
                    """
                ),
                {"e": entity_id, "src": self.source_name, **{
                    k: it.get(k) for k in ("role", "name", "appointed", "resigned")
                }},
            )

    def _upsert_financials(self, conn, entity_id: str, items: list[dict]) -> None:
        for it in items:
            conn.execute(
                text(
                    """
                    INSERT INTO entity_financials
                        (entity_id, fiscal_year, metric, value_numeric, currency, source)
                    VALUES (:e, :y, :m, :v, :c, :src)
                    ON CONFLICT (entity_id, fiscal_year, metric) DO UPDATE
                      SET value_numeric = EXCLUDED.value_numeric,
                          currency = EXCLUDED.currency,
                          source = EXCLUDED.source
                    """
                ),
                {"e": entity_id, "src": self.source_name,
                 "y": it["fiscal_year"], "m": it["metric"],
                 "v": it.get("value_numeric"), "c": it.get("currency")},
            )

    def _insert_products(self, conn, entity_id: str, items: list[dict]) -> None:
        for it in items:
            conn.execute(
                text(
                    """
                    INSERT INTO entity_products
                        (entity_id, product_name, hs_code, category, source)
                    VALUES (:e, :name, :hs, :cat, :src)
                    """
                ),
                {"e": entity_id, "src": self.source_name,
                 "name": it["product_name"],
                 "hs": it.get("hs_code"), "cat": it.get("category")},
            )
