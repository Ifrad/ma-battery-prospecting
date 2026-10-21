"""The figures README.md and docs/BRIEF.md quote still match the docs, config
and export they come from. Each check builds the phrase the page should
contain from its source; when a source changes, the failure names the page,
the phrase and the source, so the page can be updated by hand."""

import json
import re
from pathlib import Path

import pytest

from prospect.priors import config

ROOT = Path(__file__).resolve().parents[1]
README = (ROOT / "README.md").read_text()
# Line breaks in the README do not matter: compare with whitespace collapsed.
FLAT = " ".join(README.split())
BRIEF = (ROOT / "docs" / "BRIEF.md").read_text()
BRIEF_FLAT = " ".join(BRIEF.split())
DOCS = ROOT / "docs"
CFG = config.load()


def doc(name: str) -> str:
    return (DOCS / name).read_text()


def find(pattern: str, text: str, source: str) -> re.Match:
    m = re.search(pattern, text)
    assert m, f"{source} no longer has the line the figure test reads ({pattern!r})"
    return m


def money(x: float) -> str:
    return f"${x:,.0f}"


def span(f: dict) -> str:
    """A factor as the README writes it: value, range low to high."""
    return f"{f['value']}, range {f['range']['low']} to {f['range']['high']}"


def rates(utility: str) -> dict:
    return {
        s["name"]: s["demand_charge_per_kw_month"]
        for s in CFG["rates"]["utilities"][utility]["schedules"]
    }


def funnel_phrases() -> list[tuple[str, str]]:
    f = doc("FUNNEL.md")
    candidates = find(
        r"\| Candidate sites \| [\d,]+ \| [\d,]+ \| ([\d,]+) \|", f, "FUNNEL"
    )
    municipal = find(r"([\d,]+) sites served by municipal light plants", f, "FUNNEL")
    s = doc("SCORES.md")
    ms = find(r"\| Metro South \| \d+ \| \d+ \| (\d+) \|", s, "SCORES")
    w = find(r"\| Worcester \| \d+ \| \d+ \| (\d+) \|", s, "SCORES")
    both = find(r"\| Both \| (\d+) \| (\d+) \| (\d+) \| (\d+) \| (\d+) \|", s, "SCORES")
    t1, t2, scored, passing, no_profile = both.groups()
    src = "docs/FUNNEL.md and docs/SCORES.md"
    return [
        (f"{candidates[1]} candidate sites", src),
        (f"drops {municipal[1]} sites\n     served by municipal light plants", src),
        (f"{scored} scored sites, {ms[1]} in Metro South and {w[1]} in Worcester", src),
        (f"{passing} pass 200 kW", src),
        (f"{t1} are tier 1 and {t2} tier 2", src),
        (f"those {no_profile} scored sites are flagged no open profile", src),
    ]


def validation_phrases() -> list[tuple[str, str]]:
    v = doc("VALIDATION.md")
    e = find(
        r"on ([\d,]+) pilot buildings the model ranks with Spearman ([\d.]+) against"
        r" ([\d.]+) for size-only",
        v,
        "VALIDATION",
    )
    band = find(r"energy band holds the measured value (\d+)%", v, "VALIDATION")
    stress = find(
        r"Metro South keeps (\d+) of its top 15 and Worcester (\d+)\.", v, "VALIDATION"
    )
    not_closer = find(r"Where it is not: ([a-z_, ]+)\.", v, "VALIDATION")
    factory = find(
        r"summer 3 to 8 pm mean over peak \(only \d+% inside, median ([\d.]+)",
        v,
        "VALIDATION",
    )
    hosp = find(
        r"of (\d+) scored hospitals, (\w+) fail .*?; (\d+) sit outside", v, "VALIDATION"
    )
    find(r"Worcester's ranking is a tier, not an order", v, "VALIDATION")
    src = "docs/VALIDATION.md"
    return [
        (
            f"on {e[1]} pilot LBER buildings the model\n  ranks with Spearman {e[2]}"
            f" against {e[3]} for size-only",
            src,
        ),
        (f"is no closer for {not_closer[1]}", src),
        (f"value {band[1]}% of the time", src),
        (f"Metro South keeps {stress[1]} of its top 15 and Worcester {stress[2]}", src),
        (f"(median {factory[1]})", src),
        (f"of {hosp[1]} scored hospitals {hosp[2]} fails", src),
        (f"{hosp[3]} tier 1 hospitals sit outside", src),
    ]


