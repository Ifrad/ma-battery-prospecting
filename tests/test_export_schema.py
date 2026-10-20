"""The committed export: schema, size budget, and parity with the Python
model. Rounding draws to 0.1 kW-month and 0.1 kW moves value per block by a
few dollars (at most about $8 a draw with export on, where each kW of peak is
worth 1.5 x 0.61 x 0.87 x $200), and break-even by about seven times the
value gap (value over the annual cost factor), hence the tolerances."""

import copy
import json

import numpy as np
import pytest

from prospect.export import build, recompute, schema
from prospect.model import cost, grid, run, score
from prospect.priors import config

EXPORT = build.OUT
VALUE_TOL, BREAK_EVEN_TOL = 10.0, 100.0
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
            for k in ("p50", "p10", "p50_itc", "p10_itc"):
                assert r["break_even"][k] == pytest.approx(
                    e["break_even"][k], abs=BREAK_EVEN_TOL
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


def test_break_even_and_confidence_match_the_model_at_a_given_cost():
    m = build.manifest(CFG, [SITE])
    rows, site = exported(CFG)
    r = next(x for x in rows if x["scenario"] == "with_connected_solutions")
    got = recompute.site_summary(site, m, recompute.defaults(m))
    for k in ("p50", "p10", "p50_itc", "p10_itc"):
        assert got["break_even"][k] == pytest.approx(
            r["break_even"][k], abs=BREAK_EVEN_TOL
        )
    model_values = r["draws"]["value_per_block"]
    for installed, host, itc in [
        (180_000, 0, False),
        (260_000, 5_000, True),
        (90_000, 2_000, False),
    ]:
        want = cost.confidence(model_values, installed, host, CFG, itc, r["blocks"])
        have = recompute.confidence(
            got["values"], installed, host, m, itc, got["blocks"]
        )
        assert have == pytest.approx(want, abs=0.01)


def test_higher_cost_never_raises_recomputed_confidence():
    m = build.manifest(CFG, [SITE])
    _, site = exported(CFG)
    values = recompute.site_summary(site, m, recompute.defaults(m))["values"]
    c = [
        recompute.confidence(values, x, 0, m, False, 1.0) for x in (50e3, 150e3, 300e3)
    ]
    assert c == sorted(c, reverse=True) and np.isfinite(c).all()
