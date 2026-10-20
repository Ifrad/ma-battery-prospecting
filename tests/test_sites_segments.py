import pytest

from prospect.sites.build import build
from prospect.sites.segments import load_config, segment

CONFIG = load_config()
WORCESTER, BOSTON = 348, 35


@pytest.mark.parametrize(
    "code, owner, town, expected",
    [
        ("955", "ANY OWNER", WORCESTER, ("hospital", "use_code")),
        ("9550", "ANY OWNER", WORCESTER, ("hospital", "use_code")),
        ("305", "ANY OWNER", WORCESTER, ("hospital", "use_code")),
        ("979", "ANY OWNER", BOSTON, ("hospital", "use_code")),
        ("979", "ANY OWNER", WORCESTER, ("generic", "default")),
        (
            "049C",
            "WORCESTER MEMORIAL HOSPITAL INC",
            WORCESTER,
            ("hospital", "owner_keyword"),
        ),
        ("340", "UMASS MEDICAL CENTER", WORCESTER, ("hospital", "owner_keyword")),
        (
            "316",
            "NEW ENGLAND COLD STORAGE LLC",
            WORCESTER,
            ("cold_storage", "owner_keyword"),
        ),
        ("400", "ACME FOODS INC", WORCESTER, ("food_production", "owner_keyword")),
        ("325", "BEST CLEANERS", WORCESTER, ("laundry", "owner_keyword")),
        ("304", "ANY OWNER", WORCESTER, ("other_healthcare", "use_code")),
        ("3420", "ANY OWNER", WORCESTER, ("other_healthcare", "use_code")),
        ("316", "ANY OWNER", WORCESTER, ("warehouse", "use_code")),
        ("401", "ANY OWNER", WORCESTER, ("warehouse", "use_code")),
        ("400", "ANY OWNER", WORCESTER, ("manufacturing", "use_code")),
        (
            "340",
            "COMMUNITY HEALTH CENTER",
            WORCESTER,
            ("other_healthcare", "owner_keyword"),
        ),
        ("316", "NORTHEAST HEALTH LLC", WORCESTER, ("warehouse", "use_code")),
        ("340", "NOFOODS REALTY", WORCESTER, ("generic", "default")),  # word start
        ("340", "THEALTHY REALTY", WORCESTER, ("generic", "default")),
        ("340", "ACME LLC", WORCESTER, ("generic", "default")),
        ("955V", "BROCKTON HOSPITAL INC", WORCESTER, (None, None)),
    ],
)
def test_segment_rules(code, owner, town, expected):
    assert segment(code, owner, town, CONFIG) == expected


def test_only_candidates_get_segments_and_955v_is_never_a_hospital(db, raw):
    parcel, footprint = raw
    parcel("H", 0, 0, USE_CODE="955", OWNER1="BROCKTON HOSPITAL INC", BLD_AREA=9000)
    footprint(0.0001, 0.0001, 900)
    parcel("V", 0.01, 0, USE_CODE="955V", OWNER1="BROCKTON HOSPITAL INC")
    footprint(0.0101, 0.0001, 100)
    parcel("R", 0.02, 0, USE_CODE="101", OWNER1="SMITH JOHN")
    footprint(0.0201, 0.0001, 100)
    build(db)
    rows = db.execute(
        "SELECT p.loc_id, b.segment, b.segment_source FROM buildings b"
        " JOIN parcels p USING (loc_id) ORDER BY p.loc_id"
    ).fetchall()
    assert rows == [("H", "hospital", "use_code"), ("R", None, None), ("V", None, None)]


def test_site_takes_segment_of_its_largest_candidate_building(db, raw):
    parcel, footprint = raw
    # A long name elsewhere sets the town's name width, so ACME is not cut.
    parcel("Z", 0.05, 0, OWNER1="A MUCH LONGER OWNER NAME FOR WIDTH")
    parcel("A1", 0, 0, USE_CODE="316", OWNER1="ACME", BLD_AREA=20000)
    parcel("A2", 0.001, 0, USE_CODE="340", OWNER1="ACME", BLD_AREA=2000)
    footprint(0.0001, 0.0001, 5000)
    footprint(0.0011, 0.0001, 500)
    build(db)
    assert db.execute("SELECT segment, segment_source FROM sites").fetchall() == [
        ("warehouse", "use_code")
    ]


@pytest.mark.parametrize(
    "code,owner,expected",
    [
        ("3000", "AUBURN HOSPITALITY", ("generic", "default")),
        ("3420", "HOLDEN VETERINARY HOSPITAL", ("other_healthcare", "use_code")),
        ("955", "VETERINARY HOSPITAL", ("hospital", "use_code")),
        ("340", "REGIONAL HOSPITALS", ("hospital", "owner_keyword")),
        ("340", "REGIONAL MEDICAL CENTRES", ("hospital", "owner_keyword")),
        ("316", "ACME REFRIGERATION", ("cold_storage", "owner_keyword")),
        ("325", "ACME LAUNDRIES", ("laundry", "owner_keyword")),
        ("340", "FIRST CLASS HEALTHCARE", ("other_healthcare", "owner_keyword")),
        ("340", "HEALTHY INVESTMENTS", ("generic", "default")),
    ],
)
def test_whole_words_variants_and_veterinary_exclusion(code, owner, expected):
    assert segment(code, owner, WORCESTER, CONFIG) == expected


@pytest.mark.parametrize(
    "code,owner,area,expected",
    [
        ("326", "JJ'S CREAMERY", 1640, ("generic", "default")),
        ("316", "ACME FOODS DISTRIBUTOR", 19999, ("warehouse", "use_code")),
        ("316", "ACME FOODS", 20000, ("food_production", "owner_keyword")),
        ("400", "LIBERTY BAKERY", 17911, ("food_production", "owner_keyword")),
        ("400", "PERFORMANCE FOOD GROUP", 105770, ("food_production", "owner_keyword")),
        ("340", "ACME FOODS", None, ("generic", "default")),
        ("400", "ACME DAIRIES", None, ("food_production", "owner_keyword")),
    ],
)
def test_food_requires_industrial_code_or_site_area(code, owner, area, expected):
    assert (
        segment(
            code,
            owner,
            WORCESTER,
            CONFIG,
            site_area_sqft=area,
            food_min_area_sqft=20000,
        )
        == expected
    )


def test_food_threshold_uses_whole_site_area(db, raw):
    parcel, footprint = raw
    parcel("Z", 0.05, 0, OWNER1="A MUCH LONGER OWNER NAME FOR WIDTH")
    parcel("A", 0, 0, USE_CODE="316", OWNER1="ACME FOODS", BLD_AREA=12000)
    parcel("B", 0.001, 0, USE_CODE="316", OWNER1="ACME FOODS", BLD_AREA=12000)
    footprint(0.0001, 0.0001, 12000)
    footprint(0.0011, 0.0001, 12000)
    build(db)
    assert db.execute("SELECT segment FROM sites").fetchall() == [("food_production",)]
