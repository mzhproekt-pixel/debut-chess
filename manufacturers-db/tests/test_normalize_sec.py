from src.normalize.sec_edgar import SECEdgarNormalizer


def test_map_one_apple() -> None:
    raw = {
        "cik": "320193",
        "name": "Apple Inc.",
        "tickers": ["AAPL"],
        "ein": "942404110",
        "sic": "3571",
        "sicDescription": "Electronic Computers",
        "phone": "408-996-1010",
        "addresses": {
            "business": {
                "street1": "ONE APPLE PARK WAY",
                "city": "CUPERTINO",
                "stateOrCountry": "CA",
                "zipCode": "95014",
            },
            "mailing": {
                "street1": "ONE APPLE PARK WAY",
                "city": "CUPERTINO",
                "stateOrCountry": "CA",
                "zipCode": "95014",
            },
        },
    }
    out = SECEdgarNormalizer().map_one(raw)
    assert out is not None
    assert out["entity"]["name"] == "Apple Inc."
    assert out["entity"]["country_iso2"] == "US"
    assert out["entity"]["name_normalized"] == "apple inc"
    assert {"scheme": "us_cik", "value": "320193"} in out["identifiers"]
    assert {"scheme": "ticker", "value": "AAPL"} in out["identifiers"]
    assert out["contacts"] == [{"contact_type": "phone", "value": "408-996-1010"}]
    assert out["products"][0]["product_name"] == "Electronic Computers"
    assert len(out["addresses"]) == 2


def test_map_one_no_name_returns_none() -> None:
    assert SECEdgarNormalizer().map_one({"cik": 1}) is None
