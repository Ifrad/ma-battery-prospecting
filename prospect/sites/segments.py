"""Assign segments to candidate parcels from config/segments.yaml."""

import re
from pathlib import Path

import yaml

from prospect.sites import group

CONFIG = Path(__file__).resolve().parents[2] / "config" / "segments.yaml"

# Parcel classes from config/use_codes.yaml that make a parcel a candidate.
CANDIDATE_CLASSES = (
    "commercial_industrial",
    "hospital",
    "hospital_boston",
    "mixed_commercial_industrial",
)


def load_config(path: Path = CONFIG) -> dict:
    return yaml.safe_load(path.read_text())


def segment(
    code: str | None,
    owner: str | None,
    town_id: int,
    config: dict,
    *,
    site_area_sqft: float | None = None,
    food_min_area_sqft: float | None = None,
):
    """(segment, how) for a candidate parcel; how is use_code, owner_keyword
    or default. Vacant land (a fourth character V) gets no segment."""
    code = (code or "").strip().upper()
    if len(code) == 4 and code.endswith("V"):
        return None, None
    dor = code[:3]
    name = (
        " " + " ".join(re.sub(r"[^A-Z0-9]+", " ", (owner or "").upper()).split()) + " "
    )
    for rule in config["rules"]:
        if "town_ids" in rule and town_id not in rule["town_ids"]:
            continue
        if dor and dor in rule.get("use_codes", []):
            return rule["segment"], "use_code"
        if not any(" " + k + " " in name for k in rule.get("owner_keywords", [])):
            continue
        if any(" " + k + " " in name for k in rule.get("exclude_owner_keywords", [])):
            continue
        if rule["segment"] == "food_production" and not (
            dor.isdigit() and 400 <= int(dor) <= 499
        ):
            if food_min_area_sqft is None:
                food_min_area_sqft = group.load_config()["food_keyword_min_area_sqft"][
                    "value"
                ]
            if site_area_sqft is None or site_area_sqft < food_min_area_sqft:
                continue
        return rule["segment"], "owner_keyword"
    return "generic", "default"


def assign(conn, config: dict) -> None:
    """Set parcels.segment and segment_source on candidate parcels."""
    rows = conn.execute(
        "SELECT p.loc_id, p.use_code, p.owner, p.town_id, s.area_sqft FROM parcels p"
        " LEFT JOIN sites s USING (site_id) WHERE p.use_class = ANY(%s)",
        (list(CANDIDATE_CLASSES),),
    ).fetchall()
    conn.execute(
        "CREATE TEMP TABLE parcel_segment (loc_id text, segment text,"
        " segment_source text) ON COMMIT DROP"
    )
    threshold = group.load_config()["food_keyword_min_area_sqft"]["value"]
    with conn.cursor().copy("COPY parcel_segment FROM STDIN") as copy:
        for loc_id, code, owner, town_id, area in rows:
            copy.write_row(
                (
                    loc_id,
                    *segment(
                        code,
                        owner,
                        town_id,
                        config,
                        site_area_sqft=area,
                        food_min_area_sqft=threshold,
                    ),
                )
            )
    conn.execute(
        "UPDATE parcels p SET segment = s.segment, segment_source = s.segment_source"
        " FROM parcel_segment s WHERE s.loc_id = p.loc_id"
    )
