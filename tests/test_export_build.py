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


def test_draws_block_keeps_every_draw_in_physical_units():
    r = {
        "kwm_g2": [10.04, 0.0],
        "kwm_g3": [0.0, 20.06],
        "blocks_draws": [1, 2],
        "peak_kw": [301.26, 1999.94],
        "g3_draws": [False, True],
    }
    assert build.draws_block(r) == {
        "kwm_g2": [10.0, 0.0],
        "kwm_g3": [0.0, 20.1],
        "blocks": [1, 2],
        "peak_kw": [301.3, 1999.9],
        "g3": [0, 1],
    }


def test_manifest_leaves_cost_and_host_benefit_empty():
    from prospect.priors import config

    m = build.manifest(
        config.load(), [{"utility": "National Grid (Massachusetts Electric)"}]
    )
    assert m["costs"]["installed_cost_usd_per_block"] is None
    assert m["costs"]["min_host_benefit_usd_per_year"] is None
    assert m["demand_rates_usd_per_kw_month"] == {
        "National Grid (Massachusetts Electric)": {"G-2": 15.24, "G-3": 10.61}
    }
    assert m["connected_solutions"]["site_exports"] is False
    assert any(p["file"] == "costs" for p in m["placeholders"])
