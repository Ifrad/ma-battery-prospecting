-- Two new area sources: a site's pooled assessor area below or above what
-- its footprints allow (config/sites.yaml, area_checks).
ALTER TABLE buildings DROP CONSTRAINT buildings_area_source_check;
ALTER TABLE buildings ADD CONSTRAINT buildings_area_source_check
    CHECK (area_source IN (
        'assessor', 'footprint_x_stories', 'footprint_only',
        'assessor_below_footprint', 'assessor_above_footprint'
    ));

-- site_evidence gains the share of area from each new source.
DROP VIEW site_evidence;
CREATE VIEW site_evidence AS
SELECT
    s.site_id,
    s.town_id,
    pt.region,
    s.owner,
    s.site_addr,
    s.segment IS NOT NULL AS candidate,
    s.segment,
    s.segment_source,
    s.parcels,
    s.buildings,
    count(*) FILTER (WHERE e.candidate) AS candidate_buildings,
    count(*) FILTER (WHERE e.electricity_source = 'measured') AS measured_buildings,
    sum(e.grid_kwh) AS measured_kwh,
    count(*) FILTER (WHERE e.lber_method IS NOT NULL) AS lber_matched_buildings,
    count(*) FILTER (WHERE e.lber_confidence LIKE 'ambiguous%') AS ambiguous_matches,
    s.area_sqft,
    sum(e.area_sqft) FILTER (WHERE e.area_source = 'assessor') / nullif(s.area_sqft, 0)
        AS area_share_assessor,
    sum(e.area_sqft) FILTER (WHERE e.area_source = 'footprint_x_stories')
        / nullif(s.area_sqft, 0) AS area_share_footprint_x_stories,
    sum(e.area_sqft) FILTER (WHERE e.area_source = 'footprint_only')
        / nullif(s.area_sqft, 0) AS area_share_footprint_only,
    s.utility,
    s.utility_flag,
    s.local_owner,
    bool_or(e.mixed_res_ci) AS mixed_res_ci,
    s.tenure_years,
    sum(e.area_sqft) FILTER (WHERE e.area_source = 'assessor_below_footprint')
        / nullif(s.area_sqft, 0) AS area_share_assessor_below_footprint,
    sum(e.area_sqft) FILTER (WHERE e.area_source = 'assessor_above_footprint')
        / nullif(s.area_sqft, 0) AS area_share_assessor_above_footprint
FROM sites s
JOIN building_evidence e USING (site_id)
LEFT JOIN pilot_towns pt ON pt.town_id = s.town_id
GROUP BY s.site_id, pt.region;
