from src.db import text_normalize


def test_unicode_normalization() -> None:
    assert text_normalize("Müller GmbH") == "muller gmbh"
    assert text_normalize("ACME, Inc.") == "acme inc"
    assert text_normalize("  Foo   Bar  ") == "foo bar"
    assert text_normalize("ТОО «Дебют»") == "тоо дебют"
    # NFKD decomposes № to "No"
    assert text_normalize("ООО Завод-Электрик №3") == "ооо завод электрик no3"
