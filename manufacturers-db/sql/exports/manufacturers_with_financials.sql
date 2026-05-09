-- Entities with at least one financial metric — pivoted by year.
SELECT
    e.id        AS entity_id,
    e.lei,
    e.name,
    e.country_iso2,
    f.fiscal_year,
    MAX(CASE WHEN f.metric = 'revenue'    THEN f.value_numeric END) AS revenue,
    MAX(CASE WHEN f.metric = 'net_income' THEN f.value_numeric END) AS net_income,
    MAX(CASE WHEN f.metric = 'employees'  THEN f.value_numeric END) AS employees,
    MAX(f.currency)                                                  AS currency
FROM entities e
JOIN entity_financials f ON f.entity_id = e.id
GROUP BY e.id, e.lei, e.name, e.country_iso2, f.fiscal_year;
