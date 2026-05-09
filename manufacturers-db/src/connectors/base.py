from abc import ABC, abstractmethod
from collections.abc import Iterator
from typing import Any

from sqlalchemy import text

from src.db import get_connection
from src.logging_config import get_logger

log = get_logger(__name__)


class BaseConnector(ABC):
    """One connector per data source.

    Subclasses implement :meth:`fetch` as an iterator yielding
    ``(source_id, raw_record)`` tuples. The base class handles upserting
    them into ``entity_sources`` and tracking the run in ``ingestion_runs``.
    """

    source_name: str

    @abstractmethod
    def fetch(self, **kwargs: Any) -> Iterator[tuple[str, dict[str, Any]]]:
        """Yield (source_id, raw_dict) for each record from the upstream API."""
        raise NotImplementedError

    def ingest(self, **kwargs: Any) -> int:
        """Run :meth:`fetch` and persist results. Returns count ingested."""
        log.info("ingest.start", source=self.source_name)

        with get_connection() as conn:
            run_id = conn.execute(
                text(
                    "INSERT INTO ingestion_runs (source) VALUES (:s) RETURNING id"
                ),
                {"s": self.source_name},
            ).scalar_one()

        count = 0
        try:
            with get_connection() as conn:
                for source_id, raw in self.fetch(**kwargs):
                    conn.execute(
                        text(
                            """
                            INSERT INTO entity_sources (source, source_id, raw, fetched_at)
                            VALUES (:source, :source_id, CAST(:raw AS JSONB), NOW())
                            ON CONFLICT (source, source_id) DO UPDATE
                              SET raw = EXCLUDED.raw,
                                  fetched_at = EXCLUDED.fetched_at
                            """
                        ),
                        {
                            "source": self.source_name,
                            "source_id": source_id,
                            "raw": _json_dumps(raw),
                        },
                    )
                    count += 1
                    if count % 1000 == 0:
                        conn.commit()
                        log.info("ingest.progress", source=self.source_name, count=count)

            with get_connection() as conn:
                conn.execute(
                    text(
                        """
                        UPDATE ingestion_runs
                           SET finished_at = NOW(),
                               status = 'success',
                               records_ingested = :n
                         WHERE id = :id
                        """
                    ),
                    {"n": count, "id": run_id},
                )
            log.info("ingest.done", source=self.source_name, count=count)
        except Exception as exc:
            with get_connection() as conn:
                conn.execute(
                    text(
                        """
                        UPDATE ingestion_runs
                           SET finished_at = NOW(),
                               status = 'error',
                               records_ingested = :n,
                               error_message = :msg
                         WHERE id = :id
                        """
                    ),
                    {"n": count, "id": run_id, "msg": str(exc)[:2000]},
                )
            log.error("ingest.failed", source=self.source_name, error=str(exc))
            raise

        return count


def _json_dumps(obj: Any) -> str:
    import json

    return json.dumps(obj, ensure_ascii=False, default=str)
