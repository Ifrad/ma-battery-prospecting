from prospect.sites.build import build

WORCESTER, HOLDEN, MIDDLEBOROUGH = 348, 134, 182


def test_utility_flags_by_town(db, raw, lber_rows):
    parcel, footprint = raw
    town, _ = lber_rows
    town(
        WORCESTER, elec="National Grid (Massachusetts Electric)", label="Mass Electric"
    )
    town(HOLDEN, x=1, elec="Holden Municipal Light Department", label="Municipal")
    town(
        MIDDLEBOROUGH,
        x=2,
        elec="Middleborough Gas and Electric Department, Eversource Energy",
        label="Municipal, NSTAR Electric d/b/a Eversource Energy",
    )
    for x, town_id in [(0, WORCESTER), (1, HOLDEN), (2, MIDDLEBOROUGH)]:
        parcel(f"T{town_id}", x, 0, town=town_id, OWNER1=f"OWNER {town_id}")
        footprint(x + 0.0001, 0.0001, 500)
    build(db)
    rows = db.execute(
        "SELECT p.town_id, b.utility_flag, s.utility_flag FROM buildings b"
        " JOIN parcels p USING (loc_id) JOIN sites s USING (site_id)"
        " ORDER BY p.town_id"
    ).fetchall()
    assert rows == [
        (HOLDEN, "municipal", "municipal"),
        (MIDDLEBOROUGH, "unknown", "unknown"),
        (WORCESTER, "known", "known"),
    ]


def test_building_takes_its_parcels_town(db, raw, lber_rows):
    parcel, footprint = raw
    town, _ = lber_rows
    town(WORCESTER, label="Mass Electric")
    town(HOLDEN, x=1, label="Municipal")
    parcel("A", 0, 0, town=HOLDEN)  # footprints in the fixture say Worcester
    footprint(0.0001, 0.0001, 500)
    build(db)
    assert db.execute("SELECT utility_flag FROM buildings").fetchone() == ("municipal",)
