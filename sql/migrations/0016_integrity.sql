-- Integrity fixes from the Phase 2 schema review (PLAN.md, Phase 2
-- follow-up). Data is rebuilt by make sites after this migration.

-- 1. Near-duplicate footprints are flagged, not dropped. Exact duplicates
--    are dropped when buildings are built (sql/sites/02_buildings.sql).
ALTER TABLE buildings ADD COLUMN near_duplicate_of bigint;

-- 3. The footprint's own town disagrees with its parcel's town at town
--    lines; the parcel's town is the one to use, so the name says which.
ALTER TABLE buildings RENAME COLUMN town_id TO footprint_town_id;

-- 4. Allowed values. Segments match config/segments.yaml; a new segment
--    needs a migration.
ALTER TABLE parcels
    ADD CONSTRAINT parcels_segment_check CHECK (segment IN (
        'cold_storage', 'food_production', 'laundry', 'hospital',
        'other_healthcare', 'manufacturing', 'warehouse', 'generic')),
    ADD CONSTRAINT parcels_segment_source_check
        CHECK (segment_source IN ('use_code', 'owner_keyword', 'default'));
ALTER TABLE buildings
    ADD CONSTRAINT buildings_segment_check CHECK (segment IN (
        'cold_storage', 'food_production', 'laundry', 'hospital',
        'other_healthcare', 'manufacturing', 'warehouse', 'generic')),
    ADD CONSTRAINT buildings_segment_source_check
        CHECK (segment_source IN ('use_code', 'owner_keyword', 'default'));
ALTER TABLE sites
    ADD CONSTRAINT sites_segment_check CHECK (segment IN (
        'cold_storage', 'food_production', 'laundry', 'hospital',
        'other_healthcare', 'manufacturing', 'warehouse', 'generic')),
    ADD CONSTRAINT sites_segment_source_check
        CHECK (segment_source IN ('use_code', 'owner_keyword', 'default'));
ALTER TABLE site_funnel
    ADD CONSTRAINT site_funnel_segment_check CHECK (segment IN (
        'cold_storage', 'food_production', 'laundry', 'hospital',
        'other_healthcare', 'manufacturing', 'warehouse', 'generic'));
ALTER TABLE lber_matches
    ADD CONSTRAINT lber_matches_confidence_check CHECK (
        confidence IN ('high', 'medium', 'low')
        OR confidence ~ '^ambiguous, [0-9]+ buildings$');

-- 2. Foreign keys. parcels.site_id and sites.main_loc_id point at each
--    other and are filled in order inside the make sites transaction, so
--    they are checked at commit. Parcels in a group with no building have
--    no site and keep site_id null. LBER matches are derived from raw_lber
--    and go with it when a re-ingest removes a row.
UPDATE parcels p SET site_id = NULL
WHERE site_id IS NOT NULL
    AND NOT EXISTS (SELECT 1 FROM sites s WHERE s.site_id = p.site_id);
ALTER TABLE parcels
    ADD CONSTRAINT parcels_site_id_fkey FOREIGN KEY (site_id)
        REFERENCES sites (site_id) DEFERRABLE INITIALLY DEFERRED;
ALTER TABLE sites
    ADD CONSTRAINT sites_main_loc_id_fkey FOREIGN KEY (main_loc_id)
        REFERENCES parcels (loc_id) DEFERRABLE INITIALLY DEFERRED;
ALTER TABLE lber_matches
    ADD CONSTRAINT lber_matches_raw_lber_fkey FOREIGN KEY (reporting_year, objectid)
        REFERENCES raw_lber (reporting_year, objectid) ON DELETE CASCADE;
ALTER TABLE lber_unmatched
    ADD CONSTRAINT lber_unmatched_raw_lber_fkey FOREIGN KEY (reporting_year, objectid)
        REFERENCES raw_lber (reporting_year, objectid) ON DELETE CASCADE;

-- The evidence view gains the near-duplicate flag, as its last column.
CREATE OR REPLACE VIEW building_evidence AS
SELECT
    b.building_id,
    p.site_id,
    b.loc_id,
    coalesce(p.town_id, b.footprint_town_id) AS town_id,
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
    p.tenure_years,
    b.near_duplicate_of
FROM buildings b
LEFT JOIN parcels p USING (loc_id)
LEFT JOIN pilot_towns pt ON pt.town_id = coalesce(p.town_id, b.footprint_town_id)
LEFT JOIN LATERAL (
    -- The match behind the building's kWh, else its latest match.
    SELECT method, confidence
    FROM lber_matches lm
    WHERE lm.building_id = b.building_id
    ORDER BY (lm.reporting_year = b.grid_kwh_year) DESC NULLS LAST,
        lm.reporting_year DESC, lm.objectid
    LIMIT 1
) m ON true;
