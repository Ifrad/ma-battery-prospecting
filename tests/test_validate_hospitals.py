import pytest

from prospect.validate import hospitals

REF = {
    "kwh_sqft": {"min": 14.0, "median": 16.0, "max": 27.0},
    "load_factor": {"min": 0.39, "median": 0.45, "max": 0.62},
    "w_sqft": {"min": 2.6, "median": 3.8, "max": 7.2},
}


def row(**k):
    base = {
        "site_id": "S",
        "region": "worcester",
        "owner": "EXAMPLE HOSPITAL",
        "town": "Worcester",
        "tier": 2,
        "buildings": 1,
        "measured_buildings": 0,
        "area_sqft": 100000.0,
        "kwh": 1.9e6,
        "lber_kwh": None,
        "average_kw": 217.0,
        "peak_kw": 470.0,
        "load_factor": 0.45,
        "kwh_sqft": 19.0,
        "w_sqft": 4.7,
        "peak_below_average_draws": 0,
    }
    return {**base, **k}


def test_comstock_reference_reads_only_hospitals(tmp_path):
    (tmp_path / "sample.csv").write_text(
        "bldg_id,building_type,sqft\n1,Hospital,1000\n2,Warehouse,1000\n"
    )
    (tmp_path / "simulation.csv").write_text(
        "bldg_id,annual_kwh,month_mean_kw,month_peak_kw\n"
        "1,20000,2,4\n1,20000,3,5\n2,1,1,1\n"
    )
    [b] = hospitals.comstock_hospitals(tmp_path)
    assert b["kwh_sqft"] == 20.0
    assert b["load_factor"] == pytest.approx((0.5 + 0.6) / 2)
    assert b["w_sqft"] == pytest.approx(4.5)
    assert hospitals.comstock_hospitals(tmp_path / "missing") is None


def test_check_fails_only_on_load_factor_or_peak_below_average():
    assert hospitals.check(row(), REF) == {"fails": [], "outside": []}
    assert hospitals.check(row(load_factor=0.9), REF)["fails"] == [
        "load factor outside the ComStock hospitals"
    ]
    assert hospitals.check(row(peak_below_average_draws=3), REF)["fails"] == [
        "peak below average in 3 draws"
    ]
    high = hospitals.check(row(kwh_sqft=30.0, w_sqft=7.6), REF)
    assert high == {"fails": [], "outside": ["kWh per sq ft", "peak W per sq ft"]}


def test_section_says_circular_and_never_accuracy():
    x = row(tier=1, lber_kwh=1.8e6, measured_buildings=1, kwh_sqft=30.0)
    x.update(hospitals.check(x, REF))
    r = {"reference": REF, "comstock_buildings": 9, "sites": [x]}
    text = "\n".join(hospitals.section(r))
    assert "not validation and not accuracy" in text
    assert "1,800,000 (circular)" in text and "Load factor: circular" in text
    assert "Failed: none." in text
    assert "EXAMPLE HOSPITAL, tier 1, 30.0 kWh" in text
    assert "accurate" not in text
    [line] = hospitals.summary_line(r)
    assert "of 1 scored hospitals, none fail" in line and "(tier 1)" in line


def test_missing_comstock_data_says_not_run():
    assert "not run" in hospitals.summary_line(None)[0]
    assert "Not run" in hospitals.section(None)[-1]
