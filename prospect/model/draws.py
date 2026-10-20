"""Monte Carlo draws of yearly energy and peak demand.

Each building's draws are seeded by its building id and each site's by its
site id, so results never depend on row order. A spread given as p10,
median and p90 is drawn as a lognormal with its own width on each side of
the median, so the draws hit all three.
"""

import hashlib

import numpy as np

Z90 = 1.2815515655446004  # 90th percentile of the standard normal
Z95 = 1.6448536269514722  # 95th, for a two-sided 90 percent band
HOURS = 8760


def rng(key: int | str, stream: int = 0) -> np.random.Generator:
    """A generator for one building id or site id, and one input stream."""
    if isinstance(key, str):
        key = int.from_bytes(hashlib.sha256(key.encode()).digest()[:8], "big")
    return np.random.default_rng([key, stream])


def from_spread(spread: dict, z: np.ndarray) -> np.ndarray:
    """Values at standard normal z with the given p10, median and p90."""
    med = spread["median"]
    low = np.log(med / spread["p10"]) / Z90
    high = np.log(spread["p90"] / med) / Z90
    return med * np.exp(np.where(z < 0, low, high) * z)


def is_weak(confidence: str | None, cfg: dict) -> bool:
    rule = cfg["model"]["measured_kwh"]
    if confidence is None:
        return False
    return confidence in rule["weak_confidences"] or (
        rule["weak_ambiguous"] and confidence.startswith("ambiguous")
    )


def building_kwh(b: dict, cfg: dict, n: int) -> np.ndarray:
    """Yearly kWh draws for one building."""
    prior = cfg["intensity"]["segments"][b["segment"]]["prior"]
    z = rng(b["building_id"], 1).standard_normal(n)
    if b["electricity_source"] == "measured" and b["grid_kwh"]:
        if not is_weak(b["lber_confidence"], cfg):
            return np.full(n, float(b["grid_kwh"]))
        return b["grid_kwh"] * from_spread(prior, z) / prior["median"]
    return area(b, cfg, n) * from_spread(prior, z)


def area(b: dict, cfg: dict, n: int) -> np.ndarray:
    """Floor area draws, as wide as the measured error of the area source."""
    p90 = cfg["model"]["area_error"]["p90"][b["area_source"]]
    sigma = np.log1p(p90) / Z95
    return b["area_sqft"] * np.exp(sigma * rng(b["building_id"], 2).standard_normal(n))


def load_factor(site: dict, cfg: dict, n: int) -> np.ndarray:
    """Monthly load factor draws from the site's simulated profile."""
    sim = cfg["simulation"]
    g = rng(site["site_id"], 1)
    if site["profile"] == "no open profile":
        env = sim["no_open_profile"]["load_factor"]
        return g.uniform(env["low"], env["high"], n)
    if site["profile"] == "placeholder mix":
        spread = sim["pooled"]["load_factor"]
    else:
        spread = sim["types"][site["profile"]]["load_factor"]
    return np.clip(from_spread(spread, g.standard_normal(n)), 0.01, 1.0)


def site_draws(site: dict, buildings: list[dict], cfg: dict) -> dict:
    """Yearly kWh, load factor and monthly peak kW draws for one site."""
    n = cfg["model"]["draws"]["value"]
    kwh = sum(building_kwh(b, cfg, n) for b in buildings)
    lf = load_factor(site, cfg, n)
    return {"annual_kwh": kwh, "load_factor": lf, "peak_kw": kwh / HOURS / lf}
