-- One row per site with at least one building. Owner and address come from
-- the site's parcel with the most building area.
TRUNCATE sites;

INSERT INTO sites (
    site_id, town_id, owner, owner_norm, site_addr, parcels, buildings,
    area_sqft, geom, main_loc_id
)
WITH parcel_area AS (
    SELECT
        p.site_id,
        p.loc_id,
        p.town_id,
        p.owner,
        p.owner_norm,
        p.site_addr,
        coalesce(sum(b.area_sqft), 0) AS area_sqft,
        count(b.building_id) AS buildings
    FROM parcels p
    LEFT JOIN buildings b USING (loc_id)
    GROUP BY p.site_id, p.loc_id
),
main_parcel AS (
    SELECT DISTINCT ON (site_id) *
    FROM parcel_area
    ORDER BY site_id, area_sqft DESC, loc_id
),
totals AS (
    SELECT site_id, count(*) AS parcels, sum(buildings) AS buildings,
        sum(area_sqft) AS area_sqft
    FROM parcel_area
    GROUP BY site_id
    HAVING sum(buildings) > 0
),
centre AS (
    SELECT p.site_id, ST_Centroid(ST_Collect(b.geom)) AS geom
    FROM parcels p
    JOIN buildings b USING (loc_id)
    GROUP BY p.site_id
)
SELECT
    t.site_id,
    m.town_id,
    m.owner,
    m.owner_norm,
    m.site_addr,
    t.parcels,
    t.buildings,
    t.area_sqft,
    c.geom,
    m.loc_id
FROM totals t
JOIN main_parcel m USING (site_id)
JOIN centre c USING (site_id);
