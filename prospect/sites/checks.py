"""Check that derived tables agree with their sources.

Usage: python -m prospect.sites.checks   (make db-check)

Reads the database only. Every check must count zero; the command exits 1
otherwise. Run it after make sites and make funnel. Foreign keys and check
constraints cover orphans and allowed values; these checks cover copied
columns that could drift.
"""

import sys

from prospect.db import connect

MUST_BE_ZERO = {
    "buildings with exactly the shape of another": """
        SELECT count(*) FROM buildings a JOIN buildings b
            ON a.building_id < b.building_id AND a.geom && b.geom
            AND ST_Equals(a.geom, b.geom)""",
    "buildings whose segment differs from their parcel's": """
        SELECT count(*) FROM buildings b JOIN parcels p USING (loc_id)
        WHERE b.segment IS DISTINCT FROM p.segment""",
    "buildings whose utility differs from their site's": """
        SELECT count(*) FROM buildings b JOIN parcels p USING (loc_id)
        JOIN sites s USING (site_id) WHERE b.utility IS DISTINCT FROM s.utility""",
    "sites whose parcel count is wrong": """
        SELECT count(*) FROM sites s
        LEFT JOIN (SELECT site_id, count(*) n FROM parcels GROUP BY 1) p
            USING (site_id)
        WHERE s.parcels IS DISTINCT FROM p.n""",
    "sites whose building count or area is wrong": """
        SELECT count(*) FROM sites s
        LEFT JOIN (SELECT p.site_id, count(*) n, sum(b.area_sqft) a
                   FROM buildings b JOIN parcels p USING (loc_id) GROUP BY 1) b
            USING (site_id)
        WHERE s.buildings <> coalesce(b.n, 0)
            OR abs(s.area_sqft - coalesce(b.a, 0)) > 1""",
    "sites whose owner, local owner or tenure differs from the main parcel": """
        SELECT count(*) FROM sites s JOIN parcels p ON p.loc_id = s.main_loc_id
        WHERE s.owner IS DISTINCT FROM p.owner
            OR s.local_owner IS DISTINCT FROM p.local_owner
            OR s.tenure_years IS DISTINCT FROM p.tenure_years""",
    "sites whose main parcel is in another site": """
        SELECT count(*) FROM sites s JOIN parcels p ON p.loc_id = s.main_loc_id
        WHERE p.site_id IS DISTINCT FROM s.site_id""",
    "measured buildings with no matching LBER kWh": """
        SELECT count(*) FROM buildings b
        WHERE b.electricity_source = 'measured' AND NOT EXISTS (
            SELECT 1 FROM lber_matches m
            WHERE m.building_id = b.building_id
                AND m.reporting_year = b.grid_kwh_year
                AND m.grid_kwh = b.grid_kwh)""",
    "LBER matches whose kWh differs from raw_lber": """
        SELECT count(*) FROM lber_matches m
        JOIN raw_lber l USING (reporting_year, objectid)
        WHERE m.grid_kwh IS DISTINCT FROM l.grid_kwh""",
    "LBER matches whose region differs from the pilot town's": """
        SELECT count(*) FROM lber_matches m JOIN pilot_towns t USING (town_id)
        WHERE m.region <> t.region""",
    "LBER rows both matched and unmatched": """
        SELECT count(*) FROM lber_matches JOIN lber_unmatched
            USING (reporting_year, objectid)""",
    "parcels whose use class differs from use_code_classes": """
        SELECT count(*) FROM parcels p JOIN use_code_classes u
            ON u.town_id = p.town_id AND u.use_code = p.use_code
        WHERE p.use_class IS DISTINCT FROM u.use_class""",
    "funnel rows for sites that no longer exist (rerun make funnel)": """
        SELECT count(*) FROM site_funnel f
        WHERE NOT EXISTS (SELECT 1 FROM sites s WHERE s.site_id = f.site_id)""",
    "latest scores for sites no longer in the funnel (rerun make score)": """
        SELECT count(*) FROM site_scores sc
        WHERE sc.run_id = (SELECT max(run_id) FROM score_runs)
            AND NOT EXISTS (
                SELECT 1 FROM site_funnel f WHERE f.site_id = sc.site_id
                    AND (f.dropped_by IS NULL OR f.dropped_by = 'peak'))""",
    "candidate sites missing from the funnel (rerun make funnel)": """
        SELECT count(*) FROM site_evidence s WHERE s.candidate
            AND NOT EXISTS (SELECT 1 FROM site_funnel f WHERE f.site_id = s.site_id)""",
    "funnel rows whose segment or utility differs from the site's": """
        SELECT count(*) FROM site_funnel f JOIN sites s USING (site_id)
        WHERE f.segment IS DISTINCT FROM s.segment
            OR f.utility IS DISTINCT FROM s.utility""",
}

FOR_INFORMATION = {
    "near-duplicate buildings (flagged, area kept)": (
        "SELECT count(*) FROM buildings WHERE near_duplicate_of IS NOT NULL"
    ),
    "buildings on no parcel": "SELECT count(*) FROM buildings WHERE loc_id IS NULL",
    "buildings whose footprint town differs from the parcel town": """
        SELECT count(*) FROM buildings b JOIN parcels p USING (loc_id)
        WHERE b.footprint_town_id <> p.town_id""",
    "buildings matched by more than one LBER row in a year": """
        SELECT count(*) FROM (SELECT 1 FROM lber_matches
            GROUP BY building_id, reporting_year HAVING count(*) > 1) x""",
    "parcels in no site (no building in their group)": (
        "SELECT count(*) FROM parcels WHERE site_id IS NULL"
    ),
}


def run(conn) -> dict[str, int]:
    """Count for every must-be-zero check."""
    conn.execute("SET jit = off")
    return {name: conn.execute(sql).fetchone()[0] for name, sql in MUST_BE_ZERO.items()}


def main() -> int:
    with connect() as conn:
        failures = {k: v for k, v in run(conn).items() if v}
        print("Must be zero:")
        for name in MUST_BE_ZERO:
            print(f"  {failures.get(name, 0):>8,}  {name}")
        print("For information:")
        for name, sql in FOR_INFORMATION.items():
            print(f"  {conn.execute(sql).fetchone()[0]:>8,}  {name}")
    print("FAILED" if failures else "OK")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
