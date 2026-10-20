-- Segment of candidate parcels, buildings and sites; NULL elsewhere.
-- segment_source: use_code, owner_keyword or default.
ALTER TABLE parcels
    ADD COLUMN segment text,
    ADD COLUMN segment_source text;
ALTER TABLE buildings
    ADD COLUMN segment text,
    ADD COLUMN segment_source text;
ALTER TABLE sites
    ADD COLUMN segment text,
    ADD COLUMN segment_source text;
