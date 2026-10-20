"""Download the EnerNOC open commercial and industrial interval dataset.

Usage: python -m prospect.ingest.enernoc (make enernoc)

100 anonymized sites, 2012, licensed CC BY-NC 3.0 (non-commercial). Used only
as an out-of-sample test in docs/VALIDATION.md: no config value is derived or
tuned from it, and it is never committed or redistributed. Files go under
data/enernoc/ (gitignored); files already there are not fetched again. Each
run is recorded in ingest_runs.
"""

import hashlib
import sys
import tarfile
from pathlib import Path

from prospect.db import connect
from prospect.ingest.client import Client

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data" / "enernoc"
BASE = "https://open-enernoc-data.s3.amazonaws.com/anon"
FILES = {
    "all-data.tar.gz": f"{BASE}/all-data.tar.gz",
    "all_sites.csv": f"{BASE}/meta/all_sites.csv",
}


def fetch(client: Client, url: str, path: Path) -> None:
    if path.exists() and path.stat().st_size > 0:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".part")
    tmp.write_bytes(client.get(url).content)
    tmp.rename(path)


def extract(archive: Path, out: Path) -> list[Path]:
    """Unpack the per-site CSV files once; return them sorted."""
    out.mkdir(parents=True, exist_ok=True)
    if not any(out.glob("*.csv")):
        with tarfile.open(archive, "r:gz") as tar:
            for m in tar.getmembers():
                name = Path(m.name)
                # Site files only: csv/<site_id>.csv, flattened.
                if m.isfile() and name.parent.name == "csv" and name.stem.isdigit():
                    m.name = name.name
                    tar.extract(m, out, filter="data")
    return sorted(out.glob("*.csv"))


def run(conn, client: Client, data: Path = DATA) -> dict:
    run_id = conn.execute(
        "INSERT INTO ingest_runs (source, url, scope) VALUES ('enernoc', %s, 'all')"
        " RETURNING id",
        (BASE,),
    ).fetchone()[0]
    try:
        for name, url in FILES.items():
            fetch(client, url, data / name)
        sites = extract(data / "all-data.tar.gz", data / "csv")
        h = hashlib.sha256()
        for name in FILES:
            h.update((data / name).read_bytes())
        conn.execute(
            "UPDATE ingest_runs SET status = 'succeeded', finished_at = now(),"
            " rows = %s, source_rows = %s, sha256 = %s WHERE id = %s",
            (len(sites), len(sites), h.hexdigest(), run_id),
        )
    except Exception as exc:
        conn.execute(
            "UPDATE ingest_runs SET status = 'failed', finished_at = now(),"
            " error = %s WHERE id = %s",
            (f"{type(exc).__name__}: {exc}", run_id),
        )
        raise
    return {"run_id": run_id, "sites": len(sites)}


def main() -> int:
    with connect(autocommit=True) as conn, Client(delay=0.2) as client:
        out = run(conn, client)
    print(f"enernoc: {out['sites']} site files in data/enernoc/csv")
    return 0


if __name__ == "__main__":
    sys.exit(main())
