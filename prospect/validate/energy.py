"""Annual energy estimates against LBER measured electricity, towns held out.

Each building with measured grid electricity (zero or negative is missing) is
estimated as if unmeasured: its floor area times its segment's median
intensity, with the priors recomputed from every town but its own, by the
Phase 3 rules (prospect/priors/intensity.py). The size-only estimate is the
area times one global median intensity from the same other towns.

Pilot: the model as built, on our segments and our building areas.
Statewide: the same method on LBER's own property types and floor areas, a
method check, since statewide buildings have no segment or area of ours.
LBER covers buildings of about 20,000 sq ft and up only.
"""

import numpy as np

from prospect.model.drivers import spearman
from prospect.priors.intensity import HEALTHCARE, PROXY, PROXY_FOR
from prospect.sites.match_rates import table

PILOT = """
    SELECT b.town_id, b.segment, b.area_sqft, b.grid_kwh
    FROM building_evidence b
    WHERE b.electricity_source = 'measured' AND b.segment IS NOT NULL
        AND b.grid_kwh > 0 AND b.area_sqft > 0
"""
STATEWIDE = """
    SELECT (u.attrs ->> 'TOWN_ID')::integer, lower(l.attrs ->> 'Property_Type'),
           (l.attrs ->> 'Gross_Floor_Area')::float, l.grid_kwh
    FROM raw_lber l
    JOIN raw_utility_territories u ON ST_Contains(u.geom, l.geom)
    WHERE l.grid_kwh > 0 AND (l.attrs ->> 'Gross_Floor_Area')::float > 0
        AND l.attrs ->> 'Property_Type' IS NOT NULL
"""


def load(conn, sql: str) -> dict:
    rows = conn.execute(sql).fetchall()
    cols = list(zip(*rows, strict=True)) if rows else [[], [], [], []]
    return {
        "town": np.array(cols[0]),
        "segment": np.array(cols[1], dtype=object),
        "area": np.array(cols[2], dtype=float),
        "kwh": np.array(cols[3], dtype=float),
    }


def pilot_prior(segment: str, train: dict, healthcare: dict) -> float:
    """The median intensity a pilot segment gets from training rows, by the
    Phase 3 rules: other_healthcare from statewide Healthcare rows, the
    proxy segments from manufacturing, the rest from their own rows."""
    if segment in HEALTHCARE:
        return float(np.median(healthcare["kwh"] / healthcare["area"]))
    source = PROXY if segment in PROXY_FOR else segment
    return own_prior(source, train, None)


def holdout(rows: dict, prior, healthcare: dict | None = None) -> dict:
    """Model and size-only estimates for every row, its town held out."""
    model = np.full(len(rows["kwh"]), np.nan)
    size = np.full(len(rows["kwh"]), np.nan)
    for town in np.unique(rows["town"]):
        test = rows["town"] == town
        train = {k: v[~test] for k, v in rows.items()}
        hc = None
        if healthcare is not None:
            keep = healthcare["town"] != town
            hc = {k: v[keep] for k, v in healthcare.items()}
        global_median = float(np.median(train["kwh"] / train["area"]))
        size[test] = rows["area"][test] * global_median
        for seg in np.unique(rows["segment"][test]):
            m = test & (rows["segment"] == seg)
            p = prior(seg, train, hc)
            model[m] = rows["area"][m] * p
    return {"model": model, "size": size}


def own_prior(segment: str, train: dict, _hc) -> float:
    """Statewide method check: each property type's own median."""
    mask = train["segment"] == segment
    if not mask.any():
        return float(np.median(train["kwh"] / train["area"]))
    return float(np.median(train["kwh"][mask] / train["area"][mask]))


def metrics(kwh: np.ndarray, est: np.ndarray) -> dict:
    ok = np.isfinite(est)
    kwh, est = kwh[ok], est[ok]
    return {
        "n": int(len(kwh)),
        "spearman": spearman(est, kwh) if len(kwh) > 2 else float("nan"),
        "mdape": float(np.median(np.abs(est - kwh) / kwh))
        if len(kwh)
        else float("nan"),
    }


def results(conn) -> dict:
    pilot = load(conn, PILOT)
    state = load(conn, STATEWIDE)
    hc_mask = state["segment"] == "healthcare"
    healthcare = {k: v[hc_mask] for k, v in state.items()}
    out = {}
    for name, rows, prior, hc in (
        ("pilot", pilot, pilot_prior, healthcare),
        ("statewide", state, own_prior, None),
    ):
        est = holdout(rows, prior, hc)
        groups = {"all": np.ones(len(rows["kwh"]), dtype=bool)}
        for seg in sorted(set(rows["segment"])):
            groups[seg] = rows["segment"] == seg
        out[name] = {
            g: {
                "model": metrics(rows["kwh"][m], est["model"][m]),
                "size": metrics(rows["kwh"][m], est["size"][m]),
            }
            for g, m in groups.items()
        }
    return out


def rho(x: float) -> str:
    return "n/a" if np.isnan(x) else f"{x:.2f}"


def section(r: dict) -> list[str]:
    def rows(part):
        return [
            [
                g,
                v["model"]["n"],
                rho(v["model"]["spearman"]),
                rho(v["size"]["spearman"]),
                f"{v['model']['mdape']:.0%}",
                f"{v['size']['mdape']:.0%}",
            ]
            for g, v in part.items()
        ]

    header = [
        "Group",
        "Buildings",
        "Spearman, model",
        "Spearman, size-only",
        "Median abs. error, model",
        "Median abs. error, size-only",
    ]
    return [
        "## Annual energy against LBER, towns held out",
        "",
        "Each LBER building with measured grid electricity (zero or negative is"
        " missing) is estimated as if unmeasured: floor area times its"
        " segment's median kWh per sq ft, with the priors recomputed from every"
        " other town by the Phase 3 rules. Size-only is floor area times one"
        " global median from the same other towns. Spearman is the rank"
        " correlation with measured kWh (higher is better); the error is the"
        " median absolute percent error (lower is better). LBER covers only"
        " buildings of about 20,000 sq ft and up, so this says nothing about"
        " smaller buildings.",
        "",
        "Within one segment both estimates are floor area times a constant,"
        " so they rank buildings the same way; the model can only rank better"
        " across segments, and it can be closer in level. Spearman needs three"
        " or more buildings (n/a below that). Errors this large partly reflect"
        " the first LBER release, where many reported values are implausibly"
        " low (config/intensity.yaml).",
        "",
        "Pilot: the model as built, on our segments and building areas.",
        "",
        table(header, rows(r["pilot"])),
        "",
        "Statewide: the same method on LBER's own property types and floor"
        " areas, a method check, since statewide buildings have no segment or"
        " area of ours.",
        "",
        table(header, rows(r["statewide"])),
    ]
