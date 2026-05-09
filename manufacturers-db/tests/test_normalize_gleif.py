"""Pure-function tests for the GLEIF normalizer (no DB needed)."""

from src.normalize.gleif import GLEIFNormalizer


def test_map_one_minimal() -> None:
    raw = {
        "id": "353800F8R6V31KMVKW82",
        "type": "lei-records",
        "attributes": {
            "lei": "353800F8R6V31KMVKW82",
            "entity": {
                "legalName": {"name": "ACME Corporation", "language": "en"},
                "legalAddress": {
                    "country": "US",
                    "city": "Wilmington",
                    "region": "US-DE",
                    "postalCode": "19801",
                    "addressLines": ["1 Main St"],
                },
                "status": "ACTIVE",
                "creationDate": "2014-06-01T00:00:00Z",
                "legalForm": {"id": "8888"},
            },
        },
    }
    out = GLEIFNormalizer().map_one(raw)
    assert out is not None
    assert out["entity"]["lei"] == "353800F8R6V31KMVKW82"
    assert out["entity"]["name"] == "ACME Corporation"
    assert out["entity"]["name_normalized"] == "acme corporation"
    assert out["entity"]["country_iso2"] == "US"
    assert out["entity"]["status"] == "active"
    assert out["entity"]["founded_date"] == "2014-06-01"
    assert {"scheme": "lei", "value": "353800F8R6V31KMVKW82"} in out["identifiers"]
    assert len(out["addresses"]) == 1
    assert out["addresses"][0]["city"] == "Wilmington"


def test_map_one_missing_name_returns_none() -> None:
    raw = {"id": "X", "attributes": {"entity": {}}}
    assert GLEIFNormalizer().map_one(raw) is None


def test_map_one_with_separate_hq_address() -> None:
    raw = {
        "id": "ABC",
        "attributes": {
            "lei": "ABC",
            "entity": {
                "legalName": {"name": "Foo Ltd"},
                "legalAddress": {"country": "GB", "city": "London"},
                "headquartersAddress": {"country": "DE", "city": "Berlin"},
            },
        },
    }
    out = GLEIFNormalizer().map_one(raw)
    assert out is not None
    assert len(out["addresses"]) == 2
    types = sorted(a["address_type"] for a in out["addresses"])
    assert types == ["headquarters", "registered"]
