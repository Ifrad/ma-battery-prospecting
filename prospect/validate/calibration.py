"""Calibration of the annual energy band, towns held out.

Each pilot LBER building with measured grid electricity is drawn as if
unmeasured, with the model's own draw code (prospect/model/draws.py): its
area with the error of its area source, times its segment's intensity drawn
from the prior spread recomputed from every other town. An 80 percent band
(P10 to P90) should contain the measured kWh about 80 percent of the time.
"""

import copy

import numpy as np

from prospect.model import draws
from prospect.priors.intensity import HEALTHCARE, MIN_BUILDINGS, PROXY, PROXY_FOR
from prospect.sites.match_rates import table
from prospect.validate.energy import STATEWIDE, load

MIN_N = MIN_BUILDINGS  # the small-sample line of the intensity priors

PILOT = """
    SELECT b.building_id, b.town_id, b.segment, b.area_sqft, b.area_source,
           b.grid_kwh
    FROM building_evidence b
    WHERE b.electricity_source = 'measured' AND b.segment IS NOT NULL
        AND b.grid_kwh > 0 AND b.area_sqft > 0
    ORDER BY b.building_id
"""


def spread_of(x: np.ndarray) -> dict:
    p10, med, p90 = np.percentile(x, [10, 50, 90])
    return {"p10": float(p10), "median": float(med), "p90": float(p90)}


def holdout_spread(seg: str, town: int, pilot: list[dict], healthcare: dict) -> dict:
    """The segment's intensity spread from every other town, Phase 3 rules."""
    if seg in HEALTHCARE:
        keep = healthcare["town"] != town
        return spread_of(healthcare["kwh"][keep] / healthcare["area"][keep])
    source = PROXY if seg in PROXY_FOR else seg
    x = [
        b["grid_kwh"] / b["area_sqft"]
        for b in pilot
        if b["segment"] == source and b["town_id"] != town
    ]
    if len(x) < 3:  # too few left; fall back to every other building
        x = [b["grid_kwh"] / b["area_sqft"] for b in pilot if b["town_id"] != town]
    return spread_of(np.array(x))


def bands(pilot: list[dict], healthcare: dict, cfg: dict) -> list[dict]:
    """P10 and P90 of each building's draws as if unmeasured."""
    n = cfg["model"]["draws"]["value"]
    out = []
    for b in pilot:
        c = copy.copy(cfg)
        c["intensity"] = {
            "segments": {
                b["segment"]: {
                    "prior": holdout_spread(
                        b["segment"], b["town_id"], pilot, healthcare
                    )
                }
            }
        }
        x = draws.building_kwh({**b, "electricity_source": "estimated"}, c, n)
        p10, p90 = np.percentile(x, [10, 90])
        out.append({**b, "p10": p10, "p90": p90})
    return out


def hit_rates(rows: list[dict]) -> dict:
    """Share of buildings whose measured kWh is inside the band, by segment."""
    groups = {"all": rows}
    for seg in sorted({r["segment"] for r in rows}):
        groups[seg] = [r for r in rows if r["segment"] == seg]
    return {
        g: {
            "n": len(rs),
            "hit": float(np.mean([r["p10"] <= r["grid_kwh"] <= r["p90"] for r in rs])),
            "below": float(np.mean([r["grid_kwh"] < r["p10"] for r in rs])),
            "above": float(np.mean([r["grid_kwh"] > r["p90"] for r in rs])),
        }
        for g, rs in groups.items()
    }


def results(conn, cfg: dict) -> dict:
    cur = conn.execute(PILOT)
    names = [d.name for d in cur.description]
    pilot = [dict(zip(names, r, strict=True)) for r in cur.fetchall()]
    state = load(conn, STATEWIDE)
    hc = state["segment"] == "healthcare"
    healthcare = {k: v[hc] for k, v in state.items()}
    return hit_rates(bands(pilot, healthcare, cfg))


def section(r: dict, cfg: dict) -> list[str]:
    return [
        "## Calibration of the annual energy band",
        "",
        "This tests the annual energy estimate only, not peak shape. Each pilot"
        " LBER building with measured grid electricity is drawn as if"
        " unmeasured, with the model's own draws and its town held out of the"
        " priors. The P10 to P90 band claims 80 percent; the table shows how"
        " often it holds the measured kWh, and how often the measured value is"
        " below or above it.",
        "",
        table(
            ["Group", "Buildings", "Inside the band", "Below P10", "Above P90", ""],
            [
                [
                    g,
                    v["n"],
                    f"{v['hit']:.0%}",
                    f"{v['below']:.0%}",
                    f"{v['above']:.0%}",
                    "too few to judge" if v["n"] < MIN_N else "",
                ]
                for g, v in r.items()
            ],
        ),
        "",
        verdict(r["all"], cfg["validate"]["calibration_tolerance"]["value"]),
    ]


def verdict(all_: dict, tolerance: float) -> str:
    """Whether the overall band is calibrated, by config/validate.yaml."""
    off = abs(all_["hit"] - 0.8)
    if off <= tolerance:
        return (
            f"Overall the band holds the measured value {all_['hit']:.0%} of the"
            f" time against the 80 percent it claims, within {tolerance:.0%}, so"
            " the widths are not recalibrated. Groups under"
            f" {MIN_N} buildings are too small to judge on their own."
        )
    return (
        f"Overall the band holds the measured value {all_['hit']:.0%} of the"
        " time against the 80 percent it claims: outside the tolerance, so the"
        " widths need recalibrating."
    )
