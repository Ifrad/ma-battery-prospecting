from datetime import date

import pytest

from prospect.sites.build import build
from prospect.sites.group import load_config
from prospect.sites.owner import is_local, tenure_years

CONFIG = load_config()
LOCAL, TENURE = CONFIG["local_owner"], CONFIG["tenure"]
AS_OF = date(2026, 10, 19)


@pytest.mark.parametrize(
    "own_city, own_state, own_zip, site_zip, expected",
    [
        ("WEST BRIDGEWATER", "MA", "02379", None, True),
        ("W. BRIDGEWATER", "MA", "02379", None, True),  # abbreviation
        ("WHITINSVILLE", "MA", "01588", "01588", True),  # village, same ZIP
        ("WHITINSVILLE", "MA", "01588", None, False),  # no parcel ZIP
        ("BOSTON", "MA", "02110", "02379", False),
        ("WEST BRIDGEWATER", "NH", "03000", None, False),
        (None, None, None, None, None),
    ],
)
def test_local_owner(own_city, own_state, own_zip, site_zip, expected):
    assert (
        is_local("WEST BRIDGEWATER", own_city, own_state, own_zip, site_zip, LOCAL)
        == expected
    )


def test_po_box_owner_in_same_town_is_local():
    # The rule looks at city, state and ZIP only, so a P.O. box counts.
    assert is_local("WORCESTER", "WORCESTER", "MA", "01613", None, LOCAL) is True


@pytest.mark.parametrize(
    "ls_date, price, expected",
    [
        ("20161019", 450000, 10.0),
        ("20161019", 1000, 10.0),
        ("20161019", 999, None),  # nominal
        ("20161019", 100, None),
        ("20161019", 1, None),
        ("20161019", 0, None),
        ("20161019", None, None),  # no price: cannot tell, so missing
        ("17540101", 500000, None),  # filler date
        ("20270101", 500000, None),  # after the data date
        ("2016", 500000, None),
        (None, 500000, None),
    ],
)
def test_tenure_ignores_nominal_sales(ls_date, price, expected):
    assert tenure_years(ls_date, price, AS_OF, TENURE) == expected


def test_site_takes_owner_and_tenure_from_main_parcel(db, raw, lber_rows):
    parcel, footprint = raw
    town, _ = lber_rows
    town(348, label="Mass Electric")  # gives the town its name for the test
    db.execute(
        'UPDATE raw_utility_territories SET attrs = attrs || \'{"TOWN": "WORCESTER"}\''
    )
    parcel(
        "A",
        0,
        0,
        USE_CODE="400",
        OWNER1="ACME",
        BLD_AREA=9000,
        OWN_CITY="WORCESTER",
        OWN_STATE="MA",
        LS_DATE="20000101",
        LS_PRICE=100,
    )
    footprint(0.0001, 0.0001, 900)
    build(db)
    row = db.execute("SELECT local_owner, tenure_years FROM sites").fetchone()
    assert row == (True, None)  # a $100 sale leaves tenure missing
