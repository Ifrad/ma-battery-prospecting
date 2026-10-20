-- Grid program kW per block now varies by draw (the export cap depends on
-- the drawn site peak), so it is stored per draw like the other units.
ALTER TABLE site_scores
    ALTER COLUMN grid_kw TYPE real[] USING ARRAY[grid_kw];
