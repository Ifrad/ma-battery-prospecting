import json
import re
from pathlib import Path

import httpx
import pytest

from prospect.ingest import arcgis
from prospect.ingest.client import Client

URL = "https://example.test/FeatureServer/0"
FEATURES = json.loads(
    (Path(__file__).parent / "fixtures" / "arcgis" / "parcels.geojson").read_text()
)["features"]


class FakeLayer:
    """Serves features two per page by object id, like a paged ArcGIS layer."""

    def __init__(self, features, fail_after=None):
        self.features = features
        self.fail_after = fail_after
        self.afters = []

    def __call__(self, request):
        params = request.url.params
        if not request.url.path.endswith("/query"):
            return httpx.Response(200, json={"objectIdField": "OBJECTID"})
        if params.get("returnCountOnly") == "true":
            return httpx.Response(200, json={"count": len(self.features)})
        after = int(re.search(r"OBJECTID > (\d+)", params["where"]).group(1))
        self.afters.append(after)
        if self.fail_after is not None and after >= self.fail_after:
            return httpx.Response(500)
        page = [f for f in self.features if f["id"] > after][:2]
        return httpx.Response(200, json={"type": "FeatureCollection", "features": page})


def client(layer):
    return Client(transport=httpx.MockTransport(layer), delay=0, sleep=lambda s: None)


def test_fetch_pages_follows_object_ids_until_empty():
    layer = FakeLayer(FEATURES)
    pages = list(arcgis.fetch_pages(client(layer), URL, "TOWN_ID=44", "OBJECTID"))
    assert [len(p) for p in pages] == [2, 1]
    assert layer.afters == [0, FEATURES[1]["id"], FEATURES[2]["id"]]


def test_service_error_raises():
    def handler(request):
        return httpx.Response(200, json={"error": {"code": 400, "message": "bad"}})

    with pytest.raises(RuntimeError, match="bad"):
        arcgis.count(client(handler), URL, "1=1")


def load(db, layer):
    return arcgis.load(db, client(layer), "parcels", URL, "raw_parcels", "TOWN_ID=44")


def runs(db):
    return db.execute(
        "SELECT status, rows, source_rows, sha256 FROM ingest_runs ORDER BY id"
    ).fetchall()


def test_load_twice_gives_same_rows_and_hash(db):
    first = load(db, FakeLayer(FEATURES))
    second = load(db, FakeLayer(FEATURES))
    assert first["rows"] == second["rows"] == 3
    assert db.execute("SELECT count(*) FROM raw_parcels").fetchone()[0] == 3
    (s1, r1, n1, h1), (s2, r2, n2, h2) = runs(db)
    assert s1 == s2 == "succeeded"
    assert r1 == n1 == 3
    assert h1 == h2 and len(h1) == 64
    owner = db.execute(
        "SELECT attrs->>'OWNER1' FROM raw_parcels WHERE objectid = %s",
        (FEATURES[0]["id"],),
    ).fetchone()[0]
    assert owner == FEATURES[0]["properties"]["OWNER1"]


def test_failed_load_resumes_after_last_stored_id(db):
    with pytest.raises(httpx.HTTPStatusError):
        load(db, FakeLayer(FEATURES, fail_after=FEATURES[1]["id"]))
    assert runs(db)[0][0] == "failed"
    assert db.execute("SELECT count(*) FROM raw_parcels").fetchone()[0] == 2

    layer = FakeLayer(FEATURES)
    result = load(db, layer)
    assert result["resumed"] and result["rows"] == 3
    assert layer.afters[0] == FEATURES[1]["id"]
    assert [r[0] for r in runs(db)] == ["succeeded"]


def test_lber_zero_or_negative_electricity_is_missing(db):
    field = "Total_Electricity_Use_Purchased_From_Grid__kBtu_"
    features = [
        {"type": "Feature", "id": i, "geometry": None, "properties": {field: kbtu}}
        for i, kbtu in [(1, 0), (2, -41532.8), (3, 341214)]
    ]
    arcgis.load(
        db,
        client(FakeLayer(features)),
        "lber",
        URL,
        "raw_lber",
        "1=1",
        {"reporting_year": 2024},
    )
    rows = db.execute(
        "SELECT objectid, reporting_year, grid_kwh FROM raw_lber ORDER BY 1"
    ).fetchall()
    assert rows == [(1, 2024, None), (2, 2024, None), (3, 2024, pytest.approx(1e5))]


def test_lber_reporting_years_sit_side_by_side(db):
    field = "Total_Electricity_Use_Purchased_From_Grid__kBtu_"

    def release(ids):
        return FakeLayer(
            [
                {"type": "Feature", "id": i, "geometry": None, "properties": {field: 1}}
                for i in ids
            ]
        )

    def load_year(year, ids):
        url = f"https://example.test/{year}/FeatureServer/0"
        arcgis.load(
            db,
            client(release(ids)),
            "lber",
            url,
            "raw_lber",
            "1=1",
            {"reporting_year": year},
        )

    def years():
        return db.execute(
            "SELECT reporting_year, count(*) FROM raw_lber GROUP BY 1 ORDER BY 1"
        ).fetchall()

    load_year(2024, [1, 2, 3])
    load_year(2025, [1, 2])  # a new release reuses object ids
    assert years() == [(2024, 3), (2025, 2)]
    load_year(2024, [1, 2])  # reloading one year leaves the other alone
    assert years() == [(2024, 2), (2025, 2)]


def test_rows_gone_from_source_are_removed(db):
    load(db, FakeLayer(FEATURES))
    result = load(db, FakeLayer(FEATURES[:2]))
    assert result["rows"] == 2
    ids = [r[0] for r in db.execute("SELECT objectid FROM raw_parcels ORDER BY 1")]
    assert ids == [FEATURES[0]["id"], FEATURES[1]["id"]]
