import numpy as np
import pytest

from prospect.model import report, run, score
from prospect.priors import config

CFG = config.load()
NG = "National Grid (Massachusetts Electric)"
SITE = {
    "site_id": "S1",
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
        "building_id": 1,
        "segment": "warehouse",
        "electricity_source": "estimated",
        "grid_kwh": None,
        "area_sqft": 400000.0,
        "lber_confidence": None,
        "area_source": "assessor",
    }
]


def stored(r):
    """A site_scores row as the database returns it."""
    names = [c.strip() for c in run.COLUMNS.split(",")]
    return dict(zip(names, run.row(1, SITE, r), strict=True))


def test_stored_physical_units_reprice_to_the_scored_value():
    for r in score.score_site(SITE, BUILDINGS, CFG):
        repriced = run.value_draws(stored(r), CFG)
        assert repriced == pytest.approx(r["draws"]["value_per_block"], rel=1e-5)


def test_sensitivity_moves_the_right_way():
    scope = [(SITE, BUILDINGS)]
    base = report.median_p50(scope, CFG)
    assert report.median_p50(scope, report.with_factors(CFG, 0.6, 0.61, 0.13)) < base
    assert report.median_p50(scope, report.with_factors(CFG, 0.8, 0.92, 0.13)) >= base
    assert report.median_p50(scope, report.with_factors(CFG, 0.8, 0.61, 0.0)) > base


def test_scores_are_stored_per_site_and_scenario(db):
    rid = db.execute(
        "INSERT INTO score_runs (config_hash, draws) VALUES ('t', 1000)"
        " RETURNING run_id"
    ).fetchone()[0]
    with db.cursor().copy(f"COPY site_scores ({run.COLUMNS}) FROM STDIN") as cp:
        for r in score.score_site(SITE, BUILDINGS, CFG):
            cp.write_row(run.row(rid, SITE, r))
    got = db.execute(
        "SELECT scenario, cardinality(kwm_g2), value_p50 > 0 FROM site_scores"
        " ORDER BY scenario"
    ).fetchall()
    assert got == [
        ("demand_savings", 1000, True),
        ("with_connected_solutions", 1000, True),
    ]
    rows = list(run.confidence_rows(db, CFG, 180_000, 0, False))
    assert [s for _, s, _ in rows] == ["demand_savings", "with_connected_solutions"]
    assert all(0 <= c <= 1 for _, _, c in rows)
    assert np.isfinite(rows[0][2])
