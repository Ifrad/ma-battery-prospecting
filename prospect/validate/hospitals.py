"""Hospital sanity check: the scored hospitals' modeled energy and peak next
to the Massachusetts hospitals in the ComStock sample (data/comstock/, from
make comstock and make simulate).

A sanity check, not validation. The model draws hospital load factors from
those same ComStock hospitals, so the load factor comparison is circular;
tier 1 kWh is LBER's measured electricity, an input, so comparing it with
LBER is circular too. The hospital kWh prior comes from LBER pilot
hospitals, not ComStock, so kWh and peak per sq ft are an independent
comparison, against only a handful of simulated buildings.
"""

import csv
import statistics
from pathlib import Path

import numpy as np

from prospect.model import draws, run

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data" / "comstock"
TYPE = "Hospital"
OWNERS = """
    SELECT st.site_id, st.owner, initcap(u.attrs ->> 'TOWN') AS town
    FROM sites st
    JOIN raw_utility_territories u ON (u.attrs ->> 'TOWN_ID')::integer = st.town_id
    WHERE st.site_id = ANY(%s)
"""


def comstock_hospitals(data: Path = DATA) -> list[dict] | None:
    """Per ComStock hospital: kWh per sq ft, median monthly load factor and
    median monthly peak in W per sq ft. None when the files are missing."""
    if not (data / "simulation.csv").exists():
        return None
    with (data / "sample.csv").open() as f:
        sqft = {
            r["bldg_id"]: float(r["sqft"])
            for r in csv.DictReader(f)
            if r["building_type"] == TYPE
        }
    months: dict[str, list[dict]] = {}
    with (data / "simulation.csv").open() as f:
        for r in csv.DictReader(f):
            if r["bldg_id"] in sqft:
                months.setdefault(r["bldg_id"], []).append(r)
    out = []
    for b, rows in sorted(months.items()):
        area = sqft[b]
        out.append(
            {
                "bldg_id": b,
                "kwh_sqft": float(rows[0]["annual_kwh"]) / area,
                "load_factor": statistics.median(
                    float(r["month_mean_kw"]) / float(r["month_peak_kw"]) for r in rows
                ),
                "w_sqft": statistics.median(float(r["month_peak_kw"]) for r in rows)
                * 1000
                / area,
            }
        )
    return out


def reference(buildings: list[dict]) -> dict:
    """Min, median and max of each measure across the ComStock hospitals."""
    return {
        k: {
            "min": min(b[k] for b in buildings),
            "median": statistics.median(b[k] for b in buildings),
            "max": max(b[k] for b in buildings),
        }
        for k in ("kwh_sqft", "load_factor", "w_sqft")
    }


def site_row(site: dict, buildings: list[dict], cfg: dict) -> dict:
    """The model's own draws for one scored hospital, summarized."""
    d = draws.site_draws(site, buildings, cfg)
    area = sum(b["area_sqft"] for b in buildings)
    kwh = float(np.median(d["annual_kwh"]))
    peak = float(np.median(d["peak_kw"]))
    measured = [b for b in buildings if b["electricity_source"] == "measured"]
    return {
        "site_id": site["site_id"],
        "region": site["region"],
        "tier": site["tier"],
        "area_sqft": area,
        "kwh": kwh,
        "lber_kwh": sum(b["grid_kwh"] or 0 for b in measured) if measured else None,
        "measured_buildings": len(measured),
        "buildings": len(buildings),
        "average_kw": kwh / draws.HOURS,
        "peak_kw": peak,
        "load_factor": float(np.median(d["load_factor"])),
        "kwh_sqft": kwh / area,
        "w_sqft": peak * 1000 / area,
        "peak_below_average_draws": int(
            np.sum(d["peak_kw"] < d["annual_kwh"] / draws.HOURS)
        ),
    }


def check(row: dict, ref: dict) -> dict:
    """Fails: a load factor outside every ComStock hospital, or a peak below
    the implied average in any draw. Outside: kWh or W per sq ft beyond the
    ComStock hospitals, a flag to look at, not a failure."""
    inside = {
        k: ref[k]["min"] <= row[k] <= ref[k]["max"]
        for k in ("kwh_sqft", "load_factor", "w_sqft")
    }
    fails = []
    if not inside["load_factor"]:
        fails.append("load factor outside the ComStock hospitals")
    if row["peak_below_average_draws"]:
        fails.append(f"peak below average in {row['peak_below_average_draws']} draws")
    outside = [
        label
        for k, label in (("kwh_sqft", "kWh per sq ft"), ("w_sqft", "peak W per sq ft"))
        if not inside[k]
    ]
    return {"fails": fails, "outside": outside}


