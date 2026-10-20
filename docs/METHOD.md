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
