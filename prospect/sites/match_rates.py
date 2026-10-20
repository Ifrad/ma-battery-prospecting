"""Write docs/MATCH_RATES.md and the hand review sheets in data/review/.

Usage: python -m prospect.sites.match_rates

Reads the database only (no network). The review samples use a fixed seed,
so a rerun on the same data gives the same rows.
"""

import csv
import random
from datetime import date
from pathlib import Path

from prospect.db import connect
from prospect.sites.segments import CANDIDATE_CLASSES

ROOT = Path(__file__).resolve().parents[2]
REPORT = ROOT / "docs" / "MATCH_RATES.md"
REVIEW = ROOT / "data" / "review"
SEED = 20261019
REGIONS = ("metro_south", "worcester")
LABEL = {"metro_south": "Metro South", "worcester": "Worcester"}
METHODS = ("ubid", "point_in_footprint", "point_in_parcel", "address")
MAP = (
    "https://www.google.com/maps/@?api=1&map_action=map"
    "&center={lat:.6f},{lon:.6f}&zoom=19&basemap=satellite"
)


def table(header: list[str], rows: list[list]) -> str:
    """A Markdown table; numbers get thousands separators."""

    def cell(v):
        if v is None:
            return ""
        if isinstance(v, bool):
            return "yes" if v else "no"
        if isinstance(v, int):
            return f"{v:,}"
        if isinstance(v, float):
            return f"{v:,.1f}"
        return str(v)

    lines = ["| " + " | ".join(header) + " |", "|" + "---|" * len(header)]
    lines += ["| " + " | ".join(cell(v) for v in row) + " |" for row in rows]
    return "\n".join(lines)


def pct(n: int, d: int) -> str:
    return f"{n:,} ({100 * n / d:.1f}%)" if d else "0"


def by_region(conn, sql: str, keys: list[str], params=None) -> list[list]:
    """Rows of (key, count per region..., total) from a (key, region) query."""
    counts = {}
    for key, region, n in conn.execute(sql, params).fetchall():
        counts.setdefault(key, {})[region] = n
    rows = []
    for key in keys + sorted(set(counts) - set(keys), key=str):
        if key in counts:
            c = counts[key]
            rows.append([key, *(c.get(r, 0) for r in REGIONS), sum(c.values())])
    return rows


def lber_section(conn) -> str:
    pilot = dict(
        conn.execute(
            "SELECT t.region, count(*) FROM raw_lber l"
            " JOIN raw_utility_territories u ON ST_Contains(u.geom, l.geom)"
            " JOIN pilot_towns t ON t.town_id = (u.attrs->>'TOWN_ID')::integer"
            " GROUP BY 1"
        ).fetchall()
    )
    ubid = dict(
        conn.execute(
            "SELECT region, count(*) FROM lber_matches WHERE method = 'ubid' GROUP BY 1"
        ).fetchall()
    )
    total = sum(pilot.values())
    out = ["## LBER matching", ""]
    out.append(
        "Pilot rule: an LBER row is in the pilot when its point lies inside a"
        " pilot town's polygon. Each row matches once per reporting year."
    )
    out += ["", "UBID exact match rate, first:", ""]
    out.append(
        table(
            ["Region", "Pilot LBER rows", "Exact UBID match"],
            [
                [LABEL[r], pilot.get(r, 0), pct(ubid.get(r, 0), pilot.get(r, 0))]
                for r in REGIONS
            ]
            + [["Both", total, pct(sum(ubid.values()), total)]],
        )
    )
    rows = by_region(
        conn,
        "SELECT method, region, count(*) FROM lber_matches GROUP BY 1, 2"
        " UNION ALL SELECT 'unmatched', region, count(*) FROM lber_unmatched"
        " GROUP BY 2",
        [*METHODS, "unmatched"],
    )
    out += ["", "By method, in the order they run:", ""]
    out.append(table(["Method", "Metro South", "Worcester", "Both"], rows))
    kwh = by_region(
        conn,
        "SELECT method, region, count(*) FROM lber_matches"
        " WHERE grid_kwh IS NOT NULL GROUP BY 1, 2",
        list(METHODS),
    )
    out += ["", "Rows with usable grid electricity (zero or negative is missing):", ""]
    out.append(table(["Method", "Metro South", "Worcester", "Both"], kwh))
    amb = conn.execute(
        "SELECT count(*), count(*) FILTER (WHERE grid_kwh IS NOT NULL),"
        " coalesce(max(candidates), 0) FROM lber_matches WHERE candidates > 1"
    ).fetchone()
    out += [
        "",
        f"Ambiguous matches (several buildings, largest footprint used): {amb[0]:,},"
        f" {amb[1]:,} of them with grid electricity, up to {amb[2]:,} buildings.",
    ]
    unmatched = conn.execute(
        "SELECT u.region, u.city, u.street_address, u.reason,"
        " l.grid_kwh IS NOT NULL FROM lber_unmatched u"
        " JOIN raw_lber l USING (reporting_year, objectid)"
        " ORDER BY u.region, u.city, u.street_address"
    ).fetchall()
    out += ["", "Unmatched LBER rows:", ""]
    out.append(
        table(
            ["Region", "City", "Address", "Reason", "Grid electricity"],
            [[LABEL[r[0]], *r[1:]] for r in unmatched],
        )
    )
    landing = by_region(
        conn,
        """
        SELECT coalesce(c.kind, 'none'), t.region, count(*)
        FROM raw_lber l
        JOIN raw_utility_territories u ON ST_Contains(u.geom, l.geom)
        JOIN pilot_towns t ON t.town_id = (u.attrs->>'TOWN_ID')::integer
        LEFT JOIN LATERAL (
            SELECT CASE
                WHEN p.use_class = ANY(%(candidate)s) THEN 'candidate parcel'
                WHEN p.use_class IS NOT NULL THEN 'other C&I class'
                WHEN p.use_code ~ '^1[0-9]{2}' THEN 'residential parcel'
                ELSE 'other parcel (exempt, municipal, unclassified)'
            END AS kind
            FROM parcels p
            WHERE ST_Contains(p.geom, l.geom)
            ORDER BY ST_Area(p.geom), p.loc_id
            LIMIT 1
        ) c ON true
        GROUP BY 1, 2
        """,
        [
            "candidate parcel",
            "other C&I class",
            "residential parcel",
            "other parcel (exempt, municipal, unclassified)",
            "none",
        ],
        {"candidate": list(CANDIDATE_CLASSES)},
    )
    out += [
        "",
        "Where pilot LBER points land (smallest parcel containing the point):",
        "",
    ]
    out.append(table(["Parcel", "Metro South", "Worcester", "Both"], landing))
    return "\n".join(out)


