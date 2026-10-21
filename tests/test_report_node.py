"""Runs the report's JavaScript parity test (tests/js/) under node --test.

Writes the Python reference results to a file the Node test reads. Skips when
node is missing locally; fails instead when PROSPECT_REQUIRE_NODE is set, as
in CI."""

import json
import os
import shutil
import subprocess

import pytest

from prospect.export import build, recompute
from prospect.report.build import load_export

ROOT = build.ROOT
# Changed factors, as tests/js/compute.test.js sets them.
FACTOR_CASES = {
    "factors_high": {
        "realization_factor": 0.95,
        "performance_factor": 0.92,
        "overlap_factor": 0.0,
    },
    "factors_low": {
        "realization_factor": 0.6,
        "performance_factor": 0.75,
        "overlap_factor": 0.05,
    },
}


def expectations() -> dict:
    data = load_export()
    m = data["manifest"]
    sites = [s for r in data["regions"].values() for s in r]
    cases = {}
    for name in ("defaults", "cs_off", "rate_up", "factors_high", "factors_low"):
        st = recompute.defaults(m)
        if name in FACTOR_CASES:
            st.update(FACTOR_CASES[name])
        if name == "cs_off":
            st["connected_solutions"] = False
        if name == "rate_up":
            st["rates"] = {
                u: {k: v * 1.25 for k, v in sched.items()}
                for u, sched in st["rates"].items()
            }
        cases[name] = {}
        for s in sites:
            r = recompute.site_summary(s, m, st)
            cases[name][s["site_id"]] = {
                "value_per_block": r["value_per_block"],
                "total": r["total"],
                "blocks": r["blocks"],
                "cs_share": r["streams"]["connected_solutions"]["share"],
            }
    st = recompute.defaults(m)
    summaries = [recompute.site_summary(s, m, st) for s in sites]
    demand = sum(x["streams"]["demand_savings"]["p50"] for x in summaries)
    grid = sum(x["streams"]["connected_solutions"]["p50"] for x in summaries)
    return {"cases": cases, "cs_share": grid / (demand + grid)}


def test_report_javascript_matches_python(tmp_path):
    node = shutil.which("node")
    if node is None:
        if os.environ.get("PROSPECT_REQUIRE_NODE"):
            pytest.fail("node is required (PROSPECT_REQUIRE_NODE is set) but not found")
        pytest.skip("node not installed; the report's JavaScript parity test needs it")
    expected = tmp_path / "expected.json"
    expected.write_text(json.dumps(expectations()))
    proc = subprocess.run(
        [node, "--test", str(ROOT / "tests" / "js" / "compute.test.js")],
        cwd=ROOT,
        env={**os.environ, "PARITY_EXPECTED": str(expected)},
        capture_output=True,
        text=True,
        timeout=600,
    )
    assert proc.returncode == 0, proc.stdout[-4000:] + proc.stderr[-2000:]


def test_missing_node_skips_locally_and_fails_when_required(monkeypatch, tmp_path):
    monkeypatch.setattr(shutil, "which", lambda name: None)
    monkeypatch.delenv("PROSPECT_REQUIRE_NODE", raising=False)
    with pytest.raises(pytest.skip.Exception):
        test_report_javascript_matches_python(tmp_path)
    monkeypatch.setenv("PROSPECT_REQUIRE_NODE", "1")
    with pytest.raises(pytest.fail.Exception, match="node is required"):
        test_report_javascript_matches_python(tmp_path)
