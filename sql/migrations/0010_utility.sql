-- Electric utility by town (raw_utility_territories, joined on TOWN_ID).
-- utility_flag: known (one investor-owned utility), municipal (a municipal
-- light plant only) or unknown (the town lists several providers).
ALTER TABLE buildings
    ADD COLUMN utility text,
    ADD COLUMN utility_flag text
        CHECK (utility_flag IN ('known', 'municipal', 'unknown'));
ALTER TABLE sites
    ADD COLUMN utility text,
    ADD COLUMN utility_flag text
        CHECK (utility_flag IN ('known', 'municipal', 'unknown'));
