"""Unique Building Identifiers (UBID), following PNNL's specification.

https://github.com/pnnl/buildingid/blob/master/SPEC.md. A UBID is the Open
Location Code (OLC) of the footprint's centroid cell, then the north, east,
south and west extents of its bounding box, counted in centroid-sized grid
cells. This mirrors the reference encoder (pnnl/buildingid-py, code.py),
including its rounding to whole cells (".0f"), using Google's
openlocationcode. DOER builds LBER's UBID field this way at code length 11.
"""

from openlocationcode import openlocationcode as olc

CODE_LENGTH = 11


def encode(
    south: float,
    west: float,
    north: float,
    east: float,
    lat: float,
    lng: float,
    code_length: int = CODE_LENGTH,
) -> str:
    """UBID for a bounding box (degrees) and its centroid (lat, lng)."""
    if not (south <= lat <= north and west <= lng <= east):
        raise ValueError("centroid outside bounding box")
    centre = olc.encode(lat, lng, code_length)
    c = olc.decode(centre)
    ne = olc.decode(olc.encode(north, east, code_length))
    sw = olc.decode(olc.encode(south, west, code_length))
    height = c.latitudeHi - c.latitudeLo
    width = c.longitudeHi - c.longitudeLo
    north_n = (ne.latitudeHi - c.latitudeHi) / height
    east_n = (ne.longitudeHi - c.longitudeHi) / width
    south_n = (c.latitudeLo - sw.latitudeLo) / height
    west_n = (c.longitudeLo - sw.longitudeLo) / width
    return f"{centre}-{north_n:.0f}-{east_n:.0f}-{south_n:.0f}-{west_n:.0f}"


def decode(ubid: str) -> tuple[float, float, float, float]:
    """The box (south, west, north, east) a UBID covers, snapped to grid cells."""
    code, *extents = ubid.strip().split("-")
    if len(extents) != 4 or not olc.isValid(code):
        raise ValueError(f"not a UBID: {ubid!r}")
    n, e, s, w = (int(x) for x in extents)
    c = olc.decode(code)
    height = c.latitudeHi - c.latitudeLo
    width = c.longitudeHi - c.longitudeLo
    return (
        c.latitudeLo - s * height,
        c.longitudeLo - w * width,
        c.latitudeHi + n * height,
        c.longitudeHi + e * width,
    )
