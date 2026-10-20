-- Building area, pooled per site (docs/DATA.md, "Site table rules").
--
-- For each site: assessor = the sum of BLD_AREA over its parcels that have
-- it (each parcel's BLD_AREA already follows the multi-record rule), and
-- footprint = the sum of footprint area on those same parcels.
--   assessor: assessor area shared over those footprints in proportion to
--     footprint area, so the site's assessor total does not change.
--   assessor_below_footprint: assessor < footprint x floor_tolerance.
--   assessor_above_footprint: assessor > footprint x ceiling_stories_factor
--     x the site's highest recorded stories (or x ceiling_without_stories).
--   On a flagged site, those buildings use footprint x stories, or the
--   footprint alone, but keep the flag as their area_source.
-- Buildings on parcels with no BLD_AREA, or on no parcel, use
-- footprint_x_stories or footprint_only as before. Parameters come from
-- config/sites.yaml (area_checks).
WITH site_assessor AS (
    SELECT site_id, sum(bld_area) AS assessor, max(stories) AS stories
    FROM parcels
    WHERE bld_area > 0
    GROUP BY site_id
),
site_footprint AS (
    SELECT p.site_id, sum(b.footprint_sqft) AS footprint
    FROM buildings b
    JOIN parcels p USING (loc_id)
    WHERE p.bld_area > 0
    GROUP BY p.site_id
),
verdict AS (
    SELECT
        a.site_id,
        a.assessor,
        f.footprint,
        CASE
            WHEN a.assessor < f.footprint * %(floor_tolerance)s
                THEN 'assessor_below_footprint'
            WHEN a.assessor > f.footprint * coalesce(
                    a.stories * %(ceiling_stories_factor)s,
                    %(ceiling_without_stories)s)
                THEN 'assessor_above_footprint'
            ELSE 'assessor'
        END AS source
    FROM site_assessor a
    JOIN site_footprint f USING (site_id)
),
area AS (
    SELECT
        b.building_id,
        CASE
            WHEN p.bld_area > 0 AND v.source = 'assessor'
                THEN v.assessor * b.footprint_sqft / v.footprint
            WHEN p.stories IS NOT NULL THEN b.footprint_sqft * p.stories
            ELSE b.footprint_sqft
        END AS area_sqft,
        CASE
            WHEN p.bld_area > 0 THEN v.source
            WHEN p.stories IS NOT NULL THEN 'footprint_x_stories'
            ELSE 'footprint_only'
        END AS area_source
    FROM buildings b
    LEFT JOIN parcels p USING (loc_id)
    LEFT JOIN verdict v ON v.site_id = p.site_id
)
UPDATE buildings b
SET area_sqft = a.area_sqft, area_source = a.area_source
FROM area a
WHERE a.building_id = b.building_id;
