"""GLEIF — Global Legal Entity Identifier Foundation.

Free, public API. No auth. ~2.5M legal entities globally.
Docs: https://api.gleif.org/docs
"""

from collections.abc import Iterator
from typing import Any

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from src.connectors.base import BaseConnector
from src.logging_config import get_logger
from src.settings import settings

log = get_logger(__name__)

GLEIF_API_BASE = "https://api.gleif.org/api/v1"
PAGE_SIZE = 200  # GLEIF max


class GLEIFConnector(BaseConnector):
    source_name = "gleif"

    def fetch(
        self,
        country: str | None = None,
        limit: int | None = None,
        **_: Any,
    ) -> Iterator[tuple[str, dict[str, Any]]]:
        """Fetch LEI records from GLEIF.

        :param country: ISO 3166-1 alpha-2 country code to filter by, e.g. "KZ", "US"
        :param limit: stop after this many records (useful for smoke tests)
        """
        params: dict[str, Any] = {"page[size]": PAGE_SIZE, "page[number]": 1}
        if country:
            params["filter[entity.legalAddress.country]"] = country

        client = httpx.Client(
            base_url=GLEIF_API_BASE,
            headers={"User-Agent": settings.http_user_agent, "Accept": "application/vnd.api+json"},
            timeout=30.0,
        )

        count = 0
        try:
            while True:
                page = self._get_page(client, "/lei-records", params)
                records = page.get("data", [])
                if not records:
                    break

                for rec in records:
                    lei = rec.get("id")
                    if not lei:
                        continue
                    yield lei, rec
                    count += 1
                    if limit is not None and count >= limit:
                        return

                # GLEIF returns "next" link if more pages exist
                next_link = page.get("links", {}).get("next")
                if not next_link:
                    break
                params["page[number]"] += 1
        finally:
            client.close()

    @retry(
        stop=stop_after_attempt(5),
        wait=wait_exponential(multiplier=2, min=2, max=60),
        reraise=True,
    )
    def _get_page(
        self, client: httpx.Client, path: str, params: dict[str, Any]
    ) -> dict[str, Any]:
        resp = client.get(path, params=params)
        resp.raise_for_status()
        return resp.json()
