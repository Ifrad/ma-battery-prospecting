from prospect.ingest.run import Load, plan, summarize
from prospect.ingest.sources import SOURCES


def test_summary_totals_by_region_and_source_and_lists_problems():
    a = Load("metro_south", "AVON", "parcels", "raw_parcels", "TOWN_ID=18")
    b = Load("metro_south", "BROCKTON", "parcels", "raw_parcels", "TOWN_ID=44")
    c = Load("metro_south", "BROCKTON", "footprints", "raw_footprints", "TOWN_ID=44")
    text = summarize(
        [
            (a, {"rows": 10, "source_rows": 10}),
            (b, {"rows": 20, "source_rows": 21}),
            (c, RuntimeError("timeout")),
        ]
    )
    assert "metro_south  parcels                  2        30        31" in text
    assert "Count mismatches: 1" in text
    assert "metro_south BROCKTON parcels: loaded 20, source has 21" in text
    assert "Failures: 1" in text
    assert "metro_south BROCKTON footprints: RuntimeError: timeout" in text


def test_statewide_sources_once_and_town_sources_per_town():
    loads = plan({"a": {44: "BROCKTON"}, "b": {348: "WORCESTER"}})
    assert loads == [
        Load("statewide", "", "utility_territories", "raw_utility_territories", "1=1"),
        Load("statewide", "", "lber", "raw_lber", "1=1", {"reporting_year": 2024}),
        Load("a", "BROCKTON", "parcels", "raw_parcels", "TOWN_ID=44"),
        Load("a", "BROCKTON", "footprints", "raw_footprints", "TOWN_ID=44"),
        Load("b", "WORCESTER", "parcels", "raw_parcels", "TOWN_ID=348"),
        Load("b", "WORCESTER", "footprints", "raw_footprints", "TOWN_ID=348"),
    ]


def test_every_planned_source_has_a_url():
    names = {s.name for s in SOURCES}
    assert {load.source for load in plan({"a": {1: "X"}})} <= names
