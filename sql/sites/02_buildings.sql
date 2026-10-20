-- One row per footprint. Its parcel is the smallest parcel containing the
-- footprint's interior point. Area is set later, per site, by 03_area.sql;
-- until then it is the footprint area. A footprint with exactly the same
-- shape as one with a lower object id is a duplicate in the source and is
-- left out, so its area is not counted twice.
INSERT INTO buildings (
    building_id, struct_id, footprint_town_id, loc_id, footprint_sqft,
    area_sqft, area_source, geom
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
        AND NOT EXISTS (
            SELECT 1 FROM raw_footprints g
            WHERE g.objectid < f.objectid
                AND g.geom && f.geom
                AND ST_Equals(g.geom, f.geom)
        )
)
SELECT
    objectid, struct_id, town_id, loc_id, footprint_sqft, footprint_sqft,
    'footprint_only', geom
FROM f;
