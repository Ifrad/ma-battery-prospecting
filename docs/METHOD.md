# Method

How the tool turns public data into value per battery block: the simulated
yearly demand savings plus grid program revenue one battery block could
bring, gross, before any host share. Not profit, and unvalidated. Sections
are added as each part is built.

## Hypothesis: which building types are spiky

The tool looks for buildings with high demand charges and short, sharp
peaks, since a battery block of 250 kW and 522 kWh earns the most where it
can cut a monthly peak that lasts only a few hours.

The owner's starting guess:

- Spikier: manufacturing, laundry, food production and auto-type sites.
- Flatter: hospitals, offices and warehouses.

This is a hypothesis to test, not an input. Nothing in config ranks
building types by spikiness, and the model does not use this list.

How it gets tested: the battery simulation reports, for each ComStock
building type, the load factor and the monthly peak reduction as a share
of peak, split by building peak size (next section but two). There is no
dollar ranking by segment, because the open profiles cover none of the
spikier types in the guess: ComStock models no factories, laundries, food
plants or auto repair shops. Only the flatter half of the guess can be
checked.

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

## Simulated peak reduction by building size

Median monthly peak reduction as a share of the all-hours peak, from
config/simulation.yaml. Simulated, one weather year (2018), perfect
foresight: an upper bound, unvalidated. Building count in brackets;
"pooled" marks a cell with fewer than 10 buildings, which uses all types
pooled in that size bin. Load factor is the median monthly load factor.

| Building type | Load factor | Under 200 kW | 200 to 500 kW | 500 to 1,000 kW | 1,000 kW and up |
|---|---|---|---|---|---|
| SecondarySchool | 0.30 | 0.44 (7) pooled | 0.32 (7) pooled | 0.21 (9) pooled | 0.15 (7) pooled |
| PrimarySchool | 0.32 | 0.49 (13) | 0.39 (15) | 0.21 (1) pooled | 0.15 (1) pooled |
| SmallOffice | 0.36 | 0.51 (27) | 0.32 (3) pooled | 0.21 (0) pooled | 0.15 (0) pooled |
| Outpatient | 0.38 | 0.46 (14) | 0.32 (10) | 0.21 (5) pooled | 0.15 (1) pooled |
| RetailStandalone | 0.39 | 0.50 (23) | 0.32 (4) pooled | 0.21 (2) pooled | 0.15 (1) pooled |
| RetailStripmall | 0.42 | 0.52 (11) | 0.34 (10) | 0.21 (5) pooled | 0.15 (4) pooled |
| LargeOffice | 0.43 | 0.44 (5) pooled | 0.32 (5) pooled | 0.21 (9) pooled | 0.13 (11) |
| Warehouse | 0.45 | 0.41 (17) | 0.26 (11) | 0.21 (1) pooled | 0.15 (1) pooled |
| MediumOffice | 0.45 | 0.42 (19) | 0.34 (10) | 0.21 (1) pooled | 0.15 (0) pooled |
| Hospital | 0.45 | 0.44 (0) pooled | 0.32 (1) pooled | 0.21 (2) pooled | 0.15 (6) pooled |
| FullServiceRestaurant | 0.46 | 0.45 (21) | 0.32 (8) pooled | 0.21 (1) pooled | 0.15 (0) pooled |
| QuickServiceRestaurant | 0.47 | 0.44 (30) | 0.32 (0) pooled | 0.21 (0) pooled | 0.15 (0) pooled |
| LargeHotel | 0.56 | 0.44 (9) pooled | 0.32 (6) pooled | 0.22 (10) | 0.15 (5) pooled |
| SmallHotel | 0.62 | 0.27 (28) | 0.32 (2) pooled | 0.21 (0) pooled | 0.15 (0) pooled |
| Grocery | 0.69 | 0.44 (0) pooled | 0.17 (13) | 0.15 (15) | 0.15 (2) pooled |
| All types pooled | 0.44 | 0.44 (224) | 0.32 (105) | 0.21 (61) | 0.15 (39) |

