-- Utility by town, joined on TOWN_ID, no spatial join. ELEC names one
-- provider, or several separated by commas; ELEC_LABEL is "Municipal" for a
-- town served only by a municipal light plant. A building takes its
-- parcel's town, or its footprint's town when it has no parcel.
CREATE TEMP TABLE town_utility ON COMMIT DROP AS
SELECT
    (attrs ->> 'TOWN_ID')::integer AS town_id,
    attrs ->> 'ELEC' AS utility,
    CASE
        WHEN attrs ->> 'ELEC' LIKE '%,%' THEN 'unknown'
        WHEN attrs ->> 'ELEC_LABEL' = 'Municipal' THEN 'municipal'
        ELSE 'known'
    END AS utility_flag
FROM raw_utility_territories;

UPDATE buildings b
SET utility = t.utility, utility_flag = t.utility_flag
FROM buildings x
LEFT JOIN parcels p USING (loc_id)
JOIN town_utility t ON t.town_id = coalesce(p.town_id, x.town_id)
WHERE x.building_id = b.building_id;

UPDATE sites s
SET utility = t.utility, utility_flag = t.utility_flag
FROM town_utility t
WHERE t.town_id = s.town_id;
