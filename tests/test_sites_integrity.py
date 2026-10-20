"""One test per integrity fix in migration 0016."""

import psycopg
import pytest

from prospect.sites import checks
from prospect.sites.build import build


def test_exact_duplicate_footprint_is_dropped_and_near_duplicate_flagged(db, raw):
    parcel, footprint = raw
    parcel("A", 0, 0)
    footprint(0.0001, 0.0001, 600)
    footprint(0.0001, 0.0001, 600)  # same shape again: a source duplicate
    footprint(0.0005, 0.0005, 400)
    footprint(0.000505, 0.0005, 400)  # shifted 2.5 percent of its width
    build(db)
    rows = db.execute(
        "SELECT building_id, near_duplicate_of FROM buildings ORDER BY building_id"
    ).fetchall()
    assert len(rows) == 3
    assert [r[1] is not None for r in rows] == [False, False, True]
    assert rows[2][1] == rows[1][0]


def test_parcels_without_a_site_keep_no_site_id_and_site_ids_must_exist(db, raw):
    parcel, footprint = raw
    parcel("A", 0, 0, OWNER1="ACME")
    footprint(0.0001, 0.0001, 600)
    parcel("V", 0.05, 0, OWNER1="LAND ONLY")  # vacant, alone
    build(db)
    assert db.execute(
        "SELECT loc_id, site_id FROM parcels ORDER BY loc_id"
    ).fetchall() == [
        ("A", "A"),
        ("V", None),
    ]
    with pytest.raises(psycopg.errors.ForeignKeyViolation):
        db.execute("UPDATE parcels SET site_id = 'NO SUCH SITE' WHERE loc_id = 'V'")


def test_lber_matches_go_with_their_raw_row(db, raw, lber_rows):
    parcel, footprint = raw
    town, lber = lber_rows
    town(348)  # Worcester, a pilot town
    parcel("A", 0, 0)
    footprint(0.0001, 0.0001, 600)
    lber(1, 0.00015, 0.00015)
    build(db)
    assert db.execute("SELECT count(*) FROM lber_matches").fetchone()[0] == 1
    db.execute("DELETE FROM raw_lber")
    assert db.execute("SELECT count(*) FROM lber_matches").fetchone()[0] == 0


def test_building_takes_its_parcel_town_not_its_footprint_town(db, raw):
    parcel, footprint = raw
    parcel("A", 0, 0, town=17)  # the footprint fixture says Worcester (348)
    footprint(0.0001, 0.0001, 600)
    build(db)
    assert db.execute(
        "SELECT b.footprint_town_id, e.town_id FROM buildings b"
        " JOIN building_evidence e USING (building_id)"
    ).fetchone() == (348, 17)


def test_segment_and_confidence_values_are_checked(db, raw):
    parcel, footprint = raw
    parcel("A", 0, 0, USE_CODE="316")
    footprint(0.0001, 0.0001, 600)
    build(db)
    with pytest.raises(psycopg.errors.CheckViolation):
        db.execute("UPDATE buildings SET segment = 'factory'")
    with pytest.raises(psycopg.errors.CheckViolation):
        db.execute("UPDATE sites SET segment_source = 'guess'")
    with pytest.raises(psycopg.errors.CheckViolation):
        db.execute(
            "INSERT INTO lber_matches (reporting_year, objectid, town_id, region,"
            " building_id, method, confidence, candidates)"
            " SELECT 2024, 1, 348, 'worcester', building_id, 'ubid', 'certain', 1"
            " FROM buildings LIMIT 1"
        )


def test_db_check_passes_on_a_build_and_catches_drift(db, raw):
    parcel, footprint = raw
    parcel("A", 0, 0, OWNER1="ACME")
    footprint(0.0001, 0.0001, 600)
    build(db)
    assert not any(checks.run(db).values())
    db.execute("UPDATE sites SET parcels = parcels + 1")
    assert checks.run(db)["sites whose parcel count is wrong"] == 1