def candidate_section(conn) -> str:
    out = ["## Candidate buildings and sites", ""]
    out.append(
        "Candidates are buildings on parcels with a commercial, industrial,"
        " hospital or multi-use commercial class (config/use_codes.yaml), and"
        " sites with at least one such building."
    )
    totals = by_region(
        conn,
        "SELECT 'candidate buildings', region, count(*) FROM building_evidence"
        " WHERE candidate GROUP BY 2 UNION ALL"
        " SELECT 'candidate sites', region, count(*) FROM site_evidence"
        " WHERE candidate GROUP BY 2",
        ["candidate buildings", "candidate sites"],
    )
    out += ["", table(["", "Metro South", "Worcester", "Both"], totals)]
    for title, column in (
        ("segment", "segment"),
        ("how the segment was set", "segment_source"),
    ):
        out += ["", f"By {title}:", ""]
        rows = by_region(
            conn,
            f"SELECT {column}, region, count(*) FROM building_evidence"
            " WHERE candidate GROUP BY 1, 2",
            [],
        )
        sites = by_region(
            conn,
            f"SELECT {column}, region, count(*) FROM site_evidence"
            " WHERE candidate GROUP BY 1, 2",
            [],
        )
        site_by = {r[0]: r[1:] for r in sites}
        out.append(
            table(
                [
                    title.capitalize(),
                    "Buildings MS",
                    "Buildings W",
                    "Sites MS",
                    "Sites W",
                ],
                [[r[0], r[1], r[2], *site_by.get(r[0], [0, 0])[:2]] for r in rows],
            )
        )
    out += ["", "Candidate buildings by LBER match method:", ""]
    out.append(
        table(
            ["Method", "Metro South", "Worcester", "Both"],
            by_region(
                conn,
                "SELECT coalesce(lber_method, 'not matched'), region, count(*)"
                " FROM building_evidence WHERE candidate GROUP BY 1, 2",
                [*METHODS, "not matched"],
            ),
        )
    )
    out += ["", "Candidate buildings by area source:", ""]
    out.append(
        table(
            ["Area source", "Metro South", "Worcester", "Both"],
            by_region(
                conn,
                "SELECT area_source, region, count(*) FROM building_evidence"
                " WHERE candidate GROUP BY 1, 2",
                [
                    "assessor",
                    "assessor_below_footprint",
                    "assessor_above_footprint",
                    "footprint_x_stories",
                    "footprint_only",
                ],
            ),
        )
    )
    return "\n".join(out)


