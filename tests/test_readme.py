"""The figures README.md quotes still match the docs, config and export they
come from. Each check builds the phrase the README should contain from its
source; when a source changes, the failure names the phrase and the source,
so the README can be updated by hand."""

import json
import re
from pathlib import Path

import pytest

from prospect.priors import config

ROOT = Path(__file__).resolve().parents[1]
README = (ROOT / "README.md").read_text()
# Line breaks in the README do not matter: compare with whitespace collapsed.
FLAT = " ".join(README.split())
DOCS = ROOT / "docs"
CFG = config.load()


def doc(name: str) -> str:
    return (DOCS / name).read_text()


def find(pattern: str, text: str, source: str) -> re.Match:
    m = re.search(pattern, text)
    assert m, f"{source} no longer has the line the README test reads ({pattern!r})"
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
    towns = [r.split(" | ")[1] for r in top.splitlines() if r.startswith("| ")][2:12]
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
