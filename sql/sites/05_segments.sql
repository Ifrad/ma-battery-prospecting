-- Buildings take their parcel's segment. A site takes the segment of its
-- candidate building with the most area (ties: lowest building id).
UPDATE buildings b
SET segment = p.segment, segment_source = p.segment_source
FROM parcels p
WHERE p.loc_id = b.loc_id AND p.segment IS NOT NULL;

UPDATE sites s
SET segment = m.segment, segment_source = m.segment_source
FROM (
    SELECT DISTINCT ON (p.site_id) p.site_id, b.segment, b.segment_source
    FROM buildings b
    JOIN parcels p USING (loc_id)
    WHERE b.segment IS NOT NULL
    ORDER BY p.site_id, b.area_sqft DESC, b.building_id
) m
WHERE m.site_id = s.site_id;
