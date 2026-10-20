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
        assert report.reprice(stored(r), CFG, 0.8, 0.61, 0.13) == pytest.approx(
            r["value_per_block"]["p50"], rel=1e-5
        )


def test_lower_realization_or_more_overlap_lowers_repriced_value():
    r = stored(score.score_site(SITE, BUILDINGS, CFG)[1])
    base = report.reprice(r, CFG, 0.8, 0.61, 0.13)
    assert report.reprice(r, CFG, 0.6, 0.61, 0.13) < base
    assert report.reprice(r, CFG, 0.8, 0.61, 0.0) > base


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
