"""Write docs/SCORES.md from a stored score run.

Values are simulated gross yearly revenue per battery block, before any host
share. They are not profit, not accurate and unvalidated.
"""

from pathlib import Path

import numpy as np

from prospect.sites.match_rates import table

ROOT = Path(__file__).resolve().parents[2]
PAGE = ROOT / "docs" / "SCORES.md"
REGIONS = {"metro_south": "Metro South", "worcester": "Worcester"}
SCENARIOS = {
    "demand_savings": "Demand savings only",
    "with_connected_solutions": "Plus ConnectedSolutions",
}
VALUE_LINES = (20_000, 30_000, 40_000)
TOP = 15


def usd(x: float) -> str:
    return f"${x:,.0f}"


def rows(conn, run_id: int) -> list[dict]:
    cur = conn.execute(
        """
        SELECT s.*, st.owner, initcap(u.attrs ->> 'TOWN') AS town
        FROM site_scores s
        JOIN sites st USING (site_id)
        JOIN raw_utility_territories u
            ON (u.attrs ->> 'TOWN_ID')::integer = st.town_id
        WHERE s.run_id = %s
        ORDER BY s.site_id, s.scenario
        """,
        (run_id,),
    )
    names = [d.name for d in cur.description]
    return [dict(zip(names, r, strict=True)) for r in cur.fetchall()]


def reprice(r: dict, cfg: dict, real: float, perf: float, overlap: float) -> float:
    """P50 value per block with the three factors changed, from stored units.

    Stored kW-months already carry the config realization factor and stored
    grid kW the config performance and overlap factors; all scale linearly.
    """
    base_real = cfg["profiles"]["realization_factor"]["value"]
    cs = cfg["connected_solutions"]
    base_grid = cs["performance_factor"]["value"] * (1 - cs["overlap_factor"]["value"])
    rates = {
        s["name"]: s["demand_charge_per_kw_month"]
        for s in cfg["rates"]["utilities"][r["utility"]]["schedules"]
    }
    demand = np.asarray(r["kwm_g2"]) * rates["G-2"] + np.asarray(
        r["kwm_g3"]
    ) * rates.get("G-3", 0.0)
    value = demand * real / base_real
    if r["scenario"] == "with_connected_solutions" and base_grid > 0:
        grid = (
            np.asarray(r["grid_kw"]) * cs["daily_dispatch_usd_per_kw_season"]["value"]
        )
        value = value + grid * perf * (1 - overlap) / base_grid
    return float(np.median(value))


def counts_section(scored: list[dict]) -> list[str]:
    out = ["## Scored sites", ""]
    tiers = [
        [
            label,
            sum(r["region"] == k and r["tier"] == 1 for r in scored),
            sum(r["region"] == k and r["tier"] == 2 for r in scored),
            sum(r["region"] == k for r in scored),
            sum(r["region"] == k and r["passes_200kw"] for r in scored),
            sum(r["region"] == k and r["least_certain"] for r in scored),
        ]
        for k, label in REGIONS.items()
    ]
    tiers.append(["Both", *(sum(t[i] for t in tiers) for i in range(1, 6))])
    out.append(
        table(
            ["Region", "Tier 1", "Tier 2", "All", "Pass 200 kW", "No open profile"],
            tiers,
        )
    )
    out += ["", "By segment:", ""]
    segs = sorted({r["segment"] for r in scored})
    out.append(
        table(
            ["Segment", *REGIONS.values(), "Tier 1", "Tier 2"],
            [
                [
                    s,
                    *(
                        sum(r["segment"] == s and r["region"] == k for r in scored)
                        for k in REGIONS
                    ),
                    sum(r["segment"] == s and r["tier"] == 1 for r in scored),
                    sum(r["segment"] == s and r["tier"] == 2 for r in scored),
                ]
                for s in segs
            ],
        )
    )
    return out


def value_section(by: dict) -> list[str]:
    out = ["## Value per block", ""]
    out.append(
        "Across scored sites: the 10th, 50th and 90th percentile of each site's"
        " P50 value per block, the median of each site's P10 and P90, and how"
        " many sites have a P50 above each line."
    )
    body = []
    for scen, label in SCENARIOS.items():
        rs = by[scen]
        p50 = np.array([r["value_p50"] for r in rs])
        q = np.percentile(p50, [10, 50, 90])
        body.append(
            [
                label,
                usd(q[0]),
                usd(q[1]),
                usd(q[2]),
                usd(np.median([r["value_p10"] for r in rs])),
                usd(np.median([r["value_p90"] for r in rs])),
                *(int((p50 > v).sum()) for v in VALUE_LINES),
            ]
        )
    out += [
        "",
        table(
            [
                "Scenario",
                "P50 across sites, p10",
                "median",
                "p90",
                "Median site P10",
                "Median site P90",
                *(f"P50 over {usd(v)}" for v in VALUE_LINES),
            ],
            body,
        ),
    ]
    return out


