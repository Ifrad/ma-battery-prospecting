"""Write report.html from the export.

Usage: python -m prospect.report.build (make report)

One self-contained file: the export data, CSS and JavaScript are inline, with
no external scripts, fonts or images, so it opens by double click with no
network, backend or install. report.html is built, never committed (it is
gitignored); the owner attaches it to the GitHub release.
"""

import html
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
EXPORT = ROOT / "export"
OUT = ROOT / "report.html"
REGIONS = ("metro_south", "worcester")


def load_export(export: Path = EXPORT) -> dict:
    """The manifest and each region's sites, as the page embeds them."""
    regions = {}
    for r in REGIONS:
        gj = json.loads((export / f"{r}.geojson").read_text())
        regions[r] = [
            {
                **f["properties"],
                "lon": f["geometry"]["coordinates"][0],
                "lat": f["geometry"]["coordinates"][1],
            }
            for f in gj["features"]
        ]
    return {
        "manifest": json.loads((export / "manifest.json").read_text()),
        "regions": regions,
    }


DOCS = ROOT / "docs"
PATTERNS = {
    "spearman_model": r"model ranks with Spearman ([\d.]+) against",
    "spearman_size": r"model ranks with Spearman [\d.]+ against ([\d.]+) for size-only",
    "not_closer": r"Where it is not: ([^.]+)\.",
    "band_hit": r"energy band holds the measured value (\d+)% of the time",
    "worcester_tier": r"(Worcester's ranking is a tier, not an order)",
    "stress_ms": r"Metro South keeps (\d+) of its top 15",
    "stress_w": r"of its top 15 and Worcester (\d+)",
    "factory_event_median": (
        r"Light industrial against the .*?"
        r"\| Summer 3 to 8 pm mean over peak \| \d+ \| [\d.]+ / ([\d.]+) /"
    ),
}


def findings(validation: str) -> dict:
    """Figures the limits section quotes, read from docs/VALIDATION.md so the
    report never carries a stale number. Fails if one is missing."""
    import re

    out = {}
    for key, pattern in PATTERNS.items():
        m = re.search(pattern, validation, re.S)
        if not m:
            raise SystemExit(f"docs/VALIDATION.md has no {key}; run make validate")
        out[key] = m.group(1)
    return out


def export_facts(data: dict) -> dict:
    """Figures the limits section computes from the export itself."""
    ms = sorted(data["regions"]["metro_south"], key=lambda s: s["model_rank"])[:10]
    every = [s for r in data["regions"].values() for s in r]
    no_profile = [s for s in every if s["profile"] == "no open profile"]
    demand = sum(
        s["scenarios"]["with_connected_solutions"]["streams"]["demand_savings"]["p50"]
        for s in every
    )
    grid = sum(
        s["scenarios"]["with_connected_solutions"]["streams"]["connected_solutions"][
            "p50"
        ]
        for s in every
    )
    return {
        "ms_top10_unconfirmed": sum("rate_area_unconfirmed" in s["flags"] for s in ms),
        "ms_top10_towns": sorted({s["town"] for s in ms}),
        "no_profile_sites": len(no_profile),
        "sites": len(every),
        "model_factory_event": (
            no_profile[0]["event_window"]["mean_over_peak"] if no_profile else None
        ),
        "cs_share": grid / (demand + grid) if demand + grid else 0.0,
    }


