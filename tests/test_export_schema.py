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


def test_committed_manifest_was_made_on_a_clean_tree():
    assert not MANIFEST["version"].endswith("-dirty"), (
        f"export/manifest.json has version {MANIFEST['version']}: commit the"
        " code first, then run make export on a clean tree"
    )


def test_version_falls_back_without_git(monkeypatch):
    import subprocess

    def fail(*a, **k):
        raise OSError

    monkeypatch.setattr(subprocess, "run", fail)
    assert build.version()  # the package version


def test_version_is_dirty_only_for_uncommitted_code(monkeypatch, tmp_path):
    import subprocess

    def run(*args):
        subprocess.run(
            ["git", "-c", "user.name=t", "-c", "user.email=t@t", *args],
            cwd=tmp_path,
            check=True,
            capture_output=True,
        )

    files = ["prospect/x.py", "sql/1.sql", "pyproject.toml", "uv.lock"]
    files += ["config/a.yaml", "docs/a.md", "export/a.json"]
    for f in files:
        (tmp_path / f).parent.mkdir(exist_ok=True)
        (tmp_path / f).write_text("1\n")
    run("init", "-q")
    run("add", ".")
    run("commit", "-q", "-m", "init")
    run("tag", "v1")
    monkeypatch.setattr(build, "ROOT", tmp_path)
    assert build.version() == "v1"
    for f in ("config/a.yaml", "docs/a.md", "export/a.json"):
        (tmp_path / f).write_text("2\n")
    (tmp_path / "prospect" / "new.py").write_text("untracked\n")
    assert build.version() == "v1", "config, docs, export or untracked files count"
    for f in files[:4]:
        (tmp_path / f).write_text("2\n")
        assert build.version() == "v1-dirty", f"an edit to {f} should count"
        run("checkout", "--", f)


FACTORS = [(0.95, 0.92, 0.0), (0.6, 0.75, 0.05)]


@pytest.mark.parametrize("exports", [False, True])
@pytest.mark.parametrize("real, perf, overlap", FACTORS)
def test_export_matches_the_model_with_changed_factors(exports, real, perf, overlap):
    from prospect.model.report import with_factors

    base = copy.deepcopy(CFG)
    base["connected_solutions"]["site_exports"]["value"] = exports
    m = build.manifest(base, [SITE])
    _, site = exported(base)
    rescored = score.score_site(
        SITE, BUILDINGS, with_factors(base, real, perf, overlap)
    )
    st = recompute.defaults(m)
    st.update(realization_factor=real, performance_factor=perf, overlap_factor=overlap)
    # The rounding bound grows with what each rounded kW of peak is worth
    # (performance times one minus overlap), so scale the default tolerance.
    cs = CFG["connected_solutions"]
    worth = perf * (1 - overlap)
    default = cs["performance_factor"]["value"] * (1 - cs["overlap_factor"]["value"])
    tol = VALUE_TOL * max(1.0, worth / default)
    for r in rescored:
        st["connected_solutions"] = r["scenario"] == "with_connected_solutions"
        x = recompute.value_draws(site, m, st)
        assert x["value"] == pytest.approx(r["draws"]["value_per_block"], abs=tol)
