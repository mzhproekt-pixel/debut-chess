"""SEC EDGAR — US public company filings.

Free, public. Requires a descriptive User-Agent (SEC enforces this).
Docs: https://www.sec.gov/edgar/sec-api-documentation

Strategy:
  1. Download the bulk CIK→ticker map (~30k filers).
  2. For each CIK, fetch the company submissions JSON which contains
     name, addresses, SIC code, and the recent filings list.
"""

from collections.abc import Iterator
from typing import Any

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from src.connectors.base import BaseConnector
from src.logging_config import get_logger
from src.settings import settings

log = get_logger(__name__)

CIK_LOOKUP_URL = "https://www.sec.gov/files/company_tickers.json"
SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik:010d}.json"


class SECEdgarConnector(BaseConnector):
    source_name = "sec_edgar"

    def fetch(
        self,
        limit: int | None = None,
        **_: Any,
    ) -> Iterator[tuple[str, dict[str, Any]]]:
        if "your-email" in settings.http_user_agent:
            raise RuntimeError(
                "SEC EDGAR requires a real contact email in HTTP_USER_AGENT. "
                "Edit your .env file."
            )

        client = httpx.Client(
            headers={"User-Agent": settings.http_user_agent},
            timeout=30.0,
        )

        try:
            tickers = self._get_json(client, CIK_LOOKUP_URL)
            ciks = sorted({int(v["cik_str"]) for v in tickers.values()})
            log.info("sec.ciks_loaded", count=len(ciks))

            for i, cik in enumerate(ciks):
                if limit is not None and i >= limit:
                    return
                try:
                    sub = self._get_json(client, SUBMISSIONS_URL.format(cik=cik))
                except httpx.HTTPStatusError as exc:
                    if exc.response.status_code == 404:
                        continue
                    raise
                yield str(cik), sub
        finally:
            client.close()

    @retry(
        stop=stop_after_attempt(5),
        wait=wait_exponential(multiplier=2, min=2, max=60),
        reraise=True,
    )
    def _get_json(self, client: httpx.Client, url: str) -> dict[str, Any]:
        resp = client.get(url)
        resp.raise_for_status()
        return resp.json()
