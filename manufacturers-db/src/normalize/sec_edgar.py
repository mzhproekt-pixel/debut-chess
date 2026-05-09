"""Normalize SEC EDGAR submissions JSON.

A submission record looks like::

    {
        "cik": "0000320193",
        "entityType": "operating",
        "sic": "3571",
        "sicDescription": "Electronic Computers",
        "name": "Apple Inc.",
        "tickers": ["AAPL"],
        "exchanges": ["Nasdaq"],
        "ein": "942404110",
        "addresses": {
            "mailing": {...},
            "business": {...}
        },
        "phone": "...",
        "filings": {...}
    }
"""

from typing import Any

from src.db import text_normalize
from src.normalize.base import BaseNormalizer


class SECEdgarNormalizer(BaseNormalizer):
    source_name = "sec_edgar"

    def map_one(self, raw: dict[str, Any]) -> dict[str, Any] | None:
        name = (raw.get("name") or "").strip()
        if not name:
            return None

        cik = raw.get("cik")
        ein = raw.get("ein")

        identifiers = []
        if cik:
            identifiers.append({"scheme": "us_cik", "value": str(cik).lstrip("0") or "0"})
        if ein:
            identifiers.append({"scheme": "us_ein", "value": str(ein)})
        for ticker in (raw.get("tickers") or []):
            identifiers.append({"scheme": "ticker", "value": str(ticker)})

        addresses = []
        for kind in ("business", "mailing"):
            a = (raw.get("addresses") or {}).get(kind)
            if a:
                addresses.append(self._addr(a, kind))

        contacts = []
        phone = raw.get("phone")
        if phone:
            contacts.append({"contact_type": "phone", "value": str(phone)})

        sic = raw.get("sic")
        sic_desc = raw.get("sicDescription")
        products = []
        if sic_desc:
            products.append({
                "product_name": sic_desc,
                "category": f"SIC:{sic}" if sic else None,
            })

        return {
            "entity": {
                "lei": None,
                "name": name,
                "name_normalized": text_normalize(name),
                "country_iso2": "US",
                "status": (raw.get("entityType") or "").lower() or None,
                "legal_form": None,
                "founded_date": None,
                "website": (raw.get("website") or None),
            },
            "identifiers": identifiers,
            "addresses": addresses,
            "contacts": contacts,
            "officers": [],
            "financials": [],
            "products": products,
        }

    @staticmethod
    def _addr(a: dict[str, Any], kind: str) -> dict[str, Any]:
        street = ", ".join(s for s in [a.get("street1"), a.get("street2")] if s) or None
        # SEC's stateOrCountry is a US state code for domestic filers (e.g. "CA")
        # and a country code for foreign private issuers — assume US for now and
        # let downstream enrichment correct it.
        return {
            "address_type": kind,
            "country_iso2": "US",
            "region": a.get("stateOrCountry"),
            "city": a.get("city"),
            "street": street,
            "postal_code": a.get("zipCode"),
            "raw_address": ", ".join(
                p for p in [
                    street, a.get("city"), a.get("stateOrCountry"), a.get("zipCode"),
                ] if p
            ) or None,
        }