What it shows:

- Size matters more than type. A 250 kW battery cuts a larger share of a
  small building's peak: the pooled median falls from 0.44 under 200 kW to
  0.15 at 1,000 kW and up, while the kW cut grows.
- Within a size bin most types are close. The flattest types cut less:
  grocery (load factor 0.69) 0.17 at 200 to 500 kW against 0.32 pooled,
  small hotels 0.27 under 200 kW against 0.44, warehouses 0.26 at 200 to
  500 kW.
- On the guess: grocery and hotels come out flatter, as expected.
  Warehouses are flatter only above 200 kW, and offices are not flatter
  than retail or restaurants. Hospitals have too few buildings (9) to say.
  Factories, laundries, food plants and auto repair cannot be tested here.

## Priors, battery and costs

Every model input lives in config/ with a status: sourced, with its source,
or placeholder, with what it is, how it gets tested and what would replace
it. `prospect priors --list-placeholders` lists the placeholders, and
docs/ASSUMPTIONS.md (`make assumptions`) explains each one.

- Demand rates: config/rates.yaml, per utility and rate schedule, read
  from filed tariffs on 2026-10-20. Five municipal plants publish no
  schedule, so they have no rate yet.
- Energy intensity: config/intensity.yaml (`make intensity`), yearly kWh
  per sq ft by segment from LBER measured electricity. LBER covers
  buildings of about 20,000 sq ft and up, so these may not fit smaller
  buildings.
- Load shape and peak reduction: config/simulation.yaml (`make
  simulate`), simulated on ComStock, an upper bound, with
  config/profiles.yaml mapping sites to building types.
- Grid program: config/connected_solutions.yaml.
- Battery block: config/battery.yaml, 250 kW, 522 kWh and 97.5 percent
  efficiency from the Powertown product page
  (https://www.powertownusa.com/product), read by the owner on
  2026-10-19. Config `source:` lines name it "manufacturer product page"
  and point here. The page renders with JavaScript, so a recheck on
  2026-10-20 could not read it. Whether the ratings are per cabinet or per
  pair, and the 90 percent usable depth, are placeholders.
- Costs: config/costs.yaml. The 10 year life is the warranty on the same
  page; the installed cost cases, financing rate, O&M, ITC rate and
  minimum host benefit are placeholders. Cost is not an input to the
  ranking: life, financing and O&M turn value into a break-even installed
  cost, the two installed cost cases are reference points beside it, and
  the minimum host benefit has no value and is used only when a user asks
  for model confidence at a given cost.

## After each October 31 LBER release

1. Add the new layer URL and reporting year to config/lber.yaml, then
   `make ingest` (the old year stays next to the new one).
2. `make sites` to rematch buildings, then `make match-rates`.
3. `make intensity` for new priors, then `make funnel`.
4. `make assumptions` and `make check`, and review what moved.

Rates also change through the year: recheck the rate summaries named in
config/rates.yaml (each utility's `refresh` line). ComStock and the
simulation change only with a new ComStock release.

## Payback check

The operator says it recovers costs in 2 to 3 years. docs/SCORES.md
(`make score`) takes the median P50 value per block across scored sites,
with ConnectedSolutions, and multiplies it by 2 and by 3: the installed
cost per block a simple payback of that length would imply. On the
2026-10-20 run with the event-window cap (run 13) the median is $31,591
a year, so 2 years implies $63,182 per block and 3 years $94,773, below
the owner's estimates of
$180,000 and $260,000. Either real costs are lower than the estimates,
real value is higher than simulated, or the claim counts something else.

This is a consistency check on the cost estimates, not evidence for or
against the claim. Simple payback ignores financing, O&M and the host's
share, and the value is simulated, gross and unvalidated. More than half
of P50 value comes from ConnectedSolutions: the $200 per kW rate is
sourced, but the performance factor and the event-window load behind it
are a placeholder and a simulation.
