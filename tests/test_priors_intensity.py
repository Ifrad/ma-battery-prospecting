import pytest

from prospect.priors import intensity


def test_priors_flag_small_segments_and_use_healthcare_and_proxy():
    pilot = [("warehouse", 2.0, 2.1)] * 40 + [("manufacturing", 4.0, 4.0)] * 35
    pilot += [("hospital", 20.0, 18.0)] * 3 + [("laundry", 9.0, 9.0)]
    out = intensity.summarize(pilot, healthcare=[5.0, 10.0, 15.0])
    assert out["warehouse"]["measured_buildings"] == 40
    assert not out["warehouse"]["under_30"]
    assert out["warehouse"]["prior"]["median"] == pytest.approx(2.0)
    assert out["hospital"]["under_30"]
    assert out["hospital"]["prior"]["median"] == pytest.approx(20.0)
    assert "only 3 buildings" in out["hospital"]["prior_from"]
    assert out["other_healthcare"]["prior"]["median"] == pytest.approx(10.0)
    assert out["other_healthcare"]["prior_buildings"] == 3
    assert out["laundry"]["prior"] == out["manufacturing"]["our_area"]
    assert "likely understates" in out["laundry"]["prior_from"]
    assert out["cold_storage"]["measured_buildings"] == 0
