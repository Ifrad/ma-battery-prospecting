from prospect.validate import baseline


def test_overlap_counts_shared_sites():
    assert baseline.overlap(["a", "b", "c"], ["c", "b", "x"]) == 2
    assert baseline.overlap([], ["a"]) == 0


def test_section_names_the_prototype_as_prior_work():
    r = {
        k: {"overlap_all": 1, "overlap_scored": 2, "size_top_dropped": {"kwh": 3}}
        for k in baseline.REGIONS
    }
    text = "\n".join(baseline.section(r))
    assert "github.com/thutch17/powertown-hackathon" in text
    assert "prior work" in text and "hackathon entry" not in text
    assert "| Metro South | 1 | 2 | 0 | 3 | 0 |" in text
