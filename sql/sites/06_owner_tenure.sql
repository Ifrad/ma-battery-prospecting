-- Sites take local owner and tenure from their main parcel.
UPDATE sites s
SET local_owner = p.local_owner, tenure_years = p.tenure_years
FROM parcels p
WHERE p.loc_id = s.main_loc_id;
