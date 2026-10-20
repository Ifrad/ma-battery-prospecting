-- Owner mailing address and last sale of each parcel's primary record,
-- and the local owner and tenure signals built from them.
ALTER TABLE parcels
    ADD COLUMN site_zip text,
    ADD COLUMN own_addr text,
    ADD COLUMN own_city text,
    ADD COLUMN own_state text,
    ADD COLUMN own_zip text,
    ADD COLUMN ls_date text,
    ADD COLUMN ls_price integer,
    ADD COLUMN local_owner boolean,
    ADD COLUMN tenure_years numeric;

-- Sites take both signals from their main parcel (most building area).
ALTER TABLE sites
    ADD COLUMN main_loc_id text,
    ADD COLUMN local_owner boolean,
    ADD COLUMN tenure_years numeric;
