from prospect.ingest.run import Load, plan
from prospect.ingest.sources import SOURCES


def test_statewide_sources_once_and_town_sources_per_town():
    loads = plan({"a": {44: "BROCKTON"}, "b": {348: "WORCESTER"}})
    assert loads == [
        Load("statewide", "", "utility_territories", "raw_utility_territories", "1=1"),
        Load("a", "BROCKTON", "parcels", "raw_parcels", "TOWN_ID=44"),
        Load("a", "BROCKTON", "footprints", "raw_footprints", "TOWN_ID=44"),
        Load("b", "WORCESTER", "parcels", "raw_parcels", "TOWN_ID=348"),
        Load("b", "WORCESTER", "footprints", "raw_footprints", "TOWN_ID=348"),
    ]


def test_every_planned_source_has_a_url():
    names = {s.name for s in SOURCES}
    assert {load.source for load in plan({"a": {1: "X"}})} <= names
