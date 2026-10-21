import json
import re

from prospect.report import build


def test_embedded_json_cannot_close_its_script_tag():
    text = build.embed({"owner": "</script><script>alert(1)</script>"})
    assert "</script" not in text
    assert json.loads(text)["owner"] == "</script><script>alert(1)</script>"


def test_page_is_self_contained(tmp_path):
    page = build.page(build.load_export())
    assert not re.search(r"<script[^>]+src=", page)
    assert not re.search(r"(src|href)=\"https?:", page)
    links = re.findall(r"<link[^>]*>", page)
    assert links == ['<link rel="icon" href="data:,">']  # stops the favicon request
    assert "powertown" not in page.lower()


def test_customer_status_example_is_fake_and_real_files_are_ignored():
    import csv
    import subprocess

    rows = list(
        csv.DictReader((build.ROOT / "docs" / "customer_status.example.csv").open())
    )
    assert rows and set(rows[0]) == {"owner", "address", "town", "status"}
    assert {r["status"] for r in rows} <= {"customer", "contacted", "declined"}
    text = " ".join(" ".join(r.values()) for r in rows)
    assert all(w in text for w in ("EXAMPLE", "SAMPLE", "PLACEHOLDER"))

    def ignored(path):
        return (
            subprocess.run(
                ["git", "check-ignore", "-q", path], cwd=build.ROOT
            ).returncode
            == 0
        )

    assert ignored("customer_status.csv") and ignored("data/customer_status_2026.csv")
    assert not ignored("docs/customer_status.example.csv")
    assert ignored("report.html")
