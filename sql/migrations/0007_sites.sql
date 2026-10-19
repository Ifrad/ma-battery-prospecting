ALTER TABLE parcels
    ADD COLUMN owner_norm text,
    ADD COLUMN owner_truncated boolean,
    ADD COLUMN site_id text;
CREATE INDEX parcels_site_id ON parcels (site_id);

-- One row per outreach site: the buildings on touching parcels with the
-- same normalized owner, within one town. site_id is the smallest LOC_ID
-- among the site's parcels. Owner and address come from the parcel with
-- the most building area.
CREATE TABLE sites (
    site_id text PRIMARY KEY,
    town_id integer NOT NULL,
    owner text,
    owner_norm text,
    site_addr text,
    parcels integer NOT NULL,
    buildings integer NOT NULL,
    area_sqft double precision NOT NULL,
    geom geometry(Point, 4326) NOT NULL
);
