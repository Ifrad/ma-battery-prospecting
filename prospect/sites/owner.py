"""Local owner and tenure signals for parcels (config/sites.yaml)."""

import re
from datetime import date


def normalize_city(name: str | None, words: dict) -> str | None:
    tokens = re.sub(r"[^A-Z0-9]+", " ", (name or "").upper()).split()
    return " ".join(words.get(t, t) for t in tokens) or None


def is_local(town, own_city, own_state, own_zip, site_zip, config) -> bool | None:
    """Owner mailing address in the parcel's town; None if no address."""
    if not (own_city or own_zip):
        return None
    if (own_state or "MA").strip().upper() != "MA":
        return False
    words = config["city_words"]
    if own_city and normalize_city(own_city, words) == normalize_city(town, words):
        return True
    if config["zip_fallback"] and own_zip and site_zip:
        return own_zip.strip()[:5] == site_zip.strip()[:5]
    return False


def tenure_years(ls_date, ls_price, as_of: date, config) -> float | None:
    """Years since the last sale; None when that sale is nominal or unusable."""
    if ls_price is None or ls_price < config["nominal_price_below"]:
        return None
    try:
        sold = date(int(ls_date[:4]), int(ls_date[4:6]), int(ls_date[6:8]))
    except (TypeError, ValueError):
        return None
    if sold.year < config["earliest_sale_year"] or sold > as_of:
        return None
    return round((as_of - sold).days / 365.25, 1)


def assign(conn, config: dict) -> None:
    """Set parcels.local_owner and tenure_years.

    Tenure counts to the date the parcels were fetched, so a rebuild on the
    same data gives the same years.
    """
    as_of = conn.execute(
        "SELECT max(coalesce(finished_at, started_at))::date FROM ingest_runs"
        " WHERE id IN (SELECT DISTINCT run_id FROM raw_parcels)"
    ).fetchone()[0]
    towns = dict(
        conn.execute(
            "SELECT (attrs->>'TOWN_ID')::integer, attrs->>'TOWN'"
            " FROM raw_utility_territories"
        ).fetchall()
    )
    rows = conn.execute(
        "SELECT loc_id, town_id, own_city, own_state, own_zip, site_zip,"
        " ls_date, ls_price FROM parcels"
    ).fetchall()
    conn.execute(
        "CREATE TEMP TABLE parcel_owner_tenure (loc_id text, local_owner boolean,"
        " tenure_years numeric) ON COMMIT DROP"
    )
    local, tenure = config["local_owner"], config["tenure"]
    with conn.cursor().copy("COPY parcel_owner_tenure FROM STDIN") as copy:
        for loc_id, town_id, city, state, zip_, site_zip, sold, price in rows:
            copy.write_row(
                (
                    loc_id,
                    is_local(towns.get(town_id), city, state, zip_, site_zip, local),
                    tenure_years(sold, price, as_of, tenure),
                )
            )
    conn.execute(
        "UPDATE parcels p SET local_owner = o.local_owner,"
        " tenure_years = o.tenure_years"
        " FROM parcel_owner_tenure o WHERE o.loc_id = p.loc_id"
    )
