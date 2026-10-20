-- Pilot towns from config/regions.yaml, filled by prospect.sites.build.
CREATE TABLE pilot_towns (
    town_id integer PRIMARY KEY,
    region text NOT NULL
);

-- One row per matched LBER building and reporting year. An LBER row is in
-- the pilot when its point lies inside a pilot town's polygon.
CREATE TABLE lber_matches (
    reporting_year integer NOT NULL,
    objectid bigint NOT NULL,
    town_id integer NOT NULL,
    region text NOT NULL,
    building_id bigint NOT NULL REFERENCES buildings (building_id),
    method text NOT NULL
        CHECK (method IN ('ubid', 'point_in_footprint', 'point_in_parcel', 'address')),
    confidence text NOT NULL,
    candidates integer NOT NULL,
    grid_kwh double precision,
    PRIMARY KEY (reporting_year, objectid)
);
CREATE INDEX lber_matches_building ON lber_matches (building_id);

-- Pilot LBER rows that no method matched.
CREATE TABLE lber_unmatched (
    reporting_year integer NOT NULL,
    objectid bigint NOT NULL,
    town_id integer NOT NULL,
    region text NOT NULL,
    street_address text,
    city text,
    reason text NOT NULL,
    PRIMARY KEY (reporting_year, objectid)
);

-- Measured only through a matched LBER row with grid electricity, from the
-- latest reporting year that has one for the building.
ALTER TABLE buildings
    ADD COLUMN electricity_source text NOT NULL DEFAULT 'estimated'
        CHECK (electricity_source IN ('measured', 'estimated')),
    ADD COLUMN grid_kwh double precision,
    ADD COLUMN grid_kwh_year integer,
    ADD COLUMN lber_rows integer NOT NULL DEFAULT 0;
