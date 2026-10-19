import pytest

from prospect.use_codes import classify, load

CONFIG = load()
WORCESTER, BOSTON = 348, 35


@pytest.mark.parametrize(
    "code, town, expected",
    [
        ("316", WORCESTER, "commercial_industrial"),
        ("3160", WORCESTER, "commercial_industrial"),
        ("4020", WORCESTER, "commercial_industrial"),
        ("305", WORCESTER, "commercial_industrial"),
        ("955", WORCESTER, "hospital"),
        ("9550", WORCESTER, "hospital"),
        ("955C", WORCESTER, "hospital"),
        ("955V", WORCESTER, None),  # vacant land, never a hospital
        ("316V", WORCESTER, None),
        ("979", BOSTON, "hospital_boston"),
        ("979", WORCESTER, None),  # 979 is a Boston code only
        ("031", WORCESTER, "mixed_commercial_industrial"),
        ("049C", WORCESTER, "mixed_commercial_industrial"),
        ("013", WORCESTER, None),  # mixed use, primarily residential
        ("9050", WORCESTER, "charitable_former"),
        ("104", WORCESTER, None),
        ("299", WORCESTER, None),
        ("500", WORCESTER, None),
        ("930V", WORCESTER, None),
        (None, WORCESTER, None),
        ("", WORCESTER, None),
        ("ABC", WORCESTER, None),
    ],
)
def test_classify(code, town, expected):
    assert classify(code, town, CONFIG) == expected


def test_every_class_has_status_and_source_or_note():
    for name, rule in CONFIG["classes"].items():
        assert rule["status"] in {"sourced", "placeholder"}, name
        assert rule.get("source" if rule["status"] == "sourced" else "note"), name
