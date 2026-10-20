from prospect.export import build


def scenario(p50):
    return {
        "value_per_block": {"p10": p50 - 1, "p50": p50, "p90": p50 + 1},
        "total": {"p10": p50 - 1, "p50": p50, "p90": p50 + 1},
        "break_even": {
            "p50": 10,
            "p10": 5,
            "p50_itc": 14,
            "p10_itc": 7,
            "itc_applies": True,
        },
        "streams": {
            "demand_savings": {"p50": p50, "share": 1.0},
            "connected_solutions": {"p50": 0, "share": 0.0},
        },
        "top_drivers": [],
    }


SITE = {
    "site_id": "S1",
    "region": "worcester",
    "owner": "ACME",
    "site_addr": "1 MAIN ST",
    "town": "Worcester",
    "segment": "warehouse",
    "utility": "U",
    "tier": 2,
    "flags": ["capped", "no_open_profile"],
    "blocks": 1.0,
    "lat": 42.2,
    "lon": -71.8,
    "model_rank": 1,
    "size_rank": 9,
    "scenarios": {n: scenario(100) for n in build.SCENARIOS},
}


def test_geojson_puts_coordinates_in_the_geometry_only():
    f = build.geojson([SITE])["features"][0]
    assert f["geometry"] == {"type": "Point", "coordinates": [-71.8, 42.2]}
    assert "lat" not in f["properties"] and f["properties"]["size_rank"] == 9


def test_csv_has_one_row_per_scenario_with_both_ranks():
    rows = build.csv_rows([SITE])
    assert [r["scenario"] for r in rows] == list(build.SCENARIOS)
    assert set(rows[0]) == set(build.CSV_COLUMNS)
    assert rows[0]["flags"] == "capped;no_open_profile"
    assert rows[0]["model_rank"] == 1 and rows[0]["size_rank"] == 9