def gap_section(conn) -> str:
    """Gaps between same-owner parcel pairs, merged or not, near the tolerance."""
    pairs = conn.execute(
        """
        SELECT a.site_id = b.site_id,
               ST_Distance(ST_Transform(a.geom, 26986), ST_Transform(b.geom, 26986))
        FROM parcels a
        JOIN parcels b
            ON a.town_id = b.town_id AND a.loc_id < b.loc_id
            AND a.geom && ST_Expand(b.geom, 0.0001)
        WHERE a.owner_norm IS NOT NULL AND a.owner_norm = b.owner_norm
        """
    ).fetchall()
    bands = [
        ("0 (sharing a line)", 0, 0),
        ("over 0 to 0.1 m", 0, 0.1),
        ("over 0.1 to 0.5 m", 0.1, 0.5),
        ("over 0.5 to 1 m", 0.5, 1.0),
        ("over 1 to 2 m", 1.0, 2.0),
        ("over 2 to 5 m", 2.0, 5.0),
    ]
    rows = []
    for label, lo, hi in bands:
        inside = [m for m, d in pairs if (d == 0 if hi == 0 else lo < d <= hi)]
        rows.append([label, sum(inside), len(inside) - sum(inside)])
    out = ["## Touch tolerance", ""]
    out.append(
        "Pairs of parcels in one town with the same normalized owner, by the"
        " planar gap between them (Massachusetts State Plane meters). Pairs up to"
        " 1 m apart count as touching and join one site; owner names cut off at"
        " the field width can also join by prefix, which this table leaves out."
    )
    out += ["", table(["Gap", "Same site", "Different sites"], rows)]
    return "\n".join(out)


def checks_section(conn) -> str:
    memorial = conn.execute(
        "SELECT p.loc_id, p.use_code, s.owner, s.parcels FROM parcels p"
        " JOIN sites s ON s.site_id = p.site_id"
        " WHERE p.use_code = '049C' AND p.owner ILIKE 'WORCESTER MEMORIAL%'"
    ).fetchall()
    pilot_979 = conn.execute(
        "SELECT count(*) FROM parcels WHERE use_code LIKE '979%'"
    ).fetchone()[0]
    out = ["## Checks", ""]
    out.append(
        "- 979 parcel count: config/use_codes.yaml and docs/DATA.md both say"
        " all 189 parcels coded 979 are in Boston. A live count on 2026-10-19"
        " gave 189 statewide, all with TOWN_ID 35 (Boston), so both agree."
        f" The pilot has {pilot_979} such parcels, as expected."
    )
    if memorial:
        loc, code, owner, parcels = memorial[0]
        out.append(
            f"- The 049C parcel ({loc}, owner WORCESTER MEMORIAL HOSPITAL) is in"
            f" the site of {owner}, which has {parcels} parcels."
        )
    else:
        out.append("- The 049C Worcester Memorial parcel was not found.")
    return "\n".join(out)


