CREATE EXTENSION IF NOT EXISTS postgis;

-- scope is the filter a load used (for example "TOWN_ID=44"). source_rows
-- is the server's count for that filter, kept next to the rows loaded.
ALTER TABLE ingest_runs
    ADD COLUMN scope text NOT NULL DEFAULT '',
    ADD COLUMN source_rows bigint,
    ADD COLUMN error text;

-- Raw rows exactly as served: every attribute in attrs, geometry in WGS84.
CREATE TABLE raw_parcels (
    objectid bigint PRIMARY KEY,
    scope text NOT NULL,
    run_id bigint NOT NULL REFERENCES ingest_runs (id),
    attrs jsonb NOT NULL,
    geom geometry(Geometry, 4326)
);
CREATE INDEX raw_parcels_scope ON raw_parcels (scope);
CREATE INDEX raw_parcels_geom ON raw_parcels USING gist (geom);
