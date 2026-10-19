"""Pilot regions from config/regions.yaml: chamber territory to towns."""

from pathlib import Path

import yaml

CONFIG = Path(__file__).resolve().parent.parent / "config" / "regions.yaml"


def load_regions(path: Path = CONFIG) -> dict[str, dict[int, str]]:
    """Map region name to {town_id: town name}. Raises ValueError if malformed."""
    regions = yaml.safe_load(path.read_text())["regions"]
    result = {}
    for name, region in regions.items():
        if not region.get("source"):
            raise ValueError(f"{name}: no source URL")
        towns = {}
        for town in region["towns"]:
            town_id = town["town_id"]
            if not 1 <= town_id <= 351:
                raise ValueError(f"{name}: bad town_id {town_id}")
            if town_id in towns:
                raise ValueError(f"{name}: duplicate town_id {town_id}")
            towns[town_id] = town["name"]
        result[name] = towns
    return result