def break_even_section(by: dict, cfg: dict) -> list[str]:
    est = cfg["costs"]["installed_cost_usd"]
    out = ["## Break-even installed cost per block", ""]
    out.append(
        "The installed cost per block at which P50 value per block equals the"
        " annualized cost (life, financing rate and O&M from config/costs.yaml)."
        " It leaves out any host benefit. The ITC column applies the 30 percent"
        " credit where the site is under 1 MW; it is off by default. The two"
        f" estimates ({usd(est['low'])} and {usd(est['middle'])}) are the owner's"
        " unverified reference points, not model inputs: a site clears one when"
        " its break-even cost is at or above it."
    )
    body = []
    for scen, label in SCENARIOS.items():
        for itc, col in ((False, "break_even_p50"), (True, "break_even_p50_itc")):
            be = np.array([r[col] for r in by[scen]])
            q = np.percentile(be, [10, 50, 90])
            body.append(
                [
                    label,
                    "with ITC" if itc else "no ITC",
                    usd(q[0]),
                    usd(q[1]),
                    usd(q[2]),
                    int((be >= est["low"]).sum()),
                    int((be >= est["middle"]).sum()),
                    len(be),
                ]
            )
    out += [
        "",
        table(
            [
                "Scenario",
                "ITC",
                "p10",
                "median",
                "p90",
                f"Clear {usd(est['low'])}",
                f"Clear {usd(est['middle'])}",
                "Sites",
            ],
            body,
        ),
    ]
    return out


def streams_section(by: dict) -> list[str]:
    rs = by["with_connected_solutions"]
    demand = sum(r["demand_p50"] for r in rs)
    grid = sum(r["grid_p50"] for r in rs)
    total = demand + grid
    return [
        "## Value by revenue stream",
        "",
        "Share of the sum of each stream's P50 per block across scored sites,"
        " with ConnectedSolutions. No other stream is modeled"
        " (docs/REVENUE_STREAMS.md).",
        "",
        table(
            ["Stream", "Sum of P50 per block", "Share"],
            [
                ["Demand savings", usd(demand), f"{demand / total:.0%}"],
                ["ConnectedSolutions", usd(grid), f"{grid / total:.0%}"],
            ],
        ),
    ]


def sensitivity_section(by: dict, cfg: dict) -> list[str]:
    real = cfg["profiles"]["realization_factor"]
    cs = cfg["connected_solutions"]
    perf, over = cs["performance_factor"], cs["overlap_factor"]
    base = (real["value"], perf["value"], over["value"])
    cases = [
        ("Realization factor", 0, real),
        ("ConnectedSolutions performance factor", 1, perf),
        ("ConnectedSolutions overlap factor", 2, over),
    ]
    rs = by["with_connected_solutions"]

    def median_value(factors) -> float:
        return float(np.median([reprice(r, cfg, *factors) for r in rs]))

    body = []
    for name, i, c in cases:
        vals = []
        for v in (c["range"]["low"], c["value"], c["range"]["high"]):
            f = list(base)
            f[i] = v
            vals.append(median_value(f))
        body.append(
            [
                name,
                f"{c['range']['low']} / {c['value']} / {c['range']['high']}",
                usd(vals[0]),
                usd(vals[1]),
                usd(vals[2]),
                usd(max(vals) - min(vals)),
            ]
        )
    return [
        "## Sensitivity",
        "",
        "Median P50 value per block across scored sites, with ConnectedSolutions,"
        " with one factor at a time at the low end, default and high end of its"
        " range in config. Repriced from the stored draws.",
        "",
        table(
            ["Factor", "Low / default / high", "Low", "Default", "High", "Swing"], body
        ),
    ]