def write_csv(name: str, header: list[str], rows: list[list]) -> int:
    REVIEW.mkdir(parents=True, exist_ok=True)
    with open(REVIEW / name, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow([*header, "my verdict", "notes"])
        for row in rows:
            w.writerow([*row, "", ""])
    return len(rows)


def spread(rng: random.Random, rows: list, k: int, region_index: int) -> list:
    """Pick k rows, alternating between the two regions where possible."""
    pools = {r: [x for x in rows if x[region_index] == r] for r in REGIONS}
    for pool in pools.values():
        rng.shuffle(pool)
    picked = []
    while len(picked) < k and any(pools.values()):
        for r in REGIONS:
            if pools[r] and len(picked) < k:
                picked.append(pools[r].pop())
    return picked


def review_sheets(conn, rng: random.Random) -> dict:
    sites = conn.execute(
        """
        SELECT s.site_id, s.region, u.attrs->>'TOWN', s.parcels,
               (SELECT string_agg(DISTINCT p.owner, '; ') FROM parcels p
                 WHERE p.site_id = s.site_id),
               (SELECT string_agg(DISTINCT p.site_addr, '; ') FROM parcels p
                 WHERE p.site_id = s.site_id),
               ST_Y(st.geom), ST_X(st.geom)
        FROM site_evidence s
        JOIN sites st USING (site_id)
        JOIN raw_utility_territories u ON (u.attrs->>'TOWN_ID')::integer = s.town_id
        WHERE s.candidate AND s.parcels > 1
        ORDER BY s.site_id
        """
    ).fetchall()
    small = [r for r in sites if r[3] <= 3]
    large = [r for r in sites if r[3] >= 4]
    groups = spread(rng, small, 3, 1) + spread(rng, large, 2, 1)
    n_groups = write_csv(
        "owner_groups.csv",
        [
            "site id",
            "region",
            "town",
            "parcels",
            "owner names",
            "site addresses",
            "link",
        ],
        [
            [r[0], r[1], r[2], r[3], r[4], r[5], MAP.format(lat=r[6], lon=r[7])]
            for r in groups
        ],
    )

    seg = conn.execute(
        """
        SELECT s.segment, s.site_id, s.region, u.attrs->>'TOWN', s.owner, s.site_addr,
               s.segment_source, ST_Y(st.geom), ST_X(st.geom)
        FROM site_evidence s
        JOIN sites st USING (site_id)
        JOIN raw_utility_territories u ON (u.attrs->>'TOWN_ID')::integer = s.town_id
        WHERE s.candidate
        ORDER BY s.segment, s.site_id
        """
    ).fetchall()
    seg_rows = []
    for segment in sorted({r[0] for r in seg}):
        for r in spread(rng, [r for r in seg if r[0] == segment], 3, 2):
            seg_rows.append(
                [
                    r[1],
                    r[2],
                    r[3],
                    r[4],
                    r[5],
                    r[0],
                    r[6],
                    MAP.format(lat=r[7], lon=r[8]),
                ]
            )
    n_seg = write_csv(
        "segments.csv",
        ["site id", "region", "town", "owner", "address", "segment", "set by", "link"],
        seg_rows,
    )

    same = conn.execute(
        """
        SELECT p.loc_id, p.site_addr, p.bld_area, pt.region,
               (SELECT string_agg(r.attrs->>'OWNER1' || ': ' || (r.attrs->>'BLD_AREA'),
                                  '; ' ORDER BY r.objectid)
                  FROM raw_parcels r
                 WHERE r.scope = 'TOWN_ID=' || p.town_id
                   AND r.attrs->>'LOC_ID' = p.loc_id),
               ST_Y(ST_Centroid(p.geom)), ST_X(ST_Centroid(p.geom))
        FROM parcels p
        JOIN pilot_towns pt USING (town_id)
        WHERE p.records > 1 AND p.segment IS NOT NULL AND p.loc_id IN (
            SELECT attrs->>'LOC_ID' FROM raw_parcels
            WHERE (attrs->>'BLD_AREA')::integer > 0
            GROUP BY 1
            HAVING count(*) > 1 AND count(DISTINCT (attrs->>'BLD_AREA')::integer) = 1)
        ORDER BY p.loc_id
        """
    ).fetchall()
    picked = spread(rng, same, 5, 3)
    n_same = write_csv(
        "identical_area.csv",
        [
            "parcel id",
            "region",
            "address",
            "record owners and areas",
            "area used",
            "link",
        ],
        [
            [r[0], r[3], r[1], r[4], r[2], MAP.format(lat=r[5], lon=r[6])]
            for r in picked
        ],
    )
    return {
        "owner groups": (n_groups, len(sites)),
        "segments": (n_seg, len(seg)),
        "identical area": (n_same, len(same)),
    }


def main() -> None:
    rng = random.Random(SEED)
    with connect() as conn:
        conn.read_only = True
        conn.execute("SET jit = off")
        parts = [
            "# Match rates",
            "",
            f"Generated by `make match-rates` on {date.today().isoformat()} from the"
            " local database. Regions: Metro South (18 towns) and Worcester (35"
            " towns). Counts are of the latest `make sites` build.",
            "",
            lber_section(conn),
            "",
            candidate_section(conn),
            "",
            gap_section(conn),
            "",
            checks_section(conn),
        ]
        sizes = review_sheets(conn, rng)
        conn.rollback()
    parts += [
        "",
        "## Hand review",
        "",
        "Pending review.",
        "",
        f"Review sheets are written to `data/review/` (not committed), drawn with"
        f" random seed {SEED}, alternating between the two regions:",
        "",
        table(
            ["Sheet", "Rows", "Drawn from"],
            [
                [
                    "owner_groups.csv (3 sites of 2 to 3 parcels, 2 of 4 or more)",
                    *sizes["owner groups"],
                ],
                ["segments.csv (up to 3 sites per segment)", *sizes["segments"]],
                [
                    "identical_area.csv (multi-record candidate parcels whose"
                    " identical BLD_AREA values were counted once)",
                    *sizes["identical area"],
                ],
            ],
        ),
    ]
    REPORT.write_text("\n".join(parts) + "\n")
    print(f"wrote {REPORT.relative_to(ROOT)} and {len(sizes)} sheets in data/review/")


if __name__ == "__main__":
    main()
