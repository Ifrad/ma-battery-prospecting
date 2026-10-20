"""Out-of-sample check of the simulated load shape against EnerNOC meter data.

EnerNOC open data (100 anonymized commercial and industrial sites, 2012,
5-minute kWh, CC BY-NC 3.0), downloaded by make enernoc into data/enernoc/.
Used only as a test: no config value is derived or tuned from it.

The dataset skews each site's readings by an unknown linear factor, so only
unit-free measures are compared: peak-to-average ratio, monthly load factor
and the summer weekday 3 to 8 p.m. mean load over annual peak. The share of
a fixed 250 kW block's cut depends on a site's real kW, which the skew hides,
so it cannot be tested here. Readings are summed to 15-minute intervals.
"""

import csv
import io
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np

from prospect.sites.match_rates import table

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data" / "enernoc"
GROUPS = {
    "industrial": ("Light Industrial", None),
    "grocery": ("Food Sales & Storage", ("Grocery",)),
    "school": ("Education", ("PrimarySchool", "SecondarySchool")),
}
MEASURES = ("peak_to_average", "load_factor", "event_mean_over_peak")


def sites() -> list[dict]:
    text = (DATA / "all_sites.csv").read_text().replace("\r", "\n")
    return list(csv.DictReader(io.StringIO(text)))


