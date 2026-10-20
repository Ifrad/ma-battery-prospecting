# Method

How the tool turns public data into model confidence. Sections are added as
each part is built.

## Hypothesis: which building types are spiky

The tool looks for buildings with high demand charges and short, sharp
peaks, since a battery block of 250 kW and 522 kWh earns the most where it
can cut a monthly peak that lasts only a few hours.

The owner's starting guess:

- Spikier: manufacturing, laundry, food production and auto-type sites.
- Flatter: hospitals, offices and warehouses.

This is a hypothesis to test, not an input. Nothing in config ranks
building types by spikiness, and the model does not use this list.

How it gets tested: the battery simulation on the downloaded load profiles
reports, for each building type, the peak-to-average ratio, the load
factor and the monthly peak reduction as a share of peak, and the same
split by building peak size. Building types are then ranked by peak
reduction in dollars per year, using the sourced demand rates in
config/rates.yaml, and the ranking is compared with the guess above. The
result goes in this file. Whether the profiles cover every type in the
guess is checked before they are downloaded.

The simulated profiles are not measured meter data, so the ranking is
simulated, not validated. Peak shape stays unvalidated until real interval
meter data tests it.

## ComStock load profiles

The battery simulation runs on simulated 15-minute electricity profiles
from ComStock, NREL's model of the U.S. commercial building stock
(2025 release 3, baseline, Massachusetts, 2018 weather). They are model
output for one weather year, not metered buildings.

Data includes information from the ComStock dataset developed by the
National Laboratory of the Rockies (NLR) with funding from the U.S.
Department of Energy (DOE).

`make comstock` downloads a sample, not all 2,285 Massachusetts
buildings. For each of the 15 building types it sorts the buildings by
floor area, splits them into 30 groups of equal count and picks one at
random from each group, with seed 20261020 (config/comstock.yaml). A type
with 30 or fewer buildings is taken whole; Massachusetts has only 9
hospitals. The first profile is checked for one year of 15-minute steps
before the rest are fetched. Files already on disk are not fetched again.

## Battery dispatch rule

One battery block, from config/battery.yaml: 250 kW, 522 kWh, 90 percent
usable (470 kWh), 97.5 percent conversion efficiency each way. Each
building and each calendar month is simulated on its own.

1. Pick a target peak for the month.
2. Walk through the month's 15-minute steps in order. The battery starts
   the month empty.
3. In a step that counts toward the bill, if the building's load is above
   the target, the battery covers the difference, at most 250 kW. It loses
   2.5 percent on the way out.
4. In any other step the battery charges with the spare room below the
   target, at most 250 kW, so charging never sets a new peak. It loses
   2.5 percent on the way in and never holds more than 470 kWh. In steps
   that do not count toward the bill, it may charge at the full 250 kW.
5. The target works if the battery never needs more than 250 kW and never
   runs out. The lowest target that works, found by halving the gap
   between a target that works and one that does not, is the month's new
   peak.

Steps that count: every step for the all-hours peak (National Grid G-2),
and only steps inside the G-3 peak window for the peak-window case
(weekdays 8 a.m. to 9 p.m., nine holidays excluded). Timestamps are taken
as given; daylight saving time is not modeled.

The rule knows the whole month in advance (perfect foresight), so the
result is an upper bound on what a real controller would achieve.
config/simulation.yaml holds a realization factor for Phase 4 to apply.
Starting each month empty means every kWh the battery delivers was
charged that month without raising the peak, so there is no free starting
charge. It slightly understates a month whose first peak comes before any
chance to charge.

Peak reduction is the month's original billed peak minus the new peak, in
kW and as a share of the original peak. Load factor is a month's average
load divided by its peak; the peak-to-average ratio is a building's annual
peak divided by its annual average load.
