"""The committed export: schema, size budget, and parity with the Python
model. Rounding draws to 0.1 kW-month and 0.1 kW moves value per block by a
few dollars (at most about $8 a draw with export on, where each kW of peak is
worth 1.5 x 0.61 x 0.87 x $200), hence the tolerance."""

import copy
import json

import numpy as np
import pytest

from prospect.export import build, recompute, schema
from prospect.model import grid, run, score
from prospect.priors import config

EXPORT = build.OUT
VALUE_TOL = 10.0
CFG = config.load()


def load(region):
    return json.loads((EXPORT / f"{region}.geojson").read_text())


MANIFEST = json.loads((EXPORT / "manifest.json").read_text())


@pytest.mark.parametrize("region", build.REGIONS)
def test_committed_export_passes_the_schema(region):
    assert schema.check(load(region), MANIFEST) == []


def test_every_export_file_is_within_5_mb():
    assert schema.too_large(EXPORT) == []


@pytest.mark.parametrize("region", build.REGIONS)
def test_export_draws_reproduce_the_scored_values(region):
    for f in load(region)["features"]:
        s = f["properties"]
        for name in build.SCENARIOS:
            st = recompute.defaults(MANIFEST)
            st["connected_solutions"] = name == "with_connected_solutions"
            r = recompute.site_summary(s, MANIFEST, st)
            e = s["scenarios"][name]
            for k in ("p10", "p50", "p90"):
                assert r["value_per_block"][k] == pytest.approx(
                    e["value_per_block"][k], abs=VALUE_TOL
                )
                assert r["total"][k] == pytest.approx(e["total"][k], abs=VALUE_TOL)
            assert r["blocks"] == pytest.approx(s["blocks"], abs=0.01)
            for k in ("demand_savings", "connected_solutions"):
                assert r["streams"][k]["share"] == pytest.approx(
                    e["streams"][k]["share"], abs=0.01
                )


NG = "National Grid (Massachusetts Electric)"
SITE = {
    "site_id": "P1",
    "region": "worcester",
    "segment": "warehouse",
    "utility": NG,
    "tier": 2,
    "profile": "Warehouse",
    "flags": [],
    "passes_200kw": True,
}
BUILDINGS = [
    {
        "building_id": 7,
        "segment": "warehouse",
        "electricity_source": "estimated",
        "grid_kwh": None,
        "area_sqft": 300000.0,
        "lber_confidence": None,
        "area_source": "assessor",
    }
]


def exported(cfg):
    """SITE scored by the Python model, then passed through the export."""
    rows = score.score_site(SITE, BUILDINGS, cfg)
    names = [c.strip() for c in run.COLUMNS.split(",")]
    stored = [dict(zip(names, run.row(1, SITE, r), strict=True)) for r in rows]
    cs = next(r for r in stored if r["scenario"] == "with_connected_solutions")
    site = {
        **SITE,
        "draws": build.draws_block(cs),
        "event_window": grid.event_ratios(SITE, cfg),
    }
    return rows, site


@pytest.mark.parametrize("exports", [False, True])
def test_export_recompute_matches_the_model_draw_by_draw(exports):
    cfg = copy.deepcopy(CFG)
    cfg["connected_solutions"]["site_exports"]["value"] = exports
    m = build.manifest(cfg, [SITE])
    rows, site = exported(cfg)
    st = recompute.defaults(m)
    for r in rows:
        st["connected_solutions"] = r["scenario"] == "with_connected_solutions"
        x = recompute.value_draws(site, m, st)
        assert x["value"] == pytest.approx(r["draws"]["value_per_block"], abs=VALUE_TOL)


@pytest.mark.parametrize("cs_on", [False, True])
@pytest.mark.parametrize("rate_scale", [1.0, 1.25])
def test_export_matches_the_model_with_cs_on_off_and_a_changed_demand_rate(
    cs_on, rate_scale
):
    m = build.manifest(CFG, [SITE])
    rows, site = exported(CFG)
    scenario = "with_connected_solutions" if cs_on else "demand_savings"
    r = next(x for x in rows if x["scenario"] == scenario)
    st = recompute.defaults(m)
    st["connected_solutions"] = cs_on
    st["rates"] = {
        u: {k: v * rate_scale for k, v in sched.items()}
        for u, sched in st["rates"].items()
    }
    got = recompute.site_summary(site, m, st)
    # The model side: its own draws, demand repriced at the changed rate.
    x = r["draws"]
    rates = {
        k: v * rate_scale for k, v in m["demand_rates_usd_per_kw_month"][NG].items()
    }
    demand = x["kwm_g2"] * rates["G-2"] + x["kwm_g3"] * rates["G-3"]
    value = demand + (x["grid_usd"] if cs_on else 0.0)
    for q, want in zip(
        ("p10", "p50", "p90"), np.percentile(value, [10, 50, 90]), strict=True
    ):
        assert got["value_per_block"][q] == pytest.approx(want, abs=VALUE_TOL)
    assert got["blocks"] == pytest.approx(r["blocks"])
    share = (
        float(np.median(x["grid_usd"]))
        / (float(np.median(demand)) + float(np.median(x["grid_usd"])))
        if cs_on
        else 0.0
    )
    assert got["streams"]["connected_solutions"]["share"] == pytest.approx(
        share, abs=0.01
    )


def test_committed_manifest_names_its_version_config_and_sources():
    assert schema.check_manifest(MANIFEST) == []
    assert MANIFEST["config_hash"] == run.config_hash()
    assert "enernoc" not in json.dumps(MANIFEST["sources"]).lower()


def test_version_falls_back_without_git(monkeypatch):
    import subprocess

    def fail(*a, **k):
        raise OSError

    monkeypatch.setattr(subprocess, "run", fail)
    assert build.version()  # the package version


@pytest.mark.parametrize(
    "status, expected", [("", "v1-2-gabc"), (" M prospect/x.py", "v1-2-gabc-dirty")]
)
def test_version_is_dirty_only_for_changes_outside_the_export(
    monkeypatch, status, expected
):
    calls = []

    def fake(*args):
        calls.append(args)
        return "v1-2-gabc" if args[0] == "describe" else status

    monkeypatch.setattr(build, "git", fake)
    assert build.version() == expected
    assert calls[0] == ("describe", "--tags", "--always")
    assert calls[1][-1] == ":!export" and "--untracked-files=no" in calls[1]
