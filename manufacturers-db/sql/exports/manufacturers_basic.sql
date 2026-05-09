-- Basic export: one row per entity with primary identifier and address.
SELECT
    e.id                AS entity_id,
    e.lei,
    e.name,
    e.country_iso2,
    e.status,
    e.legal_form,
    e.founded_date,
    e.website,
    a.city,
    a.region,
    a.postal_code,
    a.street,
    (SELECT string_agg(scheme || ':' || value, '; ')
       FROM entity_identifiers ei WHERE ei.entity_id = e.id) AS identifiers,
    e.updated_at
FROM entities e
LEFT JOIN LATERAL (
    SELECT * FROM entity_addresses ea
     WHERE ea.entity_id = e.id
     ORDER BY (ea.address_type = 'registered') DESC, ea.id
     LIMIT 1
) a ON TRUE;