def limits(data: dict, validation: str) -> str:
    """The assumptions and limits section, as HTML."""
    f, x = findings(validation), export_facts(data)
    e = html.escape
    ms = (
        f"all {x['ms_top10_unconfirmed']}"
        if x["ms_top10_unconfirmed"] == 10
        else f"{x['ms_top10_unconfirmed']}"
    )
    items = [
        "Value per block is simulated gross yearly revenue per battery block"
        " (demand savings plus ConnectedSolutions), before any host share. It is"
        " not profit and not accurate. Installed cost and the host share are not"
        " modeled: apply your own.",
        f"ConnectedSolutions is {x['cs_share']:.0%} of P50 value per block across"
        " the scored sites (computed from the export).",
        "Peak shape is unvalidated and was only stress-tested: with the simulated"
        f" peak cut share reduced, Metro South keeps {e(f['stress_ms'])} of its top"
        f" 15 and Worcester {e(f['stress_w'])}.",
        f"{e(f['worcester_tier'])}: its top sites trade places across the model's"
        " draws, so read its list as a group to approach, not a ranking.",
        f"In Metro South, {ms} of the top 10 are Eversource sites in"
        f" {e(' and '.join(x['ms_top10_towns']))} whose rate area is unconfirmed;"
        " they are priced at the Greater Boston rate.",
        f"{x['no_profile_sites']} of {x['sites']} scored sites (factories, laundries,"
        " food plants, cold storage, auto repair) have no open load profile, so"
        " their values come from wide simulated ranges.",
        "The model beats a size-only estimate of yearly electricity only modestly:"
        f" Spearman {e(f['spearman_model'])} against {e(f['spearman_size'])}, and"
        f" it is no closer for {e(f['not_closer'])}.",
        f"The 80 percent band on yearly electricity held the measured value"
        f" {e(f['band_hit'])}% of the time.",
        "EnerNOC meter data (CC BY-NC 3.0) was used only as a local out-of-sample"
        " test: it is not in this report or the repository, and no input was"
        " derived from it.",
        "Real factories in that data use more of their peak in the 3 to 8 pm"
        f" event window (median {e(f['factory_event_median'])}) than the model"
        f" assumes for sites without a profile ({x['model_factory_event']:.2f}),"
        " so factory ConnectedSolutions revenue is probably understated.",
        "Not modeled: space for battery cabinets, utility interconnection"
        " capacity, and whether the owner is willing.",
    ]
    rows = "".join(
        "<tr><td>"
        + e(p["file"])
        + ".yaml</td><td>"
        + e(p["path"])
        + "</td><td>"
        + e(str(p["value"]))
        + "</td><td>"
        + e(p["note"])
        + "</td></tr>"
        for p in data["manifest"]["placeholders"]
    )
    return (
        '<section id="limits"><h2>Assumptions and limits</h2><ul>'
        + "".join(f"<li>{i}</li>" for i in items)
        + '</ul><p class="muted">Sources: docs/VALIDATION.md, docs/SCORES.md and'
        " the export manifest.</p>"
        + f"<h2>Placeholders in use ({len(data['manifest']['placeholders'])})</h2>"
        + '<p class="muted">Values not read from a cited source, kept visible until'
        " something better replaces them (docs/ASSUMPTIONS.md).</p>"
        + '<div class="table-wrap"><table><thead><tr><th>File</th><th>Setting</th>'
        "<th>Value</th><th>Note</th></tr></thead><tbody>"
        + rows
        + "</tbody></table></div></section>"
    )


def embed(data: dict) -> str:
    """JSON safe inside a script element."""
    return json.dumps(data, separators=(",", ":")).replace("</", "<\\/")


def page(data: dict, validation: str | None = None) -> str:
    m = data["manifest"]
    if validation is None:
        validation = (DOCS / "VALIDATION.md").read_text()
    css = (HERE / "style.css").read_text()
    js = (HERE / "compute.js").read_text() + "\n" + (HERE / "app.js").read_text()
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Battery block value by site</title>
<link rel="icon" href="data:,">
<style>{css}</style>
</head>
<body>
<header>
<h1>Battery block value by site, Massachusetts pilot</h1>
<p class="muted">Value per block is simulated gross yearly revenue one battery
block could bring a site (demand savings plus ConnectedSolutions), before any
host share. It is not profit, not accurate and unvalidated. Cost is not
modeled: the reader applies their own installed cost and host share.
Export {html.escape(m["version"])}, generated {html.escape(m["generated_at"])}.</p>
</header>
<main>
<div class="controls">
<div id="regions"></div><span id="count" class="muted"></span>
</div>
<p id="cs-note" class="note"></p>
<section id="settings"></section>
<section id="detail" class="detail" hidden></section>
<div class="table-wrap"><table id="table"></table></div>
{limits(data, validation)}
</main>
<script id="export-data" type="application/json">{embed(data)}</script>
<script>{js}</script>
</body>
</html>
"""


def write(export: Path = EXPORT, out: Path = OUT) -> Path:
    out.write_text(page(load_export(export)))
    return out


def main() -> int:
    out = write()
    print(f"wrote {out.relative_to(ROOT)}: {out.stat().st_size / 1e6:.1f} MB")
    return 0


if __name__ == "__main__":
    sys.exit(main())