def share_phrases() -> list[tuple[str, str]]:
    s = doc("SCORES.md")
    share = find(r"\| ConnectedSolutions \| \$[\d,]+ \| (\d+)% \|", s, "SCORES")
    top = s.split("### Metro South", 1)[1].split("### Worcester", 1)[0]
    towns = [r.split(" | ")[1] for r in top.splitlines() if r.startswith("| ")][1:11]
    assert set(towns) <= {"Canton", "Sharon"}, (
        f"docs/SCORES.md: Metro South's top 10 are no longer all in Canton and"
        f" Sharon ({towns}); update the README's rate area paragraph"
    )
    return [
        (
            f"ConnectedSolutions is {share[1]} percent of P50 value per block",
            "docs/SCORES.md",
        )
    ]


def config_phrases() -> list[tuple[str, str]]:
    ng = rates("National Grid (Massachusetts Electric)")
    ev = rates("Eversource Energy (NSTAR Electric)")
    cs = CFG["connected_solutions"]
    perf, over = cs["performance_factor"], cs["overlap_factor"]
    real = CFG["profiles"]["realization_factor"]
    block = CFG["battery"]["block"]
    band = CFG["model"]["rate_band_kw"]
    usd = cs["daily_dispatch_usd_per_kw_season"]["value"]
    cap = cs["export_cap_share_of_site_peak"]["value"]
    full = block["power_kw"] * perf["value"] * (1 - over["value"]) * usd
    src = "config/"
    return [
        (f"${ng['G-2']:.2f}, billed on the all-hours monthly peak", src),
        (f"${ng['G-3']:.2f}, billed on the peak in the weekday", src),
        (f"| ${ev['G-2']:.2f} |", src),
        (f"| ${ev['G-3']:.2f} |", src),
        (f"between {band['g2_below']} and {band['g3_above']} kW", src),
        (f"{CFG['funnel']['min_kwh_per_month']['value']:,} kWh a month", src),
        (f"Sites at {min(CFG['funnel']['report_peak_kw']['value'])} kW or more", src),
        (f"the {CFG['funnel']['min_peak_kw']['value']} kW line", src),
        (f"{block['power_kw']} kW and {block['energy_kwh']} kWh", src),
        (f"One block per {CFG['model']['blocks']['peak_kw_per_block']:,} kW", src),
        (f"drawn {CFG['model']['draws']['value']:,} times", src),
        (f"Rate: ${usd} per kW per summer", src),
        (f"Performance factor: {span(perf)}", src),
        (f"Overlap factor: {span(over)}", src),
        (f"Realization factor, {span(real).replace(', range', ' (range')})", src),
        (f"{cap * 100:.0f} percent of its peak", src),
        (f"x (1 - {over['value']}) x ${usd} = {money(full)}", src),
    ]


def example_phrases() -> list[tuple[str, str]]:
    sites = json.loads((ROOT / "export" / "worcester.geojson").read_text())["features"]
    [s] = [
        f["properties"]
        for f in sites
        if f["properties"]["owner"] == "WORCESTER HAHNEMANN HOSPITAL"
    ]
    cs = s["scenarios"]["with_connected_solutions"]
    v = cs["value_per_block"]
    st = cs["streams"]
    lber = sum(b["grid_kwh"] or 0 for b in s["buildings"])
    src = "export/worcester.geojson (Worcester Hahnemann Hospital)"
    return [
        (f"reports {lber:,} kWh in LBER", src),
        (f"is {money(st['demand_savings']['p50'])}.", src),
        (f"at $200 is {money(st['connected_solutions']['p50'])}.", src),
        (
            f"{money(st['demand_savings']['p50'])} +"
            f" {money(st['connected_solutions']['p50'])} = {money(v['p50'])}",
            src,
        ),
        (f"${v['p10']:,} to\n  ${v['p90']:,}", src),
    ]


