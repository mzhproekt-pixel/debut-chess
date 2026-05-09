"""UN Comtrade — bilateral trade statistics.

Free preview tier: 500 calls/day, 100k records/query.
Docs: https://comtradeapi.un.org/
Subscribe at https://comtradedeveloper.un.org for higher limits (still free).

Unlike the entity-based connectors this one writes directly to ``trade_flows``
because the data is country×HS×year aggregates — there is no per-company entity.
"""

from typing import Any

import httpx
from sqlalchemy import text
from tenacity import retry, stop_after_attempt, wait_exponential

from src.db import get_connection
from src.logging_config import get_logger
from src.settings import settings

log = get_logger(__name__)

API_BASE = "https://comtradeapi.un.org/data/v1"

# Comtrade reports trade with M49 codes; we map a small subset commonly needed.
# Full mapping is available at https://comtradeapi.un.org/files/v1/app/reference/Reporters.json
M49_TO_ISO2 = {
    "840": "US", "826": "GB", "276": "DE", "156": "CN", "643": "RU",
    "398": "KZ", "112": "BY", "860": "UZ", "417": "KG", "795": "TM",
    "392": "JP", "410": "KR", "356": "IN", "076": "BR", "036": "AU",
    "124": "CA", "484": "MX", "250": "FR", "380": "IT", "724": "ES",
    "528": "NL", "616": "PL", "203": "CZ", "208": "DK", "752": "SE",
    "578": "NO", "246": "FI", "792": "TR", "364": "IR", "682": "SA",
    "784": "AE", "818": "EG", "710": "ZA", "566": "NG", "404": "KE",
    "0": None,  # World aggregate
}


class UNComtradeConnector:
    """Standalone — does not extend BaseConnector because it writes to
    ``trade_flows`` instead of ``entity_sources``.
    """

    source_name = "un_comtrade"

    def fetch_and_store(
        self,
        years: list[int],
        reporter: str = "all",
        hs_codes: list[str] | None = None,
        flow: str = "M",  # M=imports, X=exports
    ) -> int:
        """Fetch trade flows for the given years and store in ``trade_flows``.

        :param years: list of years, e.g. [2022, 2023, 2024]
        :param reporter: M49 code or "all" to fetch all reporting countries
        :param hs_codes: list of HS codes (e.g. ["8501", "2710"]) or None for total
        :param flow: "M" for imports, "X" for exports, "all" for both
        """
        if "your-email" in settings.http_user_agent:
            log.warning("comtrade.user_agent_default",
                        msg="Update HTTP_USER_AGENT in .env for politeness")

        client = httpx.Client(
            headers={"User-Agent": settings.http_user_agent},
            timeout=60.0,
        )
        try:
            count = 0
            for year in years:
                params = {
                    "reporterCode": reporter,
                    "period": str(year),
                    "flowCode": flow,
                    "cmdCode": ",".join(hs_codes) if hs_codes else "TOTAL",
                    "partnerCode": "0",   # 0 = World
                    "freqCode": "A",      # Annual
                    "clCode": "HS",
                    "format": "JSON",
                }
                if settings.comtrade_primary_key:
                    params["subscription-key"] = settings.comtrade_primary_key

                data = self._get(client, f"{API_BASE}/get/C/A/HS", params)
                rows = data.get("data") or []
                if not rows:
                    log.info("comtrade.empty", year=year, reporter=reporter)
                    continue

                count += self._store(rows)
                log.info("comtrade.year_done", year=year, rows=len(rows))

            return count
        finally:
            client.close()

    @retry(
        stop=stop_after_attempt(5),
        wait=wait_exponential(multiplier=2, min=5, max=120),
        reraise=True,
    )
    def _get(self, client: httpx.Client, url: str, params: dict) -> dict:
        resp = client.get(url, params=params)
        resp.raise_for_status()
        return resp.json()

    def _store(self, rows: list[dict[str, Any]]) -> int:
        with get_connection() as conn:
            inserted = 0
            for r in rows:
                reporter_iso = M49_TO_ISO2.get(str(r.get("reporterCode")))
                partner_iso = M49_TO_ISO2.get(str(r.get("partnerCode")))
                if not reporter_iso:
                    continue

                flow_code = r.get("flowCode")
                flow_name = {"M": "import", "X": "export",
                             "RM": "re-import", "RX": "re-export"}.get(flow_code)
                if not flow_name:
                    continue

                conn.execute(
                    text(
                        """
                        INSERT INTO trade_flows
                            (reporter_iso2, partner_iso2, flow, hs_code, year,
                             trade_value_usd, net_weight_kg)
                        VALUES (:r, :p, :flow, :hs, :y, :v, :w)
                        ON CONFLICT (reporter_iso2, partner_iso2, flow, hs_code, year)
                        DO UPDATE SET
                            trade_value_usd = EXCLUDED.trade_value_usd,
                            net_weight_kg = EXCLUDED.net_weight_kg
                        """
                    ),
                    {
                        "r": reporter_iso,
                        "p": partner_iso,
                        "flow": flow_name,
                        "hs": str(r.get("cmdCode") or "TOTAL"),
                        "y": int(r.get("period") or 0),
                        "v": r.get("primaryValue"),
                        "w": r.get("netWgt"),
                    },
                )
                inserted += 1
            return inserted
