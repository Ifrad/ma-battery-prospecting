# Brief

## Worked example: Worcester Hahnemann Hospital

An example site, not the top site. It ranks first in Worcester, but Worcester's top is a tier, not an order: no Worcester site stays in the top 15 in more than half of the model's draws (docs/VALIDATION.md, rank stability). Every figure below is from export/worcester.geojson and export/manifest.json (score run 16). Values are simulated gross yearly revenue per battery block, before any host share: not profit, not accurate, unvalidated.

The site: 281 Lincoln St, Worcester, one parcel (use code 9550, charitable hospital), 4 buildings, 202,994 sq ft. National Grid serves it. Tier 1: its main building reports 6,211,196 kWh of grid electricity in LBER, so the model's yearly estimate (6,269,099 kWh) is mostly measured, not estimated. Its only flag is that the hospital intensity prior, used for the three small estimated buildings, comes from just 13 pilot buildings.

How its value per block is built, at the P50 draw:

| Step | Figure | Source |
|---|---|---|
| Battery block | 250 kW, 522 kWh | config/battery.yaml, sourced |
| Expected blocks | 1.0 | export, mean of the draws |
| Rate class | G-3 in every draw | export draws |
| G-3 demand charge | $10.61 per kW-month | National Grid tariff M.D.P.U. No. 1591, config/rates.yaml, sourced |
| Peak cut per year | 2,380.55 kW-months, after the realization factor 0.8 | export draws; the factor is a placeholder |
| Demand savings | 2,380.55 x $10.61 = $25,258 | export |
| ConnectedSolutions kW counted | min(250 x 0.61, 0.401 x 1,579 kW median modeled peak) = 152.5 kW, x (1 - 0.13) = 132.675 kW | performance factor 0.61 and overlap factor 0.13 are placeholders; 0.401 is the hospital's 3 to 8 pm mean over peak from ComStock |
| ConnectedSolutions revenue | 132.675 kW x $200 = $26,535 | $200 per kW-summer, National Grid and Mass Save, config/connected_solutions.yaml, sourced |
| Value per block | $25,258 + $26,535 = $51,793 | export, P50 with ConnectedSolutions |

The band is $37,542 to $51,999 (P10 to P90). The top of it is the block's power limit: at most 250 kW cut in each of 12 months, times 0.8, is 2,400 kW-months, worth $25,464, plus the same $26,535. ConnectedSolutions is 51 percent of its P50 value, and without it the site's value per block is $25,258. The building's 3 to 8 pm load does not limit ConnectedSolutions here; the block's average event output does.

Why it ranks where it does: a large hospital whose modeled peak (median 1,579 kW, from its measured yearly kWh and the ComStock hospital load factor) is well above one block, so in at least half the draws one block cuts within 1 percent of its full 250 kW every month, on a G-3 rate. The share of the peak one block cuts drives most of the spread across draws. By building area alone it ranks 78th among Worcester's candidate sites.

What to doubt: its yearly kWh per sq ft (30.9) and peak per sq ft (7.8 W) are above all 9 ComStock Massachusetts hospitals, because its measured LBER electricity is high for its floor area (docs/VALIDATION.md, hospital sanity check). Its peak shape is simulated from ComStock and unvalidated.
