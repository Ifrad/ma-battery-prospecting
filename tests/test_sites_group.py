import pytest

from prospect.sites.build import build
from prospect.sites.group import components, load_config, normalize_owner

DROP = load_config()["owner_normalization"]["drop_words"]


@pytest.mark.parametrize(
    "name, truncated, expected",
    [
        ("BROCKTON HOSPITAL", False, "BROCKTON HOSPITAL"),
        ("BROCKTON HOSPITAL INC", False, "BROCKTON HOSPITAL"),
        ("BROCKTON HOSPITAL COMPANY THE", False, "BROCKTON HOSPITAL"),
        ("UMASS MEMORIAL HEALTH CARE, INC", False, "UMASS MEMORIAL HEALTH CARE"),
        ("UMASS MEMORIAL HEALTH CARE, IN", True, "UMASS MEMORIAL HEALTH CARE"),
        ("THE MEDICAL CENTER OF CENTRAL", True, "MEDICAL CENTER OF"),
        ("Boyer, Elphege H.", False, "BOYER ELPHEGE H"),
        ("THE", False, None),
        (None, False, None),
    ],
)
def test_normalize_owner(name, truncated, expected):
    assert normalize_owner(name, truncated, DROP) == expected


def test_components_join_chains_and_name_groups_by_smallest_node():
    groups = components(["a", "b", "c", "d"], [("c", "b"), ("b", "a")])
    assert groups == {"a": "a", "b": "a", "c": "a", "d": "d"}


def sites(db):
    return db.execute(
        "SELECT site_id, owner, parcels, buildings FROM sites ORDER BY site_id"
    ).fetchall()


def test_touching_parcels_of_one_owner_form_one_site(db, raw):
    parcel, footprint = raw
    # Whitman case: a house lot and an auto repair lot, touching, one owner.
    parcel("A1", 0, 0, OWNER1="BOYER ELPHEGE H", USE_CODE="104", BLD_AREA=3748)
    parcel("A2", 0.001, 0, OWNER1="BOYER ELPHEGE H", USE_CODE="332", BLD_AREA=2280)
    footprint(0.0001, 0.0001, 1900)
    footprint(0.0011, 0.0001, 2280)
    build(db)
    assert sites(db) == [("A1", "BOYER ELPHEGE H", 2, 2)]


def test_spelling_variants_and_cut_off_names_join(db, raw):
    parcel, footprint = raw
    # As in a town whose owner field is 30 characters wide.
    parcel("B1", 0.01, 0, OWNER1="MEDICAL CENTER OF CENTRAL MASS", BLD_AREA=9000)
    parcel("B2", 0.011, 0, OWNER1="THE MEDICAL CENTER OF CENTRAL", BLD_AREA=100)
    parcel("B3", 0.012, 0, OWNER1="MEDICAL CENTER OF CENTRAL")
    for x in (0.0101, 0.0111, 0.0121):
        footprint(x, 0.0001, 500)
    build(db)
    assert [(s, p) for s, _, p, _ in sites(db)] == [("B1", 3)]


def test_scattered_parcels_and_other_owners_stay_separate(db, raw):
    parcel, footprint = raw
    parcel("C1", 0.02, 0, OWNER1="ACME")
    parcel("C2", 0.025, 0, OWNER1="ACME")  # same owner, not touching
    parcel("C3", 0.021, 0, OWNER1="OTHER LLC")  # touching C1, other owner
    for x in (0.0201, 0.0251, 0.0211):
        footprint(x, 0.0001, 500)
    build(db)
    assert [s for s, _, _, _ in sites(db)] == ["C1", "C2", "C3"]


def test_town_line_splits_sites(db, raw):
    parcel, footprint = raw
    parcel("D1", 0.03, 0, OWNER1="ACME")
    parcel("D2", 0.031, 0, town=316, OWNER1="ACME")
    footprint(0.0301, 0.0001, 500)
    footprint(0.0311, 0.0001, 500)
    build(db)
    assert [s for s, _, _, _ in sites(db)] == ["D1", "D2"]


def test_vacant_parcel_links_but_is_not_a_site_alone(db, raw):
    parcel, footprint = raw
    parcel("E1", 0.04, 0, OWNER1="ACME")
    parcel("E2", 0.041, 0, OWNER1="ACME")  # vacant, between E1 and E3
    parcel("E3", 0.042, 0, OWNER1="ACME")
    parcel("F1", 0.05, 0, OWNER1="LAND ONLY")
    footprint(0.0401, 0.0001, 500)
    footprint(0.0421, 0.0001, 500)
    build(db)
    assert sites(db) == [("E1", "ACME", 3, 2)]
