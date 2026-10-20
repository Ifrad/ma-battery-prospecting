-- Value per battery block per site and scenario, from make score. Values
-- are simulated gross yearly revenue per block before any host share, not
-- profit, and unvalidated. Each make score adds a run; the latest run is
-- current. No foreign key to sites: make sites truncates sites, so rerun
-- make funnel and make score after it (make db-check reports stale rows).
CREATE TABLE score_runs (
    run_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    config_hash text NOT NULL,
    draws integer NOT NULL,
    scored_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE site_scores (
    run_id bigint NOT NULL REFERENCES score_runs (run_id) ON DELETE CASCADE,
    site_id text NOT NULL,
    scenario text NOT NULL
        CHECK (scenario IN ('demand_savings', 'with_connected_solutions')),
    region text,
    segment text NOT NULL,
    utility text NOT NULL,
    tier smallint NOT NULL CHECK (tier IN (1, 2)),
    passes_200kw boolean NOT NULL,
    least_certain boolean NOT NULL,
    flags text[] NOT NULL DEFAULT '{}',
    blocks double precision NOT NULL,
    value_p10 double precision NOT NULL,
    value_p50 double precision NOT NULL,
    value_p90 double precision NOT NULL,
    total_p10 double precision NOT NULL,
    total_p50 double precision NOT NULL,
    total_p90 double precision NOT NULL,
    break_even_p50 double precision NOT NULL,
    break_even_p10 double precision NOT NULL,
    break_even_p50_itc double precision NOT NULL,
    break_even_p10_itc double precision NOT NULL,
    itc_applies boolean NOT NULL,
    demand_p50 double precision NOT NULL,
    grid_p50 double precision NOT NULL,
    demand_share double precision NOT NULL,
    grid_share double precision NOT NULL,
    top_drivers text[] NOT NULL DEFAULT '{}',
    -- Draws in physical units, per block per year, one element per draw.
    kwm_g2 real[] NOT NULL,
    kwm_g3 real[] NOT NULL,
    blocks_draws smallint[] NOT NULL,
    grid_kw real NOT NULL,
    PRIMARY KEY (run_id, site_id, scenario)
);
