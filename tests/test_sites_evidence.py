from prospect.sites.build import build


def test_site_evidence_summarizes_its_buildings(db, raw, lber_rows):
    parcel, footprint = raw
    town, lber = lber_rows
    town(348, label="Mass Electric")
    parcel("Z", 0.05, 0, OWNER1="A MUCH LONGER OWNER NAME FOR WIDTH")
    parcel("A1", 0, 0, USE_CODE="316", OWNER1="ACME", BLD_AREA=6000)
    # Both A2 records have no building area, so the classed one (332) is
    # the primary record: a generic candidate, area from footprint x stories.
    parcel("A2", 0.001, 0, USE_CODE="104", OWNER1="ACME")
    parcel("A2", 0.001, 0, USE_CODE="332", OWNER1="ACME", STORIES="2")
    footprint(0.0001, 0.0001, 600)
    footprint(0.0011, 0.0001, 1000)
    lber(1, 0.00015, 0.00015, kbtu=341214)  # inside the A1 footprint
    build(db)
    building = db.execute(
        "SELECT loc_id, candidate, segment, electricity_source, lber_method,"
        " lber_confidence, area_source, utility_flag, mixed_res_ci"
        " FROM building_evidence ORDER BY loc_id"
    ).fetchall()
    assert building == [
        (
            "A1",
            True,
            "warehouse",
            "measured",
            "point_in_footprint",
            "high",
            "assessor",
            "known",
            False,
        ),
        (
            "A2",
            True,
            "generic",
            "estimated",
            None,
            None,
            "footprint_x_stories",
            "known",
            True,
        ),
    ]
    site = db.execute(
        "SELECT buildings, candidate_buildings, measured_buildings,"
        " round(measured_kwh), lber_matched_buildings, ambiguous_matches,"
        " round(area_share_assessor::numeric, 2),"
        " round(area_share_footprint_x_stories::numeric, 2), mixed_res_ci, segment"
        " FROM site_evidence"
    ).fetchall()
    # A1 6,000 sq ft assessor; A2 1,000 x 2 stories = 2,000 estimated.
    assert site == [(2, 2, 1, 100000, 1, 0, 0.75, 0.25, True, "warehouse")]
