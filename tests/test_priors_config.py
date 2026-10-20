import pytest

from prospect import cli
from prospect.priors import config


def test_real_config_is_clean():
    assert config.check(config.load_all()) == []


@pytest.mark.parametrize(
    "node,problem",
    [
        ({"value": 1, "status": "sourced"}, "sourced without a source"),
        ({"value": 1, "status": "placeholder"}, "placeholder without a note"),
        ({"value": 1, "status": "guess", "note": "x"}, "is not one of"),
        ({"address_status": "placeholder"}, "placeholder without a note"),
    ],
)
def test_check_finds_missing_status_details(node, problem):
    (message,) = config.check({"f": {"a": node}})
    assert problem in message


def test_entries_walk_lists_and_prefixed_statuses():
    tree = {
        "rules": [{"segment": "laundry", "status": "placeholder", "note": "n"}],
        "match": {
            "status": "sourced",
            "source": "s",
            "address_status": "placeholder",
            "address_note": "m",
            "words": {"ROAD": "RD"},
        },
    }
    assert config.placeholders({"f": tree}) == [
        ("f", "rules[laundry]", "segment=laundry", "n"),
        ("f", "match (address)", "", "m"),
    ]


def test_load_raises_on_problems(tmp_path):
    (tmp_path / "x.yaml").write_text("a: {value: 1, status: sourced}\n")
    with pytest.raises(ValueError, match="sourced without a source"):
        config.load(tmp_path)


def test_cli_lists_placeholders(capsys):
    assert cli.main(["priors", "--list-placeholders"]) == 0
    out = capsys.readouterr().out
    assert "placeholders in config/" in out
    assert "sites.yaml touch_tolerance_m = 1.0" in out
