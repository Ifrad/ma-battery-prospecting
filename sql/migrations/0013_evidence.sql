-- Every Phase 2 evidence flag in one place, per building and per site.
-- Views, so they always reflect the latest make sites.

CREATE VIEW building_evidence AS
SELECT
    b.building_id,
    p.site_id,
    b.loc_id,
    coalesce(p.town_id, b.town_id) AS town_id,
    pt.region,
    b.segment IS NOT NULL AS candidate,
    b.segment,
    b.segment_source,
    b.electricity_source,
    b.grid_kwh,
    b.grid_kwh_year,
    m.method AS lber_method,
    m.confidence AS lber_confidence,
    b.area_source,
    b.area_sqft,
    b.footprint_sqft,
    b.utility,
    b.utility_flag,
    p.local_owner,
    coalesce(p.mixed_res_ci, false) AS mixed_res_ci,
    p.tenure_years
FROM buildings b
LEFT JOIN parcels p USING (loc_id)
LEFT JOIN pilot_towns pt ON pt.town_id = coalesce(p.town_id, b.town_id)
LEFT JOIN LATERAL (
    -- The match behind the building's kWh, else its latest match.
    SELECT method, confidence
    FROM lber_matches lm
    WHERE lm.building_id = b.building_id
    ORDER BY (lm.reporting_year = b.grid_kwh_year) DESC NULLS LAST,
        lm.reporting_year DESC, lm.objectid
    LIMIT 1
) m ON true;

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
    s.tenure_years
FROM sites s
JOIN building_evidence e USING (site_id)
LEFT JOIN pilot_towns pt ON pt.town_id = s.town_id
GROUP BY s.site_id, pt.region;
