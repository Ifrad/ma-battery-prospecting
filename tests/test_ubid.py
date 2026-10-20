import json
from pathlib import Path

import pytest

from prospect.sites.ubid import decode, encode

PAIRS = json.loads(
    (Path(__file__).parent / "fixtures" / "ubid" / "lber_pairs.json").read_text()
)


def test_pnnl_reference_values():
    # pnnl/buildingid-py tests/buildingid/test_code.py, code length 10.
    assert encode(0, 0, 0, 0, 0, 0, code_length=10) == "6FG22222+22-0-0-0-0"
    assert (
        encode(0, 0, 10, 10, 5, 5, code_length=10)
        == "6FQ72222+22-40000-40000-40000-40000"
    )


@pytest.mark.parametrize("pair", PAIRS, ids=[p["ubid"] for p in PAIRS])
def test_reproduces_lber_ubids_from_massgis_footprints(pair):
    box = [pair[k] for k in ("south", "west", "north", "east", "lat", "lng")]
    assert encode(*box) == pair["ubid"]


@pytest.mark.parametrize("pair", PAIRS[:3], ids=[p["ubid"] for p in PAIRS[:3]])
def test_decoded_box_contains_the_footprint_box(pair):
    s, w, n, e = decode(pair["ubid"])
    assert s <= pair["south"] and w <= pair["west"]
    assert n >= pair["north"] and e >= pair["east"]


def test_centroid_outside_box_is_rejected():
    with pytest.raises(ValueError):
        encode(42.0, -71.0, 42.1, -70.9, 43.0, -70.95)


def test_decode_rejects_bad_strings():
    for bad in ("", "87JC3XMJ+25F", "87JC3XMJ+25F-1-2-3", "XXXX-1-1-1-1"):
        with pytest.raises(ValueError):
            decode(bad)
