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


def test_limits_read_every_figure_from_validation_md():
    f = build.findings((build.DOCS / "VALIDATION.md").read_text())
    assert set(f) == set(build.PATTERNS)
    assert 0 < float(f["spearman_size"]) <= float(f["spearman_model"]) < 1


def test_limits_fail_loudly_when_validation_md_lacks_a_figure():
    import pytest

    with pytest.raises(SystemExit, match="spearman_model"):
        build.findings("nothing here")


def test_limits_section_states_the_required_points():
    data = build.load_export()
    text = build.limits(data, (build.DOCS / "VALIDATION.md").read_text())
    for phrase in (
        "not profit",
        "Installed cost and the host share are not modeled",
        "only stress-tested",
        "tier, not an order",
        "rate area is unconfirmed",
        "no open load profile",
        "only modestly",
        "out-of-sample",
        "probably understated",
        "Placeholders in use",
    ):
        assert phrase in text
    share = build.export_facts(data)["cs_share"]
    assert f"{share:.0%}" in text
