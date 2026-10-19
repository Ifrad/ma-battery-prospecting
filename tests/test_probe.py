import json
from pathlib import Path

import httpx

from prospect.ingest.client import Client
from prospect.ingest.probe import probe_arcgis, probe_ckan, report
from prospect.ingest.sources import Source

FIXTURES = Path(__file__).parent / "fixtures" / "probe"


def fixture(name):
    return json.loads((FIXTURES / f"{name}.json").read_text())


def client_for(handler):
    return Client(transport=httpx.MockTransport(handler), delay=0)


def arcgis_handler(request):
    if request.url.path.endswith("/query"):
        if request.url.params.get("returnCountOnly") == "true":
            return httpx.Response(200, json=fixture("arcgis_count"))
        return httpx.Response(200, json=fixture("arcgis_query"))
    return httpx.Response(200, json=fixture("arcgis_layer"))


ARCGIS = Source("parcels", "arcgis", "https://example.test/FeatureServer/0")
CKAN = Source("berdo", "ckan", "https://example.test/datastore_search", "abc")


def test_probe_arcgis_reads_fields_count_and_sample():
    result = probe_arcgis(client_for(arcgis_handler), ARCGIS)
    assert result["rows"] == fixture("arcgis_count")["count"]
    assert result["page_size"] == 2000
    assert ("OWNER1", "String") in result["fields"]
    assert ("BLD_AREA", "Integer") in result["fields"]
    assert result["sample"][0]["SITE_ADDR"] == "920 W CHESTNUT ST"


def test_probe_arcgis_raises_on_service_error():
    def handler(request):
        return httpx.Response(200, json={"error": {"code": 400, "message": "bad"}})

    try:
        probe_arcgis(client_for(handler), ARCGIS)
    except RuntimeError as exc:
        assert "parcels" in str(exc)
    else:
        raise AssertionError("expected RuntimeError")


def test_probe_ckan_drops_internal_id():
    def handler(request):
        assert request.url.params["resource_id"] == "abc"
        return httpx.Response(200, json=fixture("ckan_search"))

    result = probe_ckan(client_for(handler), CKAN)
    names = [name for name, _ in result["fields"]]
    assert "_id" not in names
    assert "Electricity Usage (kWh)" in names
    assert result["rows"] == fixture("ckan_search")["result"]["total"]


def test_report_shows_first_non_empty_sample():
    text = report(
        {
            "name": "x",
            "url": "u",
            "rows": 2,
            "page_size": None,
            "geometry": None,
            "fields": [("A", "String")],
            "sample": [{"A": None}, {"A": "second"}],
        }
    )
    assert "second" in text
