-- One row per parcel polygon. Rule for polygons with several assessor
-- records (docs/DATA.md, "Site table rules"):
--   primary record: largest BLD_AREA, then a record with a use class, then
--     the lowest object id. Owner, address, use code, stories and year
--     built come from it.
--   bld_area: the sum of the records' BLD_AREA (units and ground leases add
--     up), unless every nonzero value is the same, then that value once.
--     RES_AREA is never used.
--   mixed_res_ci: some record is residential (1xx) and some record has a
--     commercial, industrial or hospital class.
TRUNCATE buildings, parcels;

INSERT INTO parcels (
    loc_id, town_id, records, prop_id, owner, site_addr, use_code, use_desc,
    use_class, bld_area, stories, year_built, mixed_res_ci, geom
)
WITH r AS (
    SELECT
        p.objectid,
        p.attrs ->> 'LOC_ID' AS loc_id,
        (p.attrs ->> 'TOWN_ID')::integer AS town_id,
        p.attrs,
        p.geom,
        coalesce((p.attrs ->> 'BLD_AREA')::integer, 0) AS bld_area,
        c.use_class,
        coalesce(p.attrs ->> 'USE_CODE' ~ '^1[0-9]{2}', false) AS residential
    FROM raw_parcels p
    LEFT JOIN use_code_classes c
        ON c.town_id = (p.attrs ->> 'TOWN_ID')::integer
        AND c.use_code = p.attrs ->> 'USE_CODE'
    WHERE p.attrs ->> 'LOC_ID' IS NOT NULL AND p.geom IS NOT NULL
),
grouped AS (
    SELECT
        loc_id,
        count(*) AS records,
        CASE
            WHEN count(DISTINCT bld_area) FILTER (WHERE bld_area > 0) = 1
            THEN max(bld_area)
            ELSE sum(bld_area)
        END AS bld_area,
        bool_or(residential) AND bool_or(use_class IN (
            'commercial_industrial', 'hospital', 'hospital_boston',
            'mixed_commercial_industrial'
        )) AS mixed_res_ci
    FROM r
    GROUP BY loc_id
),
primary_record AS (
    SELECT DISTINCT ON (loc_id) *
    FROM r
    ORDER BY loc_id, bld_area DESC, (use_class IS NULL), objectid
)
SELECT
    pr.loc_id,
    pr.town_id,
    g.records,
    pr.attrs ->> 'PROP_ID',
    pr.attrs ->> 'OWNER1',
    pr.attrs ->> 'SITE_ADDR',
    pr.attrs ->> 'USE_CODE',
    pr.attrs ->> 'USE_DESC',
    pr.use_class,
    nullif(g.bld_area, 0),
    nullif((regexp_match(pr.attrs ->> 'STORIES', '^\s*([0-9]+(\.[0-9]+)?)'))[1]::numeric, 0),
    nullif((pr.attrs ->> 'YEAR_BUILT')::integer, 0),
    coalesce(g.mixed_res_ci, false),
    pr.geom
FROM primary_record pr
JOIN grouped g USING (loc_id);