def fifteen_minute(path: Path, tz: str) -> tuple[np.ndarray, list[datetime]]:
    """kW per 15-minute interval and each interval's local start time.

    Readings are interval-ending 5-minute kWh; anomalous readings are
    dropped, and an interval counts only with all three readings.
    """
    zone = ZoneInfo(tz)
    sums: dict[int, list[float]] = {}
    with path.open() as f:
        for r in csv.DictReader(f):
            if r["anomaly"]:
                continue
            start = int(r["timestamp"]) - 300  # reading covers the 5 minutes before
            sums.setdefault(start // 900, []).append(float(r["value"]))
    keys = sorted(k for k, v in sums.items() if len(v) == 3)
    kw = np.array([sum(sums[k]) * 4 for k in keys])
    starts = [datetime.fromtimestamp(k * 900, UTC).astimezone(zone) for k in keys]
    return kw, starts


def measures(kw: np.ndarray, starts: list[datetime]) -> dict:
    """Unit-free shape measures of one site."""
    months = np.array([s.month for s in starts])
    lf = [
        kw[months == m].mean() / kw[months == m].max()
        for m in range(1, 13)
        if (months == m).sum() > 0 and kw[months == m].max() > 0
    ]
    window = np.array(
        [s.weekday() < 5 and 6 <= s.month <= 9 and 15 <= s.hour < 20 for s in starts]
    )
    peak = kw.max()
    return {
        "peak_to_average": float(peak / kw.mean()),
        "load_factor": lf,
        "event_mean_over_peak": float(kw[window].mean() / peak),
    }


def model_ranges(cfg: dict) -> dict:
    """The simulated range each group is compared with: p10 to p90 of its
    ComStock types, or for industrial sites (no open profile) the widest
    range the model uses (load factor) or the pooled range."""
    sim = cfg["simulation"]
    out = {}
    for group, (_, types) in GROUPS.items():
        if types is None:
            env = sim["no_open_profile"]["load_factor"]
            pooled = sim["pooled"]
            par = [t["peak_to_average"] for t in sim["types"].values()]
            out[group] = {
                "load_factor": (env["low"], env["high"]),
                "peak_to_average": (
                    min(p["p10"] for p in par),
                    max(p["p90"] for p in par),
                ),
                "event_mean_over_peak": (
                    pooled["event_window"]["mean_over_peak"]["p10"],
                    pooled["event_window"]["mean_over_peak"]["p90"],
                ),
            }
            continue
        cells = [sim["types"][t] for t in types]
        out[group] = {
            "load_factor": (
                min(c["load_factor"]["p10"] for c in cells),
                max(c["load_factor"]["p90"] for c in cells),
            ),
            "peak_to_average": (
                min(c["peak_to_average"]["p10"] for c in cells),
                max(c["peak_to_average"]["p90"] for c in cells),
            ),
            "event_mean_over_peak": (
                min(c["event_window"]["mean_over_peak"]["p10"] for c in cells),
                max(c["event_window"]["mean_over_peak"]["p90"] for c in cells),
            ),
        }
    return out


def compare(values: dict, ranges: dict) -> dict:
    """Per measure: observed p10, median, p90, the model range and the share
    of observations inside it."""
    out = {}
    for m in MEASURES:
        x = np.asarray(values[m], dtype=float)
        lo, hi = ranges[m]
        p10, med, p90 = np.percentile(x, [10, 50, 90])
        out[m] = {
            "n": len(x),
            "p10": float(p10),
            "median": float(med),
            "p90": float(p90),
            "low": lo,
            "high": hi,
            "inside": float(np.mean((x >= lo) & (x <= hi))),
            "below": float(np.mean(x < lo)),
            "above": float(np.mean(x > hi)),
        }
    return out


def results(cfg: dict) -> dict | None:
    if not (DATA / "csv").exists():
        return None
    meta = sites()
    ranges = model_ranges(cfg)
    out = {}
    for group, (industry, _) in GROUPS.items():
        values = {m: [] for m in MEASURES}
        members = [s for s in meta if s["INDUSTRY"] == industry]
        for s in members:
            kw, starts = fifteen_minute(
                DATA / "csv" / f"{s['SITE_ID']}.csv", s["TIME_ZONE"]
            )
            m = measures(kw, starts)
            values["peak_to_average"].append(m["peak_to_average"])
            values["load_factor"] += m["load_factor"]
            values["event_mean_over_peak"].append(m["event_mean_over_peak"])
        subs = Counter(s["SUB_INDUSTRY"].lower() for s in members)
        out[group] = {
            "sites": len(members),
            "kinds": ", ".join(f"{n} {k}" for k, n in subs.most_common()),
            **compare(values, ranges[group]),
        }
    return out


LABELS = {
    "peak_to_average": "Peak to average",
    "load_factor": "Monthly load factor (site-months)",
    "event_mean_over_peak": "Summer 3 to 8 pm mean over peak",
}
GROUP_LABELS = {
    "industrial": "Light industrial against the no-open-profile range",
    "grocery": "Grocers against ComStock Grocery",
    "school": "K-12 schools against ComStock primary and secondary schools",
}


def section(r: dict | None) -> list[str]:
    head = [
        "## Out-of-sample check against EnerNOC meter data",
        "",
        "Data: EnerNOC open data, 100 anonymized commercial and industrial"
        " sites, 2012, 5-minute readings, licensed under Creative Commons"
        " Attribution-NonCommercial 3.0 (CC BY-NC 3.0), from EnerNOC's"
        " GreenButton open data project. The tool does not incorporate this"
        " data: it is downloaded locally by `make enernoc`, never committed or"
        " redistributed, and no config value is derived or tuned from it. It"
        " has no warehouses, its locations and square footage are anonymized,"
        " and it is from 2012, against ComStock's 2018 weather.",
        "",
        "The dataset skews each site's readings by an unknown linear factor, so"
        " only unit-free measures are compared, after summing to 15-minute"
        " intervals. The share of a 250 kW block's cut, and the size bins,"
        " depend on a site's real kW and cannot be tested with it. Observed"
        " values outside the model's range are reported, and config is not"
        " changed.",
    ]
    if r is None:
        return [*head, "", "Not run on this machine: run `make enernoc` first."]
    out = head
    for g, v in r.items():
        out += [
            "",
            f"{GROUP_LABELS[g]}, {v['sites']} sites ({v['kinds']}):",
            "",
            table(
                [
                    "Measure",
                    "Observations",
                    "Observed p10 / median / p90",
                    "Model range",
                    "Inside",
                    "Below",
                    "Above",
                ],
                [
                    [
                        LABELS[m],
                        v[m]["n"],
                        f"{v[m]['p10']:.2f} / {v[m]['median']:.2f} / {v[m]['p90']:.2f}",
                        f"{v[m]['low']:.2f} to {v[m]['high']:.2f}",
                        f"{v[m]['inside']:.0%}",
                        f"{v[m]['below']:.0%}",
                        f"{v[m]['above']:.0%}",
                    ]
                    for m in MEASURES
                ],
            ),
        ]
    return out


# Rescale test: shape given an assumed peak, not real kW.
RESCALE_GROUPS = {"industrial": "Light Industrial", "grocery": "Food Sales & Storage"}
COMSTOCK_SIM = ROOT / "data" / "comstock" / "simulation.csv"


def bin_targets(cfg: dict) -> dict:
    """The assumed annual peak per size bin: the bin's midpoint, or for the
    open top bin the median annual peak of the ComStock sample buildings in
    it (data/comstock/simulation.csv)."""
    out = {}
    for label, (lo, hi) in cfg["simulation"]["bins_kw"].items():
        if hi is not None:
            out[label] = (lo + hi) / 2
            continue
        with COMSTOCK_SIM.open() as f:
            peaks = {
                r["bldg_id"]: float(r["annual_peak_kw"]) for r in csv.DictReader(f)
            }
        out[label] = float(np.median([p for p in peaks.values() if p >= lo]))
    return out


def monthly_shares(profiles: list, peak_kw: float, b: dict) -> np.ndarray:
    """All-hours monthly peak cut share of one block for each site-month, with
    every profile scaled so its annual peak is peak_kw."""
    from prospect.priors.simulate import by_month, lowest_peak

    loads, valids = [], []
    for kw, starts in profiles:
        scaled = kw * peak_kw / kw.max()
        index, valid = by_month(scaled, starts)
        loads.append(np.where(valid, scaled[index], 0.0))
        valids.append(valid)
    load, valid = np.concatenate(loads), np.concatenate(valids)
    keep = valid.any(axis=1)
    load, valid = load[keep], valid[keep]
    peak = np.where(valid, load, 0.0).max(axis=1)
    held = lowest_peak(load, valid, b)
    return (peak - held) / peak


def rescale_results(cfg: dict) -> dict | None:
    if not (DATA / "csv").exists() or not COMSTOCK_SIM.exists():
        return None
    from prospect.model.savings import bin_envelope
    from prospect.priors.simulate import battery

    b = battery()
    targets = bin_targets(cfg)
    meta = sites()
    grocery_cells = cfg["simulation"]["types"]["Grocery"]["bins"]
    out = {"targets": targets}
    for group, industry in RESCALE_GROUPS.items():
        members = [s for s in meta if s["INDUSTRY"] == industry]
        profiles = [
            fifteen_minute(DATA / "csv" / f"{s['SITE_ID']}.csv", s["TIME_ZONE"])
            for s in members
        ]
        rows = {}
        for label, peak in targets.items():
            x = monthly_shares(profiles, peak, b)
            if group == "industrial":
                lo, hi = bin_envelope(label, "all_hours", cfg)
                model = f"{lo:.2f} to {hi:.2f} (no-profile range)"
            else:
                c = grocery_cells[label]
                lo, hi = c["all_hours"]["p10"], c["all_hours"]["p90"]
                model = f"{lo:.2f} to {hi:.2f}" + (
                    " (pooled, under 10 ComStock grocers)"
                    if c["pooled_fallback"]
                    else ""
                )
            p10, med, p90 = np.percentile(x, [10, 50, 90])
            rows[label] = {
                "sites": len(members),
                "site_months": int(len(x)),
                "p10": float(p10),
                "median": float(med),
                "p90": float(p90),
                "model": model,
                "inside": float(np.mean((x >= lo) & (x <= hi))),
            }
        out[group] = rows
    return out


def rescale_section(r: dict | None) -> list[str]:
    head = [
        "### Peak cut share with an assumed peak",
        "",
        "This tests load shape given an assumed peak, not real kW: each light"
        " industrial and grocery profile is scaled so its annual peak equals the"
        " midpoint of a Phase 3 size bin (100, 350 and 750 kW; for 1,000 kW and"
        " up, which has no midpoint, the median annual peak of the ComStock"
        " sample buildings in that bin), and the same dispatch as the ComStock"
        " simulation (250 kW, 522 kWh block, perfect foresight) gives the"
        " all-hours monthly peak cut share. The license limits above apply; no"
        " config value comes from it.",
    ]
    if r is None:
        return [
            *head,
            "",
            "Not run on this machine: run `make enernoc` and `make simulate`.",
        ]
    out = head
    names = {"industrial": "Light industrial", "grocery": "Grocers"}
    for group, label in names.items():
        out += [
            "",
            f"{label}:",
            "",
            table(
                [
                    "Size bin",
                    "Assumed peak kW",
                    "Sites",
                    "Site-months",
                    "Share p10 / median / p90",
                    "Model range (p10 to p90)",
                    "Inside",
                ],
                [
                    [
                        b,
                        f"{r['targets'][b]:,.0f}",
                        v["sites"],
                        v["site_months"],
                        f"{v['p10']:.2f} / {v['median']:.2f} / {v['p90']:.2f}",
                        v["model"],
                        f"{v['inside']:.0%}",
                    ]
                    for b, v in r[group].items()
                ],
            ),
        ]
    return out
