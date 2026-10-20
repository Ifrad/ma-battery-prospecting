import random

from prospect.sites.match_rates import spread, table


def test_table_formats_numbers_and_blanks():
    text = table(["A", "B"], [["x", 1234], ["y", None], ["z", 2.25]])
    assert text.splitlines() == [
        "| A | B |",
        "|---|---|",
        "| x | 1,234 |",
        "| y |  |",
        "| z | 2.2 |",
    ]


def test_spread_alternates_regions_and_repeats_with_the_seed():
    rows = [(i, "metro_south") for i in range(5)] + [
        (i, "worcester") for i in range(5, 7)
    ]
    first = spread(random.Random(1), list(rows), 5, 1)
    assert [r[1] for r in first] == [
        "metro_south",
        "worcester",
        "metro_south",
        "worcester",
        "metro_south",
    ]
    assert spread(random.Random(1), list(rows), 5, 1) == first
