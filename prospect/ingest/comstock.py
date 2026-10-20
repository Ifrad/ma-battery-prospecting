"""Download a sample of ComStock 15-minute building profiles for Massachusetts.

Usage: python -m prospect.ingest.comstock

Reads the county metadata files, picks about config sample.per_type buildings
per building type spread across floor area (fixed seed), and saves their
profiles under data/comstock/. Files already on disk are not fetched again,
so a rerun only fills gaps. Each run is recorded in ingest_runs.
"""

import csv
import hashlib
import io
import random
import re
import sys
import tarfile
from itertools import pairwise
from pathlib import Path

import pyarrow.parquet as pq
import yaml

from prospect.db import connect
from prospect.ingest.client import Client

ROOT = Path(__file__).resolve().parents[2]
CONFIG = ROOT / "config" / "comstock.yaml"
DATA = ROOT / "data" / "comstock"
STEP_SECONDS = 15 * 60
STEPS_PER_YEAR = 365 * 24 * 4


def load_config(path: Path = CONFIG) -> dict:
    return yaml.safe_load(path.read_text())


def release_url(cfg: dict) -> str:
    d = cfg["dataset"]
    return f"{d['base_url']}/{d['release']}"


def list_keys(client: Client, bucket_url: str, prefix: str) -> list[str]:
    """Every object key under prefix, from the public S3 listing (paged)."""
    keys, token = [], None
    while True:
        params = {"list-type": "2", "prefix": prefix}
        if token:
            params["continuation-token"] = token
        text = client.get(bucket_url, params).text
        keys += re.findall(r"<Key>([^<]*)</Key>", text)
        m = re.search(r"<NextContinuationToken>([^<]*)</NextContinuationToken>", text)
        if not m:
            return keys
        token = m.group(1)


def fetch(client: Client, url: str, path: Path) -> bool:
    """Save url to path unless it is already there. True if downloaded."""
    if path.exists() and path.stat().st_size > 0:
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".part")
    tmp.write_bytes(client.get(url).content)
    tmp.rename(path)
    return True


def read_metadata(paths: list[Path]) -> list[dict]:
    """One (bldg_id, building_type, sqft) row per building from the county
    metadata files. Each .csv.gz is a gzipped tar holding one CSV, and a
    building can appear in several counties, so ids are kept once."""
    rows = {}
    for path in paths:
        with tarfile.open(path, "r:gz") as tar:
            member = next(m for m in tar if m.isfile())
            text = io.TextIOWrapper(tar.extractfile(member), newline="")
            for r in csv.DictReader(text):
                rows.setdefault(
                    int(r["bldg_id"]),
                    {
                        "bldg_id": int(r["bldg_id"]),
                        "building_type": r["in.comstock_building_type"],
                        "sqft": float(r["in.sqft..ft2"]),
                    },
                )
    return list(rows.values())


def sample(rows: list[dict], per_type: int, seed: int) -> list[dict]:
    """Per building type, one random building from each of per_type equal
    count floor-area strata (all of them when a type has fewer)."""
    rng = random.Random(seed)
    picked = []
    for btype in sorted({r["building_type"] for r in rows}):
        ordered = sorted(
            (r for r in rows if r["building_type"] == btype),
            key=lambda r: (r["sqft"], r["bldg_id"]),
        )
        if len(ordered) <= per_type:
            picked += ordered
            continue
        for i in range(per_type):
            lo = i * len(ordered) // per_type
            hi = (i + 1) * len(ordered) // per_type
            picked.append(ordered[rng.randrange(lo, hi)])
    return picked


def check_15_minute(path: Path) -> None:
    """Raise ValueError unless the profile is one year of 15-minute steps."""
    stamps = pq.read_table(path, columns=["timestamp"]).column(0).to_pylist()
    steps = {(b - a).total_seconds() for a, b in pairwise(stamps)}
    if steps != {STEP_SECONDS} or len(stamps) != STEPS_PER_YEAR:
        raise ValueError(
            f"{path.name}: {len(stamps)} rows with steps {sorted(steps)} s,"
            f" expected {STEPS_PER_YEAR} rows of {STEP_SECONDS} s"
        )


def digest(paths: list[Path]) -> str:
    """One sha256 over each file's name and its own sha256, in name order."""
    h = hashlib.sha256()
    for p in sorted(paths):
        h.update(f"{p.name} {hashlib.sha256(p.read_bytes()).hexdigest()}\n".encode())
    return h.hexdigest()


def write_sample(picked: list[dict], path: Path) -> None:
    buf = io.StringIO()
    w = csv.DictWriter(buf, ["bldg_id", "building_type", "sqft"], lineterminator="\n")
    w.writeheader()
    w.writerows(picked)
    path.write_text(buf.getvalue())


def run(conn, client: Client, cfg: dict, data: Path = DATA) -> dict:
    d = cfg["dataset"]
    base = release_url(cfg)
    bucket_url, prefix = base.split(".amazonaws.com/")
    bucket_url += ".amazonaws.com/"
    scope = (
        f"state={d['state']} upgrade={d['upgrade']}"
        f" per_type={cfg['sample']['per_type']} seed={cfg['sample']['seed']}"
    )
    run_id = conn.execute(
        "INSERT INTO ingest_runs (source, url, scope) VALUES ('comstock', %s, %s)"
        " RETURNING id",
        (base, scope),
    ).fetchone()[0]
    try:
        meta_prefix = (
            f"{prefix}/metadata_and_annual_results/by_state_and_county/basic/csv/"
            f"state={d['state']}/"
        )
        suffix = f"_upgrade{d['upgrade']}_basic.csv.gz"
        meta = []
        for key in list_keys(client, bucket_url, meta_prefix):
            if key.endswith(suffix):
                path = data / "metadata" / key.rsplit("/", 1)[1]
                fetch(client, bucket_url + key, path)
                meta.append(path)
        picked = sample(
            read_metadata(meta), cfg["sample"]["per_type"], cfg["sample"]["seed"]
        )
        write_sample(picked, data / "sample.csv")
        profiles = []
        for i, r in enumerate(picked):
            name = f"{r['bldg_id']}-{d['upgrade']}.parquet"
            path = data / "timeseries" / name
            fetch(
                client,
                f"{base}/timeseries_individual_buildings/by_state/"
                f"upgrade={d['upgrade']}/state={d['state']}/{name}",
                path,
            )
            if i == 0:
                check_15_minute(path)
            profiles.append(path)
        sha = digest(meta + profiles)
        conn.execute(
            "UPDATE ingest_runs SET status = 'succeeded', finished_at = now(),"
            " rows = %s, source_rows = %s, sha256 = %s WHERE id = %s",
            (len(profiles), len(picked), sha, run_id),
        )
    except Exception as exc:
        conn.execute(
            "UPDATE ingest_runs SET status = 'failed', finished_at = now(),"
            " error = %s WHERE id = %s",
            (f"{type(exc).__name__}: {exc}", run_id),
        )
        raise
    return {"run_id": run_id, "metadata": len(meta), "profiles": len(profiles)}


def main() -> int:
    with connect(autocommit=True) as conn, Client(delay=0.2) as client:
        out = run(conn, client, load_config())
    print(f"comstock: {out['metadata']} metadata files, {out['profiles']} profiles")
    return 0


if __name__ == "__main__":
    sys.exit(main())