def results(conn, cfg: dict) -> dict | None:
    ref_buildings = comstock_hospitals()
    if ref_buildings is None:
        return None
    ref = reference(ref_buildings)
    scope = [(s, b) for s, b in run.load_scope(conn, cfg) if s["segment"] == "hospital"]
    names = {
        r[0]: (r[1], r[2])
        for r in conn.execute(OWNERS, ([s["site_id"] for s, _ in scope],)).fetchall()
    }
    rows = []
    for site, buildings in scope:
        row = site_row(site, buildings, cfg)
        row["owner"], row["town"] = names[site["site_id"]]
        row.update(check(row, ref))
        rows.append(row)
    rows.sort(key=lambda r: (r["region"], -r["kwh"]))
    return {"reference": ref, "comstock_buildings": len(ref_buildings), "sites": rows}


def summary_line(r: dict | None) -> list[str]:
    if r is None:
        return ["- Hospital sanity check not run on this machine (make simulate)."]
    failed = [x for x in r["sites"] if x["fails"]]
    outside = [x for x in r["sites"] if x["outside"]]
    tiers = sorted({x["tier"] for x in outside})
    return [
        f"- Hospital sanity check, not accuracy: of {len(r['sites'])} scored"
        f" hospitals, {len(failed) or 'none'} fail (load factor inside the"
        f" {r['comstock_buildings']} ComStock Massachusetts hospitals' range and"
        " peak at or above average in every draw)"
        + (
            f"; {len(outside)} sit outside their kWh or peak per sq ft range"
            f" (tier {' and '.join(map(str, tiers))})."
            if outside
            else "."
        )
    ]


def section(r: dict | None) -> list[str]:
    head = ["## Hospital sanity check", ""]
    if r is None:
        return head + [
            "Not run on this machine: it needs data/comstock (make simulate)."
        ]
    ref, n = r["reference"], r["comstock_buildings"]

    def band(k, fmt):
        x = ref[k]
        return f"{x['min']:{fmt}} to {x['max']:{fmt}} (median {x['median']:{fmt}})"

    lines = [
        *head,
        "A sanity check, not validation and not accuracy. Each scored hospital's"
        " modeled yearly electricity, implied average kW (yearly kWh over 8,760"
        " hours), modeled monthly peak kW and monthly load factor (average over"
        " peak), each the median of the model's own draws, next to the"
        f" {n} Massachusetts hospitals in the ComStock sample (2018 weather).",
        "",
        "- Load factor: circular. The model draws hospital load factors from"
        " these same ComStock hospitals, so this only checks that no draw left"
        " their range.",
        "- Peak and average: the model divides yearly kWh by the load factor,"
        " capped at 1, so a peak below the implied average should never happen;"
        " the check confirms it in every draw.",
        "- Tier 1 yearly kWh: circular. A measured building's kWh is LBER's"
        " reported electricity, an input to the model, so the LBER column is"
        " shown for reference, not as validation.",
        "- kWh and peak per sq ft: independent of ComStock, since the hospital"
        " kWh prior comes from LBER pilot hospitals (config/intensity.yaml), but"
        f" against only {n} simulated buildings, so outside their range is a"
        " flag to look at, not a failure.",
        "",
        f"ComStock hospitals: kWh per sq ft {band('kwh_sqft', '.1f')}, load"
        f" factor {band('load_factor', '.2f')}, peak W per sq ft"
        f" {band('w_sqft', '.1f')}.",
        "",
        "| Region | Owner | Town | Tier | Buildings (measured) | Floor area sq ft"
        " | Modeled kWh | LBER measured kWh | Average kW | Peak kW | Load factor"
        " | kWh per sq ft | Peak W per sq ft | Result |",
        "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for x in r["sites"]:
        result = "; ".join(
            [*x["fails"], *(f"outside ComStock {o}" for o in x["outside"])]
        )
        lber = f"{x['lber_kwh']:,.0f} (circular)" if x["lber_kwh"] is not None else ""
        lines.append(
            f"| {x['region'].replace('_', ' ').title()} | {x['owner']} | {x['town']}"
            f" | {x['tier']} | {x['buildings']} ({x['measured_buildings']})"
            f" | {x['area_sqft']:,.0f} | {x['kwh']:,.0f} | {lber}"
            f" | {x['average_kw']:,.0f} | {x['peak_kw']:,.0f}"
            f" | {x['load_factor']:.2f} | {x['kwh_sqft']:.1f} | {x['w_sqft']:.1f}"
            f" | {result or 'ok'} |"
        )
    failed = [x for x in r["sites"] if x["fails"]]
    outside = [x for x in r["sites"] if x["outside"]]
    lines += [
        "",
        "Failed: "
        + (
            "; ".join(f"{x['owner']} ({', '.join(x['fails'])})" for x in failed)
            if failed
            else "none."
        ),
        "",
        "Outside the ComStock range: "
        + (
            "; ".join(
                f"{x['owner']}, tier {x['tier']}, {x['kwh_sqft']:.1f} kWh and"
                f" {x['w_sqft']:.1f} W per sq ft"
                for x in outside
            )
            + ". For tier 1 sites the figure includes measured LBER electricity."
            if outside
            else "none."
        ),
    ]
    return lines
