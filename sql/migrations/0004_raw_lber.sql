-- DOER LBER buildings, one release at a time (the one in config/lber.yaml).
-- grid_kwh is grid electricity in kWh, or NULL when the release reports zero
-- or a negative value: those mean "no usable data", never "no use".
-- 1 kWh = 3.41214 kBtu.
CREATE TABLE raw_lber (
    objectid bigint PRIMARY KEY,
    scope text NOT NULL,
    run_id bigint NOT NULL REFERENCES ingest_runs (id),
    attrs jsonb NOT NULL,
    geom geometry(Geometry, 4326),
    reporting_year integer NOT NULL,
    grid_kwh double precision GENERATED ALWAYS AS (
        CASE
            WHEN (attrs ->> 'Total_Electricity_Use_Purchased_From_Grid__kBtu_')::float8 > 0
            THEN (attrs ->> 'Total_Electricity_Use_Purchased_From_Grid__kBtu_')::float8
                / 3.41214
        END
    ) STORED
);
CREATE INDEX raw_lber_geom ON raw_lber USING gist (geom);
