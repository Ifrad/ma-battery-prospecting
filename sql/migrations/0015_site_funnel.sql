-- Candidate sites through the prospecting funnel, rebuilt by make funnel.
-- No foreign key to sites: make sites truncates sites, so rerun make funnel
-- after it. Dropped sites stay, with the filter that dropped them.
CREATE TABLE site_funnel (
    site_id text PRIMARY KEY,
    region text,
    segment text NOT NULL,
    utility text,
    tier smallint NOT NULL CHECK (tier IN (1, 2)),
    measured_share double precision NOT NULL,
    annual_kwh double precision,
    kwh_per_month double precision,
    profile text,
    load_factor double precision,
    peak_kw double precision,
    dropped_by text CHECK (dropped_by IN ('utility', 'no_estimate', 'kwh', 'peak')),
    flags text[] NOT NULL DEFAULT '{}'
);
