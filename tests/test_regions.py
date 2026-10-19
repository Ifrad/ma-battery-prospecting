import pytest

from prospect.regions import load_regions


def write(tmp_path, towns, source="https://example.test"):
    lines = ["regions:", "  r:", f"    source: {source}", "    towns:"]
    lines += [f"      - {{name: T{t}, town_id: {t}}}" for t in towns]
    path = tmp_path / "regions.yaml"
    path.write_text("\n".join(lines))
    return path


def test_loads_towns_by_id(tmp_path):
    assert load_regions(write(tmp_path, [44, 348])) == {"r": {44: "T44", 348: "T348"}}


@pytest.mark.parametrize(
    "towns, source, message",
    [
        ([44, 44], "https://example.test", "duplicate"),
        ([0], "https://example.test", "bad town_id"),
        ([352], "https://example.test", "bad town_id"),
        ([44], "''", "no source"),
    ],
)
def test_rejects_bad_config(tmp_path, towns, source, message):
    with pytest.raises(ValueError, match=message):
        load_regions(write(tmp_path, towns, source))


def test_repo_regions_include_pilot_cities():
    regions = load_regions()
    assert regions["metro_south"][44] == "BROCKTON"
    assert regions["worcester"][348] == "WORCESTER"
    all_ids = [t for towns in regions.values() for t in towns]
    assert len(all_ids) == len(set(all_ids)), "a town is in two regions"