PHRASES = (
    funnel_phrases()
    + validation_phrases()
    + share_phrases()
    + config_phrases()
    + example_phrases()
)


@pytest.mark.parametrize("phrase, source", PHRASES, ids=[p for p, _ in PHRASES])
def test_readme_quotes_current_figures(phrase, source):
    assert " ".join(phrase.split()) in FLAT, (
        f"README.md no longer matches {source}: expected the text {phrase!r}."
        " Update the README figure from the source."
    )


def test_readme_links_and_images_exist():
    for path in re.findall(r"\]\((docs/[^)]+)\)", README):
        assert (ROOT / path).exists(), f"README links to missing {path}"
    for path in re.findall(
        r"(?<![\w/])((?:docs|data)/[\w./-]+\.(?:md|csv|png))", README
    ):
        assert (ROOT / path).exists(), f"README names missing {path}"
    for img in (DOCS / "img").glob("*.png"):
        assert img.stat().st_size <= 300_000, f"{img.name} is over 300 KB"


def test_readme_follows_the_writing_rules():
    assert "—" not in README, "README has an em dash"
    assert "**" not in README, "README uses bold"
    assert re.search(r"\baccurate\b", README.replace("not accurate", "")) is None


def hahnemann() -> dict:
    sites = json.loads((ROOT / "export" / "worcester.geojson").read_text())["features"]
    [s] = [
        f["properties"]
        for f in sites
        if f["properties"]["owner"] == "WORCESTER HAHNEMANN HOSPITAL"
    ]
    return s


