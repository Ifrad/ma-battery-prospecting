"""Classify assessor use codes with config/use_codes.yaml."""

from pathlib import Path

import yaml

CONFIG = Path(__file__).resolve().parent.parent / "config" / "use_codes.yaml"


def load(path: Path = CONFIG) -> dict:
    return yaml.safe_load(path.read_text())


def classify(code: str | None, town_id: int, config: dict) -> str | None:
    """The class of one parcel's use code, or None if it is not a candidate."""
    code = (code or "").strip().upper()
    if len(code) < 3 or not code[:3].isdigit():
        return None
    if len(code) == 4 and code[3] == config["normalize"]["vacant_suffix"]:
        return None
    dor = code[:3]
    for name, rule in config["classes"].items():
        if "town_ids" in rule and town_id not in rule["town_ids"]:
            continue
        if dor in rule.get("codes", []):
            return name
        if any(dor.startswith(p) for p in rule.get("prefixes", [])):
            return name
        if any(lo <= int(dor) <= hi for lo, hi in rule.get("ranges", [])):
            return name
    return None
