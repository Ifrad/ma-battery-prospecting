-- Cost and profit are no longer modeled (PLAN.md, Phase 6). The break-even
-- columns were functions of value_p50 and value_p10, which stay, and of
-- config/costs.yaml, which is in git history.
ALTER TABLE site_scores
    DROP COLUMN break_even_p50,
    DROP COLUMN break_even_p10,
    DROP COLUMN break_even_p50_itc,
    DROP COLUMN break_even_p10_itc,
    DROP COLUMN itc_applies;
