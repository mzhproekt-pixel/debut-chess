-- Trade flows aggregated by HS code, year, and direction.
SELECT
    reporter_iso2,
    partner_iso2,
    flow,
    hs_code,
    year,
    trade_value_usd,
    net_weight_kg
FROM trade_flows
ORDER BY year DESC, trade_value_usd DESC NULLS LAST;
