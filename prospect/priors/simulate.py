"""Simulate one battery block on the downloaded ComStock profiles.

Usage: python -m prospect.priors.simulate

Reads data/comstock/ (written by make comstock), writes one row per
building and month to data/comstock/simulation.csv, and summarizes them by
building type and peak size into config/simulation.yaml. The dispatch rule
is described in docs/METHOD.md. Results are simulated, with perfect
foresight over each month, so they are an upper bound.
"""

import csv
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

import numpy as np
import pyarrow.parquet as pq
import yaml

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data" / "comstock"
CONFIG_OUT = ROOT / "config" / "simulation.yaml"
# Bins by a building's annual peak kW; cells with fewer buildings than
# MIN_CELL use all types pooled in that bin.
BINS = [
    ("under_200", 0, 200),
    ("200_to_500", 200, 500),
    ("500_to_1000", 500, 1000),
    ("1000_up", 1000, float("inf")),
]
MIN_CELL = 10
STEP_H = 0.25
STEPS_PER_MONTH = 31 * 96  # months are padded to 31 days
ELECTRICITY = "out.electricity.total.energy_consumption"


def battery(path: Path = ROOT / "config" / "battery.yaml") -> dict:
    cfg = yaml.safe_load(path.read_text())
    b = cfg["block"]
    return {
        "power_kw": b["power_kw"],
        "usable_kwh": b["energy_kwh"] * cfg["usable_depth_of_discharge"]["value"],
        "efficiency": b["pcs_efficiency"],
    }


def nth_weekday(year: int, month: int, weekday: int, n: int) -> date:
    """The nth given weekday (0 is Monday) of a month; n = -1 is the last."""
    if n > 0:
        first = date(year, month, 1)
        return first + timedelta(days=(weekday - first.weekday()) % 7 + 7 * (n - 1))
    last = date(year, month + 1, 1) - timedelta(days=1)
    return last - timedelta(days=(last.weekday() - weekday) % 7)


def observed(d: date) -> date:
    """A fixed-date holiday on a weekend is observed on Friday or Monday."""
    return (
        d - timedelta(days=1)
        if d.weekday() == 5
        else (d + timedelta(days=1) if d.weekday() == 6 else d)
    )


HOLIDAYS = {
    "New Year's Day": lambda y: observed(date(y, 1, 1)),
    "Presidents' Day": lambda y: nth_weekday(y, 2, 0, 3),
    "Memorial Day": lambda y: nth_weekday(y, 5, 0, -1),
    "Independence Day": lambda y: observed(date(y, 7, 4)),
    "Labor Day": lambda y: nth_weekday(y, 9, 0, 1),
    "Columbus Day": lambda y: nth_weekday(y, 10, 0, 2),
    "Veterans Day": lambda y: observed(date(y, 11, 11)),
    "Thanksgiving Day": lambda y: nth_weekday(y, 11, 3, 4),
    "Christmas Day": lambda y: observed(date(y, 12, 25)),
}


def peak_window(starts: list[datetime], window: dict) -> np.ndarray:
    """True for steps that start inside the G-3 peak window."""
    start = int(window["start"][:2]) * 60 + int(window["start"][3:])
    end = int(window["end"][:2]) * 60 + int(window["end"][3:])
    years = {s.year for s in starts}
    off = {HOLIDAYS[h](y) for h in window["holidays"] for y in years}
    return np.array(
        [
            s.weekday() < 5
            and s.date() not in off
            and start <= s.hour * 60 + s.minute < end
            for s in starts
        ]
    )


def event_window(starts: list[datetime], terms: dict) -> tuple[np.ndarray, np.ndarray]:
    """ConnectedSolutions event-window steps: (summer, all year).

    Weekdays inside the daily dispatch window (3 to 8 p.m.); summer adds the
    event months (June to September). The program uses the all-year weekday
    window peak to set a G-3 site's peak for its export cap.
    """
    start = int(terms["window"]["start"][:2]) * 60 + int(terms["window"]["start"][3:])
    end = int(terms["window"]["end"][:2]) * 60 + int(terms["window"]["end"][3:])
    weekday_window = np.array(
        [s.weekday() < 5 and start <= s.hour * 60 + s.minute < end for s in starts]
    )
    summer = np.array([s.month in terms["months"] for s in starts])
    return weekday_window & summer, weekday_window


