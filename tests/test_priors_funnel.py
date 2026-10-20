import pytest

from prospect.priors import funnel

NG = "National Grid (Massachusetts Electric)"
CFG = {
    "connected_solutions": {"eligible_utilities": {"value": [NG]}},
    "funnel": {"min_kwh_per_month": {"value": 10000}, "min_peak_kw": {"value": 200}},
    "intensity": {
        "segments": {
            "generic": {
                "prior": {"median": 10.0},
                "prior_from": "pilot measured, our area",
            },
            "laundry": {
                "prior": {"median": 4.0},
                "prior_from": "manufacturing (proxy)",
            },
        }
    },
    "profiles": {
        "no_open_profile": {"segments": ["laundry"], "use_codes": ["332"]},
        "comstock_types": {
            "segments": {},
            "generic_use_codes": {"340": ["SmallOffice", "LargeOffice"]},
        },
    },
    "simulation": {
        "pooled": {"load_factor": {"median": 0.4}},
        "types": {
            "SmallOffice": {
                "floor_area_median_sqft": 5000,
                "load_factor": {"median": 0.3},
            },
            "LargeOffice": {
                "floor_area_median_sqft": 300000,
                "load_factor": {"median": 0.5},
            },
        },
    },
}


def site(utility=NG, segment="generic", flag="known"):
    return {
        "site_id": "s",
        "region": "worcester",
        "segment": segment,
        "utility": utility,
        "utility_flag": flag,
    }


def building(area, code="340", segment="generic", kwh=None):
    return {
        "segment": segment,
        "electricity_source": "measured" if kwh else "estimated",
        "grid_kwh": kwh,
        "area_sqft": area,
        "use_code": code,
    }


def test_municipal_site_is_dropped_first_and_flagged():
    row = funnel.evaluate(site("Holden MLD", flag="municipal"), [building(400000)], CFG)
    assert row["dropped_by"] == "utility"
    assert "municipal_plant" in row["flags"]


def test_small_use_is_dropped_at_the_kwh_line():
    row = funnel.evaluate(site(), [building(10000)], CFG)  # 100,000 kWh a year
    assert row["dropped_by"] == "kwh"
    assert row["tier"] == 2


def test_measured_large_office_survives_as_tier_one():
    # 2,000,000 kWh a year / 8760 / 0.5 (LargeOffice by floor area) = 457 kW
    row = funnel.evaluate(site(), [building(250000, kwh=2_000_000)], CFG)
    assert row["profile"] == "LargeOffice"
    assert row["peak_kw"] == pytest.approx(2_000_000 / 8760 / 0.5)
    assert row["dropped_by"] is None and row["tier"] == 1


def test_peak_line_and_no_open_profile():
    # 60,000 sq ft x 4 kWh = 240,000 kWh a year, over the kWh line, but
    # 240,000 / 8760 / 0.4 (pooled load factor) = 68 kW, under 200.
    row = funnel.evaluate(
        site(segment="laundry"), [building(60000, segment="laundry")], CFG
    )
    assert row["profile"] == "no open profile" and row["load_factor"] == 0.4
    assert row["dropped_by"] == "peak"
    assert "no_open_profile" in row["flags"]


def test_stage_survival_follows_the_dropping_filter():
    assert funnel.passed({"dropped_by": "kwh"}, "utility")
    assert not funnel.passed({"dropped_by": "kwh"}, "kwh")
    assert funnel.passed({"dropped_by": None}, "peak")
    assert not funnel.passed({"dropped_by": "utility"}, "utility")


def test_store_keeps_dropped_sites(db):
    rows = [
        funnel.evaluate(site(), [building(10000)], CFG),
        funnel.evaluate(site("Holden MLD", flag="municipal"), [building(400000)], CFG),
    ]
    rows[1]["site_id"] = "t"
    funnel.store(db, rows)
    assert db.execute(
        "SELECT site_id, dropped_by, flags FROM site_funnel ORDER BY site_id"
    ).fetchall() == [("s", "kwh", []), ("t", "utility", ["municipal_plant"])]
