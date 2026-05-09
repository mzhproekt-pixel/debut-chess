-- Entities with at least one contact (phone/email/fax).
SELECT
    e.id                AS entity_id,
    e.lei,
    e.name,
    e.country_iso2,
    e.website,
    (SELECT string_agg(value, '; ') FROM entity_contacts c
       WHERE c.entity_id = e.id AND c.contact_type = 'phone') AS phones,
    (SELECT string_agg(value, '; ') FROM entity_contacts c
       WHERE c.entity_id = e.id AND c.contact_type = 'email') AS emails,
    (SELECT string_agg(value, '; ') FROM entity_contacts c
       WHERE c.entity_id = e.id AND c.contact_type = 'fax')   AS faxes
FROM entities e
WHERE EXISTS (SELECT 1 FROM entity_contacts c WHERE c.entity_id = e.id);