def by_month(kw: np.ndarray, starts: list[datetime]) -> tuple[np.ndarray, np.ndarray]:
    """Split one year of steps into 12 rows padded to 31 days.

    Returns (index, valid): index[m, i] is the step number of month m's
    i-th step, valid marks real steps.
    """
    months = np.array([s.month for s in starts])
    index = np.zeros((12, STEPS_PER_MONTH), dtype=int)
    valid = np.zeros((12, STEPS_PER_MONTH), dtype=bool)
    for m in range(12):
        steps = np.flatnonzero(months == m + 1)
        index[m, : len(steps)] = steps
        valid[m, : len(steps)] = True
    return index, valid


def feasible(load, counted, threshold, b) -> np.ndarray:
    """Whether the battery can hold each row's counted load at its threshold.

    load and counted are (rows, steps); threshold is (rows,). The battery
    starts each row empty, charges with any spare room (never raising a
    counted step above the threshold) and discharges what counted steps
    exceed the threshold. Starting empty means every kWh it delivers was
    charged in the same row, so there is no free starting charge.
    """
    p, e, eff = b["power_kw"], b["usable_kwh"], b["efficiency"]
    soc = np.zeros(load.shape[0])
    ok = np.ones(load.shape[0], dtype=bool)
    for t in range(load.shape[1]):
        lt, ct = load[:, t], counted[:, t]
        need = np.where(ct, np.maximum(lt - threshold, 0.0), 0.0)
        ok &= need <= p + 1e-9
        soc = soc - need * STEP_H / eff
        ok &= soc >= -1e-9
        room = np.where(ct, np.clip(threshold - lt, 0.0, p), p)
        soc = soc + np.minimum(room, (e - soc) / (STEP_H * eff)) * STEP_H * eff
    return ok


def lowest_peak(load, counted, b, iterations: int = 30) -> np.ndarray:
    """Per row, the lowest counted peak the battery can hold, by bisection."""
    peak = np.where(counted, load, 0.0).max(axis=1)
    lo = np.maximum(peak - b["power_kw"], 0.0)
    hi = peak.copy()
    done = feasible(load, counted, lo, b)
    hi = np.where(done, lo, hi)
    for _ in range(iterations):
        mid = (lo + hi) / 2
        ok = feasible(load, counted, mid, b)
        hi = np.where(ok & ~done, mid, hi)
        lo = np.where(~ok & ~done, mid, lo)
    return hi


def read_profile(path: Path) -> tuple[np.ndarray, list[datetime]]:
    """kW per 15-minute step and each step's start (timestamps end the step)."""
    t = pq.read_table(path, columns=["timestamp", ELECTRICITY])
    kw = np.asarray(t.column(ELECTRICITY).to_numpy(), dtype=float) / STEP_H
    starts = [s - timedelta(minutes=15) for s in t.column("timestamp").to_pylist()]
    return kw, starts


