"""Translate value per block into a break-even installed cost per block.

The break-even cost is the installed cost per block at which the yearly
value equals the annualized cost: installed cost over the life at the
financing rate, plus O&M. It leaves out any host benefit. The ITC, when
on, lowers the installed cost by the credit.
"""

import numpy as np


def crf(rate: float, years: float) -> float:
    """Capital recovery factor: yearly payment per dollar borrowed."""
    growth = (1 + rate) ** years
    return rate * growth / (growth - 1)


def itc_applies(blocks: float, cfg: dict) -> bool:
    """The under-1 MW ITC rate applies only below its capacity limit."""
    itc = cfg["costs"]["itc"]
    return blocks * cfg["battery"]["block"]["power_kw"] < itc["max_capacity_kw"]


def annual_cost(installed: float, cfg: dict, itc: bool, blocks: float = 1) -> float:
    """Yearly cost of one block: capital recovery plus O&M."""
    c = cfg["costs"]
    credit = c["itc"]["rate"] if itc and itc_applies(blocks, cfg) else 0.0
    factor = crf(c["financing_rate"]["value"], c["life_years"]["value"])
    return installed * (1 - credit) * factor + c["om_usd_per_year"]["value"]


def break_even(value: float, cfg: dict, itc: bool, blocks: float = 1) -> float:
    """Highest installed cost per block that a yearly value per block covers."""
    c = cfg["costs"]
    credit = c["itc"]["rate"] if itc and itc_applies(blocks, cfg) else 0.0
    factor = crf(c["financing_rate"]["value"], c["life_years"]["value"])
    return max(0.0, (value - c["om_usd_per_year"]["value"]) / (factor * (1 - credit)))


def break_even_summary(value_per_block: np.ndarray, blocks: float, cfg: dict) -> dict:
    """Break-even cost per block at P50 and P10 value, without and with ITC."""
    p10, p50 = np.percentile(value_per_block, [10, 50])
    out = {}
    for label, v in (("p50", p50), ("p10", p10)):
        out[label] = break_even(float(v), cfg, itc=False)
        out[f"{label}_itc"] = break_even(float(v), cfg, itc=True, blocks=blocks)
    out["itc_applies"] = itc_applies(blocks, cfg)
    return out
