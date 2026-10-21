# data/

Nothing here is committed except this file. A fresh clone does not need
anything in this folder to build the report: `make report` reads the
committed export/ files. You need the sources below only to rerun the
pipeline (`make ingest` through `make export`), which also needs PostGIS
(`make db-up`, `make migrate`).

## Public sources loaded into the database

`make ingest` reads these over HTTP (JSON, no key) and writes them to raw
tables in Postgres, not to files in this folder. The endpoints are in
`prospect/ingest/sources.py` and `config/lber.yaml`; docs/DATA.md says what
each contains and its gaps.

| Source | Table | Endpoint | Terms (docs/DATA.md) |
|---|---|---|---|
| MassGIS Level 3 assessor parcels | raw_parcels | ArcGIS layer `Massachusetts_Property_Tax_Parcels` | MassGIS public data, no warranty |
| MassGIS building footprints | raw_footprints | ArcGIS layer `Building_Structures` | public, attribution Rolta, MassGIS, City of Boston |
| Electric providers by town | raw_utility_territories | ArcGIS layer `ElectricityProviders` on arcgisserver.digital.mass.gov | public, source DPU and MassGIS |
| DOER LBER, calendar 2024 | raw_lber | ArcGIS layer in `config/lber.yaml`, moves with each October 31 release | EEA public data, as is |

Parcels and footprints load per pilot town; providers and LBER load
statewide. BERDO (Boston) is listed in `sources.py` but not loaded; it is
under Later in PLAN.md.

## Files written here

| Path | Written by | What | Licence |
|---|---|---|---|
| data/comstock/ | `make comstock` (download, about 1 GB) | NREL ComStock metadata and 15-minute profiles for a Massachusetts sample, from the OEDI data lake (`config/comstock.yaml`) | ComStock License, BSD style |
| data/comstock/simulation.csv | `make simulate` | one row per sampled building and month; summarized into config/simulation.yaml | derived from ComStock |
| data/enernoc/ | `make enernoc` (download) | EnerNOC open interval data, 100 anonymized sites, 2012 | CC BY-NC 3.0, non-commercial: used only as a local out-of-sample test, never committed or redistributed |
| data/validate/sensitivity.json | `make sensitivity` | rerun results that `make validate` reads | ours |
| data/review/ | `make match-rates` | hand review sheets | ours |

Downloads skip files already on disk, so a rerun only fills gaps. Each
ingest and download is recorded in the `ingest_runs` table.

## Manual steps

None of the sources above is downloaded by hand. Some config values were
read from public pages and typed into config/, not fetched by the
pipeline, each with its source and read date: the demand charges (config/rates.yaml), the
ConnectedSolutions terms (config/connected_solutions.yaml) and the battery
block figures (config/battery.yaml, from a product page that renders with
JavaScript). mass.gov returns HTTP 403 to automated downloads; this
blocked reading the clean peak regulations (docs/REVENUE_STREAMS.md), which
are not an input.
