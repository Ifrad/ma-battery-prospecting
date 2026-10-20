import pytest

from prospect import cli
from prospect.priors import config


def test_real_config_is_clean():
    assert config.check(config.load_all()) == []


@pytest.mark.parametrize(
    "node,problem",
    [
        ({"value": 1, "status": "sourced"}, "sourced without a source"),
        (
            {"value": 1, "status": "placeholder", "test": "t", "replace": "r"},
            "placeholder without a note",
        ),
        (
            {"value": 1, "status": "placeholder", "note": "n", "replace": "r"},
            "placeholder without a test",
        ),
        ({"value": 1, "status": "guess", "note": "x"}, "is not one of"),
        (
            {
                "address_status": "placeholder",
                "address_test": "t",
                "address_replace": "r",
            },
            "placeholder without a note",
        ),
    ],
)
def test_check_finds_missing_status_details(node, problem):
    (message,) = config.check({"f": {"a": node}})
    assert problem in message


def test_entries_walk_lists_and_prefixed_statuses():
    tree = {
        "rules": [
            {
                "segment": "laundry",
                "status": "placeholder",
                "note": "n",
                "test": "t",
                "replace": "r",
            }
        ],
        "match": {
            "status": "sourced",
            "source": "s",
            "address_status": "placeholder",
            "address_note": "m",
            "address_test": "t",
            "address_replace": "r",
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


def test_assumptions_page_is_current():
    from prospect.priors import assumptions

    assert assumptions.PAGE.read_text() == assumptions.render(config.load()), (
        "docs/ASSUMPTIONS.md is stale; run make assumptions"
    )


def test_check_rejects_a_value_outside_its_range():
    node = {
        "value": 0.99,
        "range": {"low": 0.6, "high": 0.95},
        "status": "placeholder",
        "note": "n",
        "test": "t",
        "replace": "r",
    }
    (message,) = config.check({"f": {"a": node}})
    assert "outside its range" in message
    assert config.summary(dict(node, value=0.8), "") == "0.8 (range 0.6 to 0.95)"
