"""Normalize raw GLEIF JSON:API records into canonical schema.

A GLEIF record looks like::

    {
        "id": "353800F8R6V31KMVKW82",
        "attributes": {
            "lei": "353800F8R6V31KMVKW82",
            "entity": {
                "legalName": {"name": "ACME ...", "language": "en"},
                "legalAddress": {"country": "US", "city": "...", ...},
                "headquartersAddress": {...},
                "registeredAt": {"id": "RA000665"},
                "registeredAs": "12345678",
                "jurisdiction": "US-DE",
                "category": "GENERAL",
                "legalForm": {"id": "8888"},
                "status": "ACTIVE",
                "creationDate": "2014-...",
            },
            "registration": {"status": "ISSUED", ...},
            ...
        }
    }
"""

from typing import Any

from src.db import text_normalize
from src.normalize.base import BaseNormalizer


class GLEIFNormalizer(BaseNormalizer):
    source_name = "gleif"

    def map_one(self, raw: dict[str, Any]) -> dict[str, Any] | None:
        attrs = raw.get("attributes") or {}
        entity = attrs.get("entity") or {}
        if not entity:
            return None

        legal_name = ((entity.get("legalName") or {}).get("name") or "").strip()
        if not legal_name:
            return None

        lei = attrs.get("lei") or raw.get("id")
        legal_addr = entity.get("legalAddress") or {}
        hq_addr = entity.get("headquartersAddress") or {}
        country = (legal_addr.get("country") or "").upper() or None

        founded = self._parse_date(entity.get("creationDate"))

        identifiers: list[dict[str, Any]] = []
        if lei:
            identifiers.append({"scheme": "lei", "value": lei})
        registered_as = entity.get("registeredAs")
        registered_at = (entity.get("registeredAt") or {}).get("id")
        if registered_as and registered_at:
            identifiers.append({
                "scheme": f"gleif_ra:{registered_at}",
                "value": str(registered_as),
            })

        addresses: list[dict[str, Any]] = []
        if legal_addr:
            addresses.append(self._addr(legal_addr, "registered"))
        if hq_addr and hq_addr != legal_addr:
            addresses.append(self._addr(hq_addr, "headquarters"))

        return {
            "entity": {
                "lei": lei,
                "name": legal_name,
                "name_normalized": text_normalize(legal_name),
                "country_iso2": country,
                "status": (entity.get("status") or "").lower() or None,
                "legal_form": (entity.get("legalForm") or {}).get("id"),
                "founded_date": founded,
                "website": None,  # GLEIF does not provide it
            },
            "identifiers": identifiers,
            "addresses": addresses,
            "contacts": [],
            "officers": [],
            "financials": [],
            "products": [],
        }

    @staticmethod
    def _addr(a: dict[str, Any], kind: str) -> dict[str, Any]:
        lines = a.get("addressLines") or []
        street = ", ".join(line for line in lines if line) or None
        return {
            "address_type": kind,
            "country_iso2": (a.get("country") or "").upper() or None,
            "region": a.get("region"),
            "city": a.get("city"),
            "street": street,
            "postal_code": a.get("postalCode"),
            "raw_address": ", ".join(
                p for p in [
                    street, a.get("city"), a.get("region"),
                    a.get("postalCode"), a.get("country"),
                ] if p
            ) or None,
        }

    @staticmethod
    def _parse_date(s: str | None) -> str | None:
        if not s:
            return None
        # GLEIF dates are ISO 8601, sometimes with timezone offsets.
        return s[:10] if len(s) >= 10 else None
