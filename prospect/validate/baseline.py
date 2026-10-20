"""Size-only baseline: rank sites by building area, as the earlier public
prototype (github.com/thutch17/powertown-hackathon) did, credited as prior
work. Its score also used town solar and battery permits, but only for
Boston, Cambridge and Somerville; elsewhere that part is a constant, so in
the pilot towns it ranks by size alone.
"""

from prospect.model.report import rank_key
from prospect.sites.match_rates import table

REGIONS = {"metro_south": "Metro South", "worcester": "Worcester"}
TOP = 50


def model_top(conn, region: str, k: int = TOP) -> list[str]:
    """The model's top k sites in a region, latest run, with ConnectedSolutions."""
    cur = conn.execute(
        "SELECT site_id, value_p50, blocks, total_p50 FROM site_scores"
        " WHERE run_id = (SELECT max(run_id) FROM score_runs)"
        " AND scenario = 'with_connected_solutions' AND region = %s",
        (region,),
    )
    names = [d.name for d in cur.description]
    rows = [dict(zip(names, r, strict=True)) for r in cur.fetchall()]
    return [r["site_id"] for r in sorted(rows, key=rank_key)[:k]]


def size_top(conn, region: str, scored_only: bool, k: int = TOP) -> list[str]:
    """The k candidate sites with the most building area in a region."""
    scope = (
        " AND site_id IN (SELECT site_id FROM site_scores"
        " WHERE run_id = (SELECT max(run_id) FROM score_runs))"
        if scored_only
        else ""
    )
    return [
        r[0]
        for r in conn.execute(
            "SELECT site_id FROM site_evidence WHERE candidate AND region = %s"
            + scope
            + " ORDER BY area_sqft DESC, site_id LIMIT %s",
            (region, k),
        ).fetchall()
    ]


def overlap(a: list[str], b: list[str]) -> int:
    return len(set(a) & set(b))


def results(conn) -> dict:
    out = {}
    for region in REGIONS:
        model = model_top(conn, region)
        every = size_top(conn, region, scored_only=False)
        dropped = dict(
            conn.execute(
                "SELECT f.dropped_by, count(*) FROM site_funnel f"
                " WHERE f.site_id = ANY(%s) AND f.site_id NOT IN ("
                "   SELECT site_id FROM site_scores"
                "   WHERE run_id = (SELECT max(run_id) FROM score_runs))"
                " GROUP BY 1",
                (every,),
            ).fetchall()
        )
        out[region] = {
            "overlap_all": overlap(model, every),
            "overlap_scored": overlap(model, size_top(conn, region, scored_only=True)),
            "size_top_dropped": dropped,
        }
    return out


def section(r: dict) -> list[str]:
    reasons = ("utility", "kwh", "peak")
    return [
        "## Size-only baseline",
        "",
        "The earlier public prototype (github.com/thutch17/powertown-hackathon),"
        " credited as prior work, ranked sites by building size and town permit"
        " history; outside Boston, Cambridge and Somerville the permit part is a"
        " constant, so in the pilot towns it is a size-only ranking. Here: the"
        f" {TOP} candidate sites per region with the most building area, against"
        f" the model's top {TOP} by value per block (with ConnectedSolutions).",
        "",
        table(
            [
                "Region",
                f"Overlap with size top {TOP}, all candidates",
                "Overlap, scored sites only",
                *(f"Size top {TOP} not scored: {x}" for x in reasons),
            ],
            [
                [
                    label,
                    r[k]["overlap_all"],
                    r[k]["overlap_scored"],
                    *(r[k]["size_top_dropped"].get(x, 0) for x in reasons),
                ]
                for k, label in REGIONS.items()
            ],
        ),
        "",
        "Not scored means the funnel dropped the site (docs/FUNNEL.md): utility"
        " is a municipal plant, kwh is under the monthly kWh line, and peak is"
        " an estimated peak under 150 kW. A large building is not a good battery"
        " site by size alone.",
    ]
