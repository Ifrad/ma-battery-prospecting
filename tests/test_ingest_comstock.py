import csv
import io
import tarfile
from datetime import datetime, timedelta

import httpx
import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from prospect.ingest import comstock as cs
from prospect.ingest.client import Client


def metadata_tar(rows: list[tuple]) -> bytes:
    """A gzipped tar holding one CSV, like the ComStock county files."""
    text = io.StringIO()
    w = csv.writer(text)
    w.writerow(["bldg_id", "in.comstock_building_type", "in.sqft..ft2"])
    w.writerows(rows)
    data = text.getvalue().encode()
    out = io.BytesIO()
    with tarfile.open(fileobj=out, mode="w:gz") as tar:
        info = tarfile.TarInfo("county.csv")
        info.size = len(data)
        tar.addfile(info, io.BytesIO(data))
    return out.getvalue()


def profile(step_minutes: int = 15, n: int = cs.STEPS_PER_YEAR) -> bytes:
    start = datetime(2018, 1, 1, 0, 15)
    table = pa.table(
        {
            "timestamp": [
                start + timedelta(minutes=step_minutes * i) for i in range(n)
            ],
            "out.electricity.total.energy_consumption": [1.0] * n,
        }
    )
    out = io.BytesIO()
    pq.write_table(table, out)
    return out.getvalue()


def test_sample_takes_one_per_area_stratum_and_repeats_with_the_seed():
    rows = [
        {"bldg_id": i, "building_type": "Office", "sqft": float(i)} for i in range(100)
    ]
    rows += [
        {"bldg_id": 500 + i, "building_type": "Hospital", "sqft": 1.0} for i in range(3)
    ]
    picked = cs.sample(rows, 10, seed=7)
    offices = [r["bldg_id"] for r in picked if r["building_type"] == "Office"]
    assert [i // 10 for i in offices] == list(range(10))
    assert [r["bldg_id"] for r in picked if r["building_type"] == "Hospital"] == [
        500,
        501,
        502,
    ]
    assert cs.sample(rows, 10, seed=7) == picked


def test_read_metadata_reads_tar_files_and_keeps_each_building_once(tmp_path):
    a, b = tmp_path / "a.csv.gz", tmp_path / "b.csv.gz"
    a.write_bytes(metadata_tar([(1, "Warehouse", "5000.0"), (2, "Hospital", "90000")]))
    b.write_bytes(metadata_tar([(2, "Hospital", "90000")]))
    assert cs.read_metadata([a, b]) == [
        {"bldg_id": 1, "building_type": "Warehouse", "sqft": 5000.0},
        {"bldg_id": 2, "building_type": "Hospital", "sqft": 90000.0},
    ]


def test_check_15_minute_rejects_hourly_data(tmp_path):
    good, bad = tmp_path / "good.parquet", tmp_path / "bad.parquet"
    good.write_bytes(profile())
    bad.write_bytes(profile(step_minutes=60, n=8760))
    cs.check_15_minute(good)
    with pytest.raises(ValueError, match="expected 35040 rows"):
        cs.check_15_minute(bad)


def test_run_records_provenance_and_skips_files_on_disk(db, tmp_path):
    cfg = cs.load_config()
    cfg["sample"]["per_type"] = 1
    listing = (
        "<ListBucketResult><Key>x/state=MA/county=1/MA_1_upgrade0_basic.csv.gz</Key>"
        "<Key>x/state=MA/county=1/MA_1_upgrade1_basic.csv.gz</Key></ListBucketResult>"
    )
    requests = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request.url.path)
        if "list-type" in str(request.url):
            return httpx.Response(200, text=listing)
        if request.url.path.endswith(".csv.gz"):
            return httpx.Response(200, content=metadata_tar([(7, "Warehouse", "100")]))
        return httpx.Response(200, content=profile())

    def go():
        client = Client(delay=0, transport=httpx.MockTransport(handler))
        return cs.run(db, client, cfg, data=tmp_path)

    assert go()["profiles"] == 1
    first = len(requests)
    assert go()["profiles"] == 1
    assert len(requests) == first + 1  # only the listing again
    assert (tmp_path / "timeseries" / "7-0.parquet").exists()
    assert db.execute(
        "SELECT count(*), min(rows) FROM ingest_runs"
        " WHERE source = 'comstock' AND status = 'succeeded'"
    ).fetchone() == (2, 1)