def payback_section(by: dict, cfg: dict) -> list[str]:
    med = float(np.median([r["value_p50"] for r in by["with_connected_solutions"]]))
    est = cfg["costs"]["installed_cost_usd"]
    return [
        "## Payback check",
        "",
        "The operator says it recovers costs in 2 to 3 years. At the median P50"
        f" value per block with ConnectedSolutions, {usd(med)} a year, a simple"
        f" payback of 2 years implies an installed cost of {usd(2 * med)} per"
        f" block and 3 years {usd(3 * med)}, against the owner's estimates of"
        f" {usd(est['low'])} and {usd(est['middle'])}. This is a consistency"
        " check on the cost estimates, not evidence for or against the claim:"
        " simple payback ignores financing, O&M and the host's share.",
    ]


def rank_key(r: dict) -> tuple:
    """Rank by P50 value per block, then expected blocks, then P50 total."""
    return (-r["value_p50"], -r["blocks"], -r["total_p50"], r["site_id"])


def top_section(by: dict) -> list[str]:
    out = ["## Top sites by value per block", ""]
    out.append(
        f"The {TOP} sites per region with the highest P50 value per block, with"
        " ConnectedSolutions. Value is per block per year; the band is P10 to"
        " P90. Break-even is per block at P50, without the ITC. Ties are"
        " broken by expected blocks, then P50 total. capped: one block's cut"
        " reaches its power limit in most draws, so value per block is at the"
        " one-block ceiling. Rate area unconfirmed: Eversource sites in Canton"
        " and Sharon, priced at the Greater Boston rates (a placeholder)."
    )
    for k, label in REGIONS.items():
        rs = sorted(
            (r for r in by["with_connected_solutions"] if r["region"] == k),
            key=rank_key,
        )[:TOP]
        out += [
            "",
            f"### {label}",
            "",
            table(
                [
                    "Owner",
                    "Town",
                    "Segment",
                    "Tier",
                    "Blocks",
                    "Value per block P50",
                    "P10 to P90",
                    "Break-even",
                    "Note",
                ],
                [
                    [
                        r["owner"],
                        r["town"],
                        r["segment"],
                        r["tier"],
                        f"{r['blocks']:.1f}",
                        usd(r["value_p50"]),
                        f"{usd(r['value_p10'])} to {usd(r['value_p90'])}",
                        usd(r["break_even_p50"]),
                        "; ".join(
                            n
                            for n, on in (
                                ("no open profile, least certain", r["least_certain"]),
                                ("under 200 kW", not r["passes_200kw"]),
                                ("capped", "capped" in r["flags"]),
                                (
                                    "Eversource, all-hours reduction",
                                    "eversource_all_hours" in r["flags"],
                                ),
                                (
                                    "rate area unconfirmed",
                                    "rate_area_unconfirmed" in r["flags"],
                                ),
                            )
                            if on
                        ),
                    ]
                    for r in rs
                ],
            ),
        ]
    return out


def render(scored: list[dict], run: dict, cfg: dict) -> str:
    by = {s: [r for r in scored if r["scenario"] == s] for s in SCENARIOS}
    one = by["with_connected_solutions"]
    parts = [
        "# Scores",
        "",
        f"Generated by `make score` on {run['scored_at']:%Y-%m-%d}, run"
        f" {run['run_id']}, {run['draws']} draws per site, config"
        f" {run['config_hash'][:12]}. Values are simulated gross yearly revenue"
        " per battery block, before any host share: not profit, not accurate,"
        " and unvalidated. Peak shape is simulated (ComStock, 2018 weather,"
        " perfect foresight reduced by the realization factor).",
        "",
        f"Scope: {len(one)} funnel survivors at 150 kW (docs/FUNNEL.md), two"
        " scenarios each. Municipal plant sites are not scored. Model"
        " confidence is not computed here; run `prospect score --installed-cost"
        " X --min-host-benefit Y` for a given cost.",
        "",
        *counts_section(one),
        "",
        *value_section(by),
        "",
        *break_even_section(by, cfg),
        "",
        *streams_section(by),
        "",
        *sensitivity_section(by, cfg),
        "",
        *payback_section(by, cfg),
        "",
        *top_section(by),
    ]
    return "\n".join(parts) + "\n"


def write(conn, run_id: int, cfg: dict, path: Path = PAGE) -> None:
    cur = conn.execute("SELECT * FROM score_runs WHERE run_id = %s", (run_id,))
    run = dict(zip([d.name for d in cur.description], cur.fetchone(), strict=True))
    path.write_text(render(rows(conn, run_id), run, cfg))
