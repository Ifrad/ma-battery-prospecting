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
