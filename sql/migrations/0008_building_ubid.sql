-- UBID of each building's footprint (code length 11, as in LBER), filled by
-- prospect.sites.build. Not unique: two footprints can share a UBID.
ALTER TABLE buildings ADD COLUMN ubid text;
CREATE INDEX buildings_ubid ON buildings (ubid);
