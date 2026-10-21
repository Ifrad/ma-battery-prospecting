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


def embed(data: dict) -> str:
    """JSON safe inside a script element."""
    return json.dumps(data, separators=(",", ":")).replace("</", "<\\/")


def page(data: dict) -> str:
    m = data["manifest"]
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
<section id="detail" class="detail" hidden></section>
<div class="table-wrap"><table id="table"></table></div>
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
