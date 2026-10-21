# Brief

For Powertown. This project is not affiliated with Powertown, uses public data only, and builds on an earlier public prototype (github.com/thutch17/powertown-hackathon), credited as prior work. Figures are from docs/SCORES.md, docs/VALIDATION.md, config/ and the export; the README explains each step.

## What it does

It ranks commercial and industrial sites in Metro South (Brockton) and Worcester by value per battery block: the simulated yearly demand savings plus ConnectedSolutions revenue one 250 kW, 522 kWh block could bring a site, gross, before any host share. Each site has a P10 to P90 band, the reasons, and an owner and address for outreach, in one offline page, report.html. Cost and profit are not modeled: you apply your own installed cost and host share.

## Headline

- 354 of 9,640 candidate sites are scored: 156 in Metro South, 198 in Worcester.
- The median scored site's P50 value per block is $31,591 a year with ConnectedSolutions, $11,589 from demand savings alone.
- ConnectedSolutions is 56 percent of P50 value across sites, so the ranking leans on one program and on placeholder delivery factors.
- Metro South's top 10 are all Eversource sites in Canton and Sharon, priced at Eversource's Greater Boston G-2 rate ($33.95 per kW-month, against National Grid's $15.24). That rate area is unconfirmed.
- Worcester's top is a tier, not an order: its top 15 run from $46,989 to $51,793, close to the one-block ceiling of $51,999.

## Worked example: Worcester Hahnemann Hospital

An example site, not the top site: it ranks first in Worcester, but Worcester's top is a tier, not an order. 281 Lincoln St, National Grid, 4 buildings, 202,994 sq ft. Tier 1: its main building reports 6,211,196 kWh in LBER. From export/worcester.geojson and export/manifest.json, at P50:

| Step | Figure | Source |
|---|---|---|
| Rate class and charge | G-3 in every draw, $10.61 per kW-month | National Grid tariff M.D.P.U. No. 1591, sourced |
| Peak cut per year | 2,380.55 kW-months, after the realization factor 0.8 | export; the factor is a placeholder |
| Demand savings | 2,380.55 x $10.61 = $25,258 | export |
| ConnectedSolutions kW | min(250 x 0.61, 0.401 x 1,579 kW peak) = 152.5, x (1 - 0.13) = 132.675 kW | factors 0.61 and 0.13 are placeholders; 0.401 is the ComStock hospital 3 to 8 pm ratio |
| ConnectedSolutions revenue | 132.675 kW x $200 = $26,535 | $200 per kW-summer, National Grid and Mass Save, sourced |
| Value per block | $25,258 + $26,535 = $51,793, band $37,542 to $51,999 | export, 1.0 expected blocks |

Its modeled peak is well above one block, so in at least half the draws one block cuts within 1 percent of its full 250 kW every month. By building area alone it ranks 78th in Worcester. What to doubt: its kWh and peak per sq ft (30.9 kWh, 7.8 W) are above all 9 ComStock Massachusetts hospitals, because its measured LBER electricity is high for its size (docs/VALIDATION.md, hospital sanity check).

## What is unvalidated

- Value per block has no accuracy figure. It is simulated and gross, and it is not profit.
- Peak shape is simulated (ComStock, 2018 weather, perfect foresight times the realization factor) and only stress-tested: with the cut share reduced, Metro South keeps 14 of its top 15 and Worcester 8.
- Yearly electricity beats a size-only estimate only modestly: Spearman 0.47 against 0.43, towns held out, and no better for manufacturing.
- ConnectedSolutions delivery (performance factor 0.61, overlap factor 0.13, no export) is a placeholder.
- 91 scored sites (factories, laundries, food plants, cold storage, auto repair) have no open load profile. Factories in the EnerNOC meter data, used only as a local test, use more of their peak in the 3 to 8 pm event window than the model assumes, so their ConnectedSolutions revenue is probably understated.

## Open questions for Powertown

1. Installed cost per block.
2. ITC eligibility.
3. Whether ConnectedSolutions stacks with peak shaving on the same battery.
4. The savings split with the host.
5. How you find sites today.
6. A list of current and contacted sites, to load as the report's customer status file.
7. Anonymized load shapes for manufacturing, laundry and food sites.
8. A Canton or Sharon commercial bill, to settle which Eversource rate area serves those towns.
9. Priority regions.

## Claims to check, not inputs

Two claims on Powertown's product page are not used by the model: "1 to 3 months off your bill" and recovering costs "by year two or three". Your installed cost and savings split would let the report's values test them.
