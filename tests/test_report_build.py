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