def simulate(paths: list[Path], window: dict, b: dict, terms: dict) -> list[dict]:
    """One row per building and month: peaks, load factor and peak reduction,
    with the building's event-window mean and peak (terms: ConnectedSolutions
    daily dispatch terms) repeated on each of its rows."""
    loads, valids, windows, meta, events = [], [], [], [], []
    for path in paths:
        kw, starts = read_profile(path)
        summer, all_year = event_window(starts, terms)
        events.append((kw[summer].mean(), kw[all_year].max()))
        index, valid = by_month(kw, starts)
        in_window = peak_window(starts, window)
        loads.append(np.where(valid, kw[index], 0.0))
        valids.append(valid)
        windows.append(valid & in_window[index])
        meta.append((path, kw))
    load = np.concatenate(loads)
    valid = np.concatenate(valids)
    window_mask = np.concatenate(windows)
    peak_all = np.where(valid, load, 0.0).max(axis=1)
    peak_win = np.where(window_mask, load, 0.0).max(axis=1)
    held_all = lowest_peak(load, valid, b)
    held_win = lowest_peak(load, window_mask, b)
    mean_kw = load.sum(axis=1) / valid.sum(axis=1)
    rows = []
    for i, (path, kw) in enumerate(meta):
        for m in range(12):
            r = i * 12 + m
            rows.append(
                {
                    "bldg_id": int(path.name.split("-")[0]),
                    "annual_kwh": round(kw.sum() * STEP_H, 1),
                    "annual_peak_kw": round(kw.max(), 2),
                    "month": m + 1,
                    "month_mean_kw": round(mean_kw[r], 3),
                    "month_peak_kw": round(peak_all[r], 3),
                    "month_window_peak_kw": round(peak_win[r], 3),
                    "reduction_all_kw": round(peak_all[r] - held_all[r], 3),
                    "reduction_window_kw": round(peak_win[r] - held_win[r], 3),
                    "event_mean_kw": round(events[i][0], 3),
                    "event_peak_kw": round(events[i][1], 3),
                }
            )
    return rows


def spread(values) -> dict:
    """p10, median and p90, rounded; None for an empty cell."""
    values = list(values)
    if not values:
        return {"p10": None, "median": None, "p90": None}
    q = np.percentile(np.asarray(values, dtype=float), [10, 50, 90])
    return {
        k: round(float(v), 3) for k, v in zip(("p10", "median", "p90"), q, strict=True)
    }


def shares(rows: list[dict]) -> dict:
    """Monthly peak reduction as a share of the billed peak, both cases."""
    return {
        "all_hours": spread(r["reduction_all_kw"] / r["month_peak_kw"] for r in rows),
        "peak_window": spread(
            r["reduction_window_kw"] / r["month_window_peak_kw"]
            for r in rows
            if r["month_window_peak_kw"] > 0
        ),
    }


def event_ratios(first_rows) -> dict:
    """Event-window load over annual peak, across buildings: the summer
    weekday 3 to 8 p.m. mean, and the all-year weekday 3 to 8 p.m. peak."""
    rows = list(first_rows)
    return {
        "mean_over_peak": spread(
            r["event_mean_kw"] / r["annual_peak_kw"] for r in rows
        ),
        "peak_over_peak": spread(
            r["event_peak_kw"] / r["annual_peak_kw"] for r in rows
        ),
    }


def summarize(rows: list[dict], sample: list[dict]) -> dict:
    """Per building type: load shape and peak reduction by peak size bin."""
    btype = {s["bldg_id"]: s["building_type"] for s in sample}
    sqft = {s["bldg_id"]: s["sqft"] for s in sample}

    def binned(rs, label, lo, hi):
        cell = [r for r in rs if lo <= r["annual_peak_kw"] < hi]
        return cell, len({r["bldg_id"] for r in cell})

    pooled = {}
    for label, lo, hi in BINS:
        cell, n = binned(rows, label, lo, hi)
        pooled[label] = {"buildings": n, **shares(cell)}
    types = {}
    for t in sorted(set(btype.values())):
        rs = [r for r in rows if btype[r["bldg_id"]] == t]
        ids = sorted({r["bldg_id"] for r in rs})
        first = {r["bldg_id"]: r for r in rs if r["month"] == 1}
        bins = {}
        for label, lo, hi in BINS:
            cell, n = binned(rs, label, lo, hi)
            if n >= MIN_CELL:
                bins[label] = {"buildings": n, "pooled_fallback": False, **shares(cell)}
            else:
                bins[label] = {
                    "buildings": n,
                    "pooled_fallback": True,
                    **{k: v for k, v in pooled[label].items() if k != "buildings"},
                }
        types[t] = {
            "buildings": len(ids),
            "floor_area_median_sqft": round(float(np.median([sqft[i] for i in ids]))),
            "peak_kw": spread(first[i]["annual_peak_kw"] for i in ids),
            "peak_to_average": spread(
                first[i]["annual_peak_kw"] / (first[i]["annual_kwh"] / 8760)
                for i in ids
            ),
            "load_factor": spread(r["month_mean_kw"] / r["month_peak_kw"] for r in rs),
            "event_window": event_ratios(first[i] for i in ids),
            "bins": bins,
        }
    cells = [c for t in types.values() for c in t["bins"].values()]
    envelope = {
        case: {
            "low": min(c[case]["p10"] for c in cells if c[case]["p10"] is not None),
            "high": max(c[case]["p90"] for c in cells if c[case]["p90"] is not None),
        }
        for case in ("all_hours", "peak_window")
    }
    envelope["load_factor"] = {
        "low": min(t["load_factor"]["p10"] for t in types.values()),
        "high": max(t["load_factor"]["p90"] for t in types.values()),
    }
    return {
        "pooled": {
            "load_factor": spread(
                r["month_mean_kw"] / r["month_peak_kw"] for r in rows
            ),
            "event_window": event_ratios(r for r in rows if r["month"] == 1),
            "bins": pooled,
        },
        "types": types,
        "no_open_profile": envelope,
    }