def brief_phrases() -> list[tuple[str, str]]:
    import numpy as np

    f, s, v = doc("FUNNEL.md"), doc("SCORES.md"), doc("VALIDATION.md")
    candidates = find(
        r"\| Candidate sites \| [\d,]+ \| [\d,]+ \| ([\d,]+) \|", f, "FUNNEL"
    )
    ms = find(r"\| Metro South \| \d+ \| \d+ \| (\d+) \|", s, "SCORES")
    w = find(r"\| Worcester \| \d+ \| \d+ \| (\d+) \|", s, "SCORES")
    both = find(r"\| Both \| \d+ \| \d+ \| (\d+) \| \d+ \| (\d+) \|", s, "SCORES")
    with_cs = find(
        r"\| Plus ConnectedSolutions \| \$[\d,]+ \| (\$[\d,]+) \|", s, "SCORES"
    )
    demand = find(r"\| Demand savings only \| \$[\d,]+ \| (\$[\d,]+) \|", s, "SCORES")
    share = find(r"\| ConnectedSolutions \| \$[\d,]+ \| (\d+)% \|", s, "SCORES")
    wtop = s.split("### Worcester", 1)[1]
    wvals = [r.split(" | ")[5] for r in wtop.splitlines() if r.startswith("| ")][1:16]
    e = find(r"Spearman ([\d.]+) against ([\d.]+) for size-only", v, "VALIDATION")
    stress = find(
        r"Metro South keeps (\d+) of its top 15 and Worcester (\d+)\.", v, "VALIDATION"
    )
    not_closer = find(r"Where it is not: ([a-z_, ]+)\.", v, "VALIDATION")
    hrow = find(
        r"\| WORCESTER HAHNEMANN HOSPITAL \|.*\| ([\d.]+) \| ([\d.]+) \| outside",
        v,
        "VALIDATION",
    )
    n_ref = find(
        r"next to the (\d+) Massachusetts hospitals in the ComStock", v, "VALIDATION"
    )

    ng = rates("National Grid (Massachusetts Electric)")
    ev = rates("Eversource Energy (NSTAR Electric)")
    cs = CFG["connected_solutions"]
    perf, over = cs["performance_factor"]["value"], cs["overlap_factor"]["value"]
    usd = cs["daily_dispatch_usd_per_kw_season"]["value"]
    real = CFG["profiles"]["realization_factor"]["value"]
    power = CFG["battery"]["block"]["power_kw"]
    full_cs = power * perf * (1 - over) * usd
    ceiling = 12 * power * real * ng["G-3"] + full_cs

    site = hahnemann()
    x = site["scenarios"]["with_connected_solutions"]
    val, st = x["value_per_block"], x["streams"]
    dem, grid = st["demand_savings"]["p50"], st["connected_solutions"]["p50"]
    kwm = float(np.percentile(site["draws"]["kwm_g3"], 50))
    peak = float(np.percentile(site["draws"]["peak_kw"], 50))
    ratio = site["event_window"]["mean_over_peak"]
    lber = sum(b["grid_kwh"] or 0 for b in site["buildings"])
    src_docs = "docs/FUNNEL.md, docs/SCORES.md and docs/VALIDATION.md"
    src_ex = "export/worcester.geojson (Worcester Hahnemann Hospital) and config/"
    return [
        (
            f"{both[1]} of {candidates[1]} candidate sites are scored: {ms[1]} in"
            f" Metro South, {w[1]} in Worcester",
            src_docs,
        ),
        (
            f"{with_cs[1]} a year with ConnectedSolutions, {demand[1]} from demand"
            " savings alone",
            src_docs,
        ),
        (f"ConnectedSolutions is {share[1]} percent of P50 value", src_docs),
        (
            f"(${ev['G-2']:.2f} per kW-month, against National Grid's"
            f" ${ng['G-2']:.2f})",
            "config/",
        ),
        (
            f"its top 15 run from {wvals[-1]} to {wvals[0]}, close to the one-block"
            f" ceiling of {money(ceiling)}",
            "docs/SCORES.md and config/",
        ),
        (f"{site['building_count']} buildings, {site['area_sqft']:,} sq ft", src_ex),
        (f"reports {lber:,} kWh in LBER", src_ex),
        (f"G-3 in every draw, ${ng['G-3']:.2f} per kW-month", src_ex),
        (f"{kwm:,.2f} kW-months, after the realization factor {real}", src_ex),
        (
            f"{kwm:,.2f} x ${ng['G-3']:.2f} = {money(st['demand_savings']['p50'])}",
            src_ex,
        ),
        (
            f"min({power} x {perf}, {ratio} x {peak:,.0f} kW peak) = {power * perf:g},"
            f" x (1 - {over}) = {power * perf * (1 - over):g} kW",
            src_ex,
        ),
        (
            f"{power * perf * (1 - over):g} kW x ${usd} ="
            f" {money(st['connected_solutions']['p50'])}",
            src_ex,
        ),
        (
            f"{money(dem)} + {money(grid)} = {money(val['p50'])},"
            f" band ${val['p10']:,} to ${val['p90']:,}",
            src_ex,
        ),
        (f"{site['blocks']:.1f} expected blocks", src_ex),
        (f"ranks {site['size_rank']}th in Worcester", src_ex),
        (f"({hrow[1]} kWh, {hrow[2]} W) are above all {n_ref[1]} ComStock", src_docs),
        (
            f"Metro South keeps {stress[1]} of its top 15 and Worcester {stress[2]}",
            src_docs,
        ),
        (f"Spearman {e[1]} against {e[2]}", src_docs),
        (f"no better for {not_closer[1]}", src_docs),
        (f"(performance factor {perf}, overlap factor {over}, no export)", "config/"),
        (f"{both[2]} scored sites (factories", src_docs),
    ]


BRIEF_PHRASES = brief_phrases()


@pytest.mark.parametrize(
    "phrase, source", BRIEF_PHRASES, ids=[p for p, _ in BRIEF_PHRASES]
)
def test_brief_quotes_current_figures(phrase, source):
    assert " ".join(phrase.split()) in BRIEF_FLAT, (
        f"docs/BRIEF.md no longer matches {source}: expected the text {phrase!r}."
        " Update the brief figure from the source."
    )


def test_brief_follows_the_writing_rules():
    assert "\u2014" not in BRIEF and "**" not in BRIEF
    assert "not affiliated with Powertown" in BRIEF
    assert "github.com/thutch17/powertown-hackathon" in BRIEF and "prior work" in BRIEF
    assert "hackathon entry" not in BRIEF
    assert re.search(r"\baccurate\b", BRIEF) is None
    assert len(BRIEF.split()) <= 800, "docs/BRIEF.md is meant to fit on one page"
