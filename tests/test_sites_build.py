from prospect.sites.build import build


def parcel_row(db, loc_id):
    return db.execute(
        "SELECT records, owner, use_code, use_class, bld_area, stories, mixed_res_ci"
        " FROM parcels WHERE loc_id = %s",
        (loc_id,),
    ).fetchone()


def building_rows(db, loc_id):
    return db.execute(
        "SELECT round(area_sqft), area_source FROM buildings"
        " WHERE loc_id IS NOT DISTINCT FROM %s ORDER BY footprint_sqft DESC",
        (loc_id,),
    ).fetchall()


def test_assessor_area_is_shared_by_footprint_area(db, raw):
    parcel, footprint = raw
    parcel("A", 0, 0, USE_CODE="316", BLD_AREA=10000, OWNER1="ACME")
    footprint(0.0001, 0.0001, 600)
    footprint(0.0005, 0.0005, 400)
    build(db)
    assert parcel_row(db, "A")[3] == "commercial_industrial"
    assert building_rows(db, "A") == [(6000, "assessor"), (4000, "assessor")]


def test_multi_record_parcel_sums_units_and_takes_largest_record(db, raw):
    parcel, footprint = raw
    parcel("B", 0.01, 0, USE_CODE="3221", BLD_AREA=55720, OWNER1="UNIT TWO LLC")
    parcel("B", 0.01, 0, USE_CODE="995", BLD_AREA=0, OWNER1="LAND OWNER LLC")
    parcel("B", 0.01, 0, USE_CODE="3221", BLD_AREA=112339, OWNER1="UNIT ONE LLC")
    build(db)
    records, owner, _, _, bld_area, _, mixed = parcel_row(db, "B")
    assert (records, owner, bld_area, mixed) == (3, "UNIT ONE LLC", 168059, False)


def test_repeated_area_counts_once(db, raw):
    parcel, _ = raw
    parcel("C", 0.02, 0, USE_CODE="343", BLD_AREA=5000)
    parcel("C", 0.02, 0, USE_CODE="343", BLD_AREA=5000)
    build(db)
    assert parcel_row(db, "C")[4] == 5000


def test_residential_and_commercial_records_are_flagged_mixed(db, raw):
    parcel, _ = raw
    parcel("D", 0.03, 0, USE_CODE="104", BLD_AREA=3000)
    parcel("D", 0.03, 0, USE_CODE="332", BLD_AREA=2000)
    build(db)
    assert parcel_row(db, "D")[6] is True


def test_area_falls_back_to_stories_then_footprint(db, raw):
    parcel, footprint = raw
    parcel("E", 0.04, 0, USE_CODE="400", BLD_AREA=0, STORIES="1.75")
    footprint(0.0401, 0.0001, 1000)
    parcel("F", 0.05, 0, USE_CODE="400", STORIES="0", RES_AREA=9999)
    footprint(0.0501, 0.0001, 1000)
    build(db)
    assert building_rows(db, "E") == [(1750, "footprint_x_stories")]
    assert building_rows(db, "F") == [(1000, "footprint_only")]


def test_vacant_hospital_code_has_no_class(db, raw):
    parcel, _ = raw
    parcel("G", 0.06, 0, USE_CODE="955V", BLD_AREA=0)
    build(db)
    assert parcel_row(db, "G")[3] is None


def test_footprint_outside_any_parcel_keeps_footprint_area(db, raw):
    _, footprint = raw
    footprint(0.5, 0.5, 750)
    build(db)
    assert building_rows(db, None) == [(750, "footprint_only")]


def test_rebuild_gives_same_rows(db, raw):
    parcel, footprint = raw
    parcel("A", 0, 0, USE_CODE="316", BLD_AREA=10000)
    footprint(0.0001, 0.0001, 600)
    build(db)
    build(db)
    assert db.execute("SELECT count(*) FROM buildings").fetchone()[0] == 1
