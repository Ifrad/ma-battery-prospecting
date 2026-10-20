"""Load config/*.yaml and check that every value says where it comes from.

A value is any mapping with a status key (or a prefixed one such as
address_status). Its status is sourced, with a source, or placeholder,
with a note saying why.
"""

from pathlib import Path

import yaml

CONFIG_DIR = Path(__file__).resolve().parents[2] / "config"
STATUSES = ("sourced", "placeholder")
META = ("status", "source", "note")


def load_all(directory: Path = CONFIG_DIR) -> dict[str, object]:
    """Every config file by name, without the .yaml suffix."""
    return {
        p.stem: yaml.safe_load(p.read_text()) for p in sorted(directory.glob("*.yaml"))
    }


def entries(tree, path: str = ""):
    """Yield (path, prefix, mapping) for each value with a status."""
    if isinstance(tree, dict):
        for key in tree:
            if isinstance(key, str) and key.endswith("status"):
                prefix = key[: -len("status")]
                label = f"{path} ({prefix.rstrip('_')})" if prefix else path
                yield label, prefix, tree
        for key, child in tree.items():
            yield from entries(child, f"{path}.{key}" if path else str(key))
    elif isinstance(tree, list):
        for i, child in enumerate(tree):
            label = i
            if isinstance(child, dict):
                label = child.get("name") or child.get("segment") or i
            yield from entries(child, f"{path}[{label}]")


def summary(node: dict, prefix: str) -> str:
    """The value itself, short: `value` if given, else the other scalar fields."""
    if prefix + "value" in node:
        return str(node[prefix + "value"])
    if prefix:
        return ""
    parts = []
    for key, v in node.items():
        if key.endswith(META):
            continue
        if isinstance(v, list):
            parts.append(f"{key}: {len(v)} items")
        elif not isinstance(v, dict):
            parts.append(f"{key}={v}")
    return ", ".join(parts)


def check(configs: dict) -> list[str]:
    """Problems with status, source or note, as messages; empty when clean."""
    problems = []
    for name, tree in configs.items():
        for path, prefix, node in entries(tree):
            where = f"{name}: {path or '(top)'}"
            status = node[prefix + "status"]
            if status not in STATUSES:
                problems.append(f"{where}: status {status!r} is not one of {STATUSES}")
            elif status == "sourced" and not node.get(prefix + "source"):
                problems.append(f"{where}: sourced without a source")
            elif status == "placeholder" and not node.get(prefix + "note"):
                problems.append(f"{where}: placeholder without a note")
    return problems


def load(directory: Path = CONFIG_DIR) -> dict:
    """All config, raising ValueError if any value lacks its status details."""
    configs = load_all(directory)
    problems = check(configs)
    if problems:
        raise ValueError("config problems:\n" + "\n".join(problems))
    return configs


def placeholders(configs: dict) -> list[tuple[str, str, str, str]]:
    """(file, path, value, note) for every placeholder."""
    return [
        (
            name,
            path or "(top)",
            summary(node, prefix),
            " ".join(node[prefix + "note"].split()),
        )
        for name, tree in configs.items()
        for path, prefix, node in entries(tree)
        if node[prefix + "status"] == "placeholder"
    ]
