-- The drawn site peak and whether each draw is billed on G-3, so the export
-- can recompute the ConnectedSolutions caps (event-window load and export
-- cap) in the report. Null on runs scored before this migration.
ALTER TABLE site_scores
    ADD COLUMN peak_kw real[],
    ADD COLUMN g3_draws boolean[];
