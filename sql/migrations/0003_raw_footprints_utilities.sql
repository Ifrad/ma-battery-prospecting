-- Same shape as raw_parcels: every attribute in attrs, geometry in WGS84.
CREATE TABLE raw_footprints (
    objectid bigint PRIMARY KEY,
    scope text NOT NULL,
    run_id bigint NOT NULL REFERENCES ingest_runs (id),
    attrs jsonb NOT NULL,
    geom geometry(Geometry, 4326)
);
CREATE INDEX raw_footprints_scope ON raw_footprints (scope);
CREATE INDEX raw_footprints_geom ON raw_footprints USING gist (geom);

-- One row per town. Joined to parcels on TOWN_ID, not spatially.
CREATE TABLE raw_utility_territories (
    objectid bigint PRIMARY KEY,
    scope text NOT NULL,
    run_id bigint NOT NULL REFERENCES ingest_runs (id),
    attrs jsonb NOT NULL,
    geom geometry(Geometry, 4326)
);