HEADER = """\
# Generated by make simulate from the ComStock sample (config/comstock.yaml).
# Do not edit by hand. Simulated, one weather year (2018), perfect foresight
# over each month: an upper bound, unvalidated. Shares are monthly peak
# reduction over the month's billed peak, across building-months: all_hours
# is the National Grid G-2 peak, peak_window the G-3 peak window. Bins are by
# the building's annual peak kW. A cell with fewer than 10 buildings uses all
# types pooled in that bin (pooled_fallback: true) and keeps its own count.
# event_window: across buildings, the June to September weekday 3 to 8 p.m.
# mean load and the all-year weekday 3 to 8 p.m. peak, each over the annual
# peak, for the ConnectedSolutions caps.
"""


class NoAliases(yaml.SafeDumper):
    """Write repeated values in full, never as YAML anchors."""

    def ignore_aliases(self, data):
        return True


def write_config(summary: dict, path: Path = CONFIG_OUT) -> None:
    doc = {
        "status": "sourced",
        "source": (
            "Simulated by prospect/priors/simulate.py (dispatch rule in"
            " docs/METHOD.md) on the ComStock 2025 release 3 Massachusetts"
            " sample in config/comstock.yaml, 2018 weather."
        ),
        "note": (
            "Simulated, not measured: an upper bound with perfect foresight,"
            " peak shape unvalidated. Phase 4 applies the realization factor"
            " in config/profiles.yaml."
        ),
        "bins_kw": {
            label: [lo, None if hi == float("inf") else hi] for label, lo, hi in BINS
        },
        "min_cell_buildings": MIN_CELL,
        **summary,
    }
    path.write_text(
        HEADER
        + yaml.dump(
            doc, Dumper=NoAliases, sort_keys=False, width=88, default_flow_style=None
        )
    )


def main() -> int:
    rates = yaml.safe_load((ROOT / "config" / "rates.yaml").read_text())
    ngrid = rates["utilities"]["National Grid (Massachusetts Electric)"]
    window = next(s for s in ngrid["schedules"] if s["name"] == "G-3")["peak_window"]
    paths = sorted((DATA / "timeseries").glob("*.parquet"))
    cs = yaml.safe_load((ROOT / "config" / "connected_solutions.yaml").read_text())
    rows = simulate(paths, window, battery(), cs["daily_dispatch_terms"])
    out = DATA / "simulation.csv"
    with out.open("w", newline="") as f:
        w = csv.DictWriter(f, list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    sample = [
        {
            "bldg_id": int(r["bldg_id"]),
            "building_type": r["building_type"],
            "sqft": float(r["sqft"]),
        }
        for r in csv.DictReader((DATA / "sample.csv").open())
    ]
    write_config(summarize(rows, sample))
    print(f"wrote {out.relative_to(ROOT)}: {len(paths)} buildings, {len(rows)} rows")
    print(f"wrote {CONFIG_OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
