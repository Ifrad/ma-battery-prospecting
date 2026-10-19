-- Class of each (town, use code) pair, filled by prospect.sites from
-- config/use_codes.yaml.
CREATE TABLE use_code_classes (
    town_id integer NOT NULL,
    use_code text NOT NULL,
    use_class text,
    PRIMARY KEY (town_id, use_code)
);

-- One row per parcel polygon (LOC_ID). A polygon can carry several assessor
-- records (condo units, ground leases); see docs/DATA.md for the rule that
-- turns them into one row.
CREATE TABLE parcels (
    loc_id text PRIMARY KEY,
    town_id integer NOT NULL,
    records integer NOT NULL,
    prop_id text,
    owner text,
    site_addr text,
    use_code text,
    use_desc text,
    use_class text,
    bld_area integer,
    stories numeric,
    year_built integer,
    mixed_res_ci boolean NOT NULL,
    geom geometry(Geometry, 4326) NOT NULL
);
CREATE INDEX parcels_geom ON parcels USING gist (geom);

-- One row per MassGIS footprint, linked to the parcel its interior point
-- falls in. Area: the parcel's assessor area shared by footprint area,
-- else footprint area times stories, else footprint area alone.
CREATE TABLE buildings (
    building_id bigint PRIMARY KEY,
    struct_id text,
    town_id integer NOT NULL,
    loc_id text REFERENCES parcels (loc_id),
    footprint_sqft double precision NOT NULL,
    area_sqft double precision NOT NULL,
    area_source text NOT NULL
        CHECK (area_source IN ('assessor', 'footprint_x_stories', 'footprint_only')),
    geom geometry(Geometry, 4326) NOT NULL
);
CREATE INDEX buildings_loc_id ON buildings (loc_id);
CREATE INDEX buildings_geom ON buildings USING gist (geom);
