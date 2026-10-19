-- One row per footprint. Its parcel is the smallest parcel containing the
-- footprint's interior point. Area, in order:
--   assessor: the parcel's BLD_AREA, shared among the parcel's footprints
--     in proportion to footprint area
--   footprint_x_stories: footprint area times the parcel's stories
--   footprint_only: footprint area alone
INSERT INTO buildings (
    building_id, struct_id, town_id, loc_id, footprint_sqft, area_sqft,
    area_source, geom
)
WITH f AS (
    SELECT
        f.objectid,
        f.attrs ->> 'STRUCT_ID' AS struct_id,
        (f.attrs ->> 'TOWN_ID')::integer AS town_id,
        coalesce(
            (f.attrs ->> 'AREA_SQ_FT')::double precision,
            ST_Area(f.geom::geography) * 10.7639
        ) AS footprint_sqft,
        f.geom,
        (
            SELECT p.loc_id
            FROM parcels p
            WHERE ST_Contains(p.geom, ST_PointOnSurface(f.geom))
            ORDER BY ST_Area(p.geom), p.loc_id
            LIMIT 1
        ) AS loc_id
    FROM raw_footprints f
    WHERE f.geom IS NOT NULL
),
shared AS (
    SELECT f.*, sum(footprint_sqft) OVER (PARTITION BY loc_id) AS parcel_footprint
    FROM f
)
SELECT
    s.objectid,
    s.struct_id,
    s.town_id,
    s.loc_id,
    s.footprint_sqft,
    CASE
        WHEN p.bld_area IS NOT NULL THEN p.bld_area * s.footprint_sqft / s.parcel_footprint
        WHEN p.stories IS NOT NULL THEN s.footprint_sqft * p.stories
        ELSE s.footprint_sqft
    END,
    CASE
        WHEN p.bld_area IS NOT NULL THEN 'assessor'
        WHEN p.stories IS NOT NULL THEN 'footprint_x_stories'
        ELSE 'footprint_only'
    END,
    s.geom
FROM shared s
LEFT JOIN parcels p USING (loc_id);
