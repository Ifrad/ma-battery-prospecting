import pytest

from prospect.sites.build import build
from prospect.sites.group import load_config
from prospect.sites.lber import normalize_address
from prospect.sites.ubid import encode

WORDS = load_config()["lber_match"]["address_words"]


def test_normalize_address():
    assert normalize_address("10 Main Street", WORDS) == "10 MAIN ST"
    assert normalize_address("10  MAIN ST.", WORDS) == "10 MAIN ST"
    assert normalize_address("5 North Road", WORDS) == "5 N RD"
    assert normalize_address(None, WORDS) is None


def footprint_ubid(x, y, size=0.0002):
    """UBID of the test footprint box at (x, y), as the build computes it."""
    s, w = 42.26 + y, -71.8 + x
    return encode(s, w, s + size, w + size, s + size / 2, w + size / 2)


def matches(db):
    return db.execute(
        "SELECT objectid, method, confidence FROM lber_matches ORDER BY objectid"
    ).fetchall()


@pytest.fixture
def pilot_town(lber_rows):
    town, lber = lber_rows
    town(348)  # Worcester, a pilot town; covers all test parcels
    return lber


def test_methods_run_in_order(db, raw, pilot_town):
    parcel, footprint = raw
    lber = pilot_town
    parcel("A", 0, 0, SITE_ADDR="1 ELM ST")
    footprint(0.0001, 0.0001, 600)
    parcel("B", 0.01, 0, SITE_ADDR="2 OAK ST")
    footprint(0.0101, 0.0001, 900)
    footprint(0.0106, 0.0006, 300)
    parcel("C", 0.02, 0, SITE_ADDR="10 MAIN ST")
    footprint(0.0201, 0.0001, 500)
    # 1: right UBID, point outside everything
    lber(1, 0.3, 0.3, ubid=footprint_ubid(0.0001, 0.0001))
    # 2: point inside a footprint
    lber(2, 0.00015, 0.00015)
    # 3: point on parcel B, outside its two footprints
    lber(3, 0.0109, 0.0001)
    # 4: point outside parcels, address of parcel C
    lber(4, 0.3, 0.31, street="10 Main Street")
    # 5: nothing matches
    lber(5, 0.3, 0.32, street="99 Nowhere Rd")
    build(db)
    assert matches(db) == [
        (1, "ubid", "high"),
        (2, "point_in_footprint", "high"),
        (3, "point_in_parcel", "ambiguous, 2 buildings"),
        (4, "address", "low"),
    ]
    big = db.execute(
        "SELECT b.footprint_sqft FROM lber_matches m JOIN buildings b"
        " USING (building_id) WHERE m.objectid = 3"
    ).fetchone()[0]
    assert big == 900  # the largest footprint, never both
    unmatched = db.execute("SELECT objectid, reason FROM lber_unmatched").fetchall()
    assert unmatched == [(5, "outside parcels, no address match")]


def test_zero_or_negative_electricity_stays_missing(db, raw, pilot_town):
    parcel, footprint = raw
    lber = pilot_town
    for i, kbtu in enumerate([341214, 0, -5000]):
        parcel(f"P{i}", 0.01 * i, 0)
        footprint(0.01 * i + 0.0001, 0.0001, 500)
        lber(i + 1, 0.01 * i + 0.00015, 0.00015, kbtu=kbtu)
    build(db)
    rows = db.execute(
        "SELECT b.electricity_source, round(b.grid_kwh) FROM lber_matches m"
        " JOIN buildings b USING (building_id) ORDER BY m.objectid"
    ).fetchall()
    assert rows == [("measured", 100000), ("estimated", None), ("estimated", None)]


def test_rows_outside_pilot_towns_are_ignored(db, raw, lber_rows):
    town, lber = lber_rows
    town(1, x=2, y=2)  # Abington is a pilot town, but not where this point is
    town(999, x=1, y=1)  # not a pilot town
    lber(1, 1.1, 1.1)
    build(db)
    assert matches(db) == []
    assert db.execute("SELECT count(*) FROM lber_unmatched").fetchone()[0] == 0


def test_each_reporting_year_matches_once_and_latest_kwh_wins(db, raw, pilot_town):
    parcel, footprint = raw
    lber = pilot_town
    parcel("A", 0, 0)
    footprint(0.0001, 0.0001, 600)
    lber(7, 0.00015, 0.00015, kbtu=341214, year=2024)
    lber(7, 0.00015, 0.00015, kbtu=682428, year=2025)
    build(db)
    years = db.execute("SELECT reporting_year FROM lber_matches ORDER BY 1").fetchall()
    assert years == [(2024,), (2025,)]
    kwh, year = db.execute(
        "SELECT round(grid_kwh), grid_kwh_year FROM buildings"
    ).fetchone()
    assert (kwh, year) == (200000, 2025)
