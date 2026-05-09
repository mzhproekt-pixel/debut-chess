from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.engine import Connection, Engine

from src.settings import settings

_engine: Engine | None = None


def get_engine() -> Engine:
    global _engine
    if _engine is None:
        _engine = create_engine(
            settings.database_url,
            pool_pre_ping=True,
            pool_size=5,
            max_overflow=10,
        )
    return _engine


@contextmanager
def get_connection() -> Iterator[Connection]:
    conn = get_engine().connect()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def text_normalize(name: str) -> str:
    """Lightweight name normalization for matching.

    Keeps Latin and Cyrillic letters (KZ/RU sources), strips diacritics
    and punctuation, lowercases, collapses whitespace.
    """
    import re
    import unicodedata

    s = unicodedata.normalize("NFKD", name)
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = s.lower()
    # keep ASCII alnum + Cyrillic (basic + supplement) + spaces
    s = re.sub(r"[^a-z0-9Ѐ-ӿ ]+", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s
