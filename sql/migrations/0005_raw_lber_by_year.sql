-- Keep LBER releases side by side: each October 31 release reuses object
-- ids, so the reporting year is part of the key.
ALTER TABLE raw_lber DROP CONSTRAINT raw_lber_pkey;
ALTER TABLE raw_lber ADD PRIMARY KEY (reporting_year, objectid);
