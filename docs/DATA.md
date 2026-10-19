# Data sources

What each public source contains, where it lives, its terms, and the gaps
that affect this project. Checked on 2026-10-19 with `make probe` and
follow-up queries against the live services. Endpoints are in
`prospect/ingest/sources.py`.

## Summary

All five Phase 1 sources are reachable as JSON over HTTP with no key. No
core field is missing. Five findings change the plan and need a decision
before the loaders are written. They are listed at the end under
"Decisions needed".

| Source | Rows | Page size | Geometry | Terms |
|---|---|---|---|---|
| parcels | 2,559,555 | 2,000 | polygon | MassGIS, public, no warranty |
| footprints | 2,678,977 | 2,000 | polygon | MassGIS and City of Boston, public |
| utility_territories | 351 | 2,000 | polygon (town) | DPU and MassGIS, public |
| lber | 33,185 | 2,000 | point | EEA, public, no warranty |
| berdo | 5,638 | none (CKAN) | none | ODC PDDL (public domain) |

## Verified facts, rechecked

| Fact in PLAN.md | Result |
|---|---|
| L3 parcels have owner1, site_addr, bld_area, year_built, ls_date, use_code | True. Field names are upper case. |
| L3 parcels are a hosted ArcGIS feature layer with 2,000 record pages | True. The layer is `Massachusetts_Property_Tax_Parcels`. An older name found online, `L3_TAXPAR_POLY_ASSESS_gdb`, no longer exists. |
| 305 private hospital, 979 exempt hospital, 414 food processing | True for Boston only. All 189 parcels coded 979 are in Boston. Other towns use the state DOR code 955 (or 9550, 955V) for charitable hospitals, 584 parcels statewide. |
| LBER covers buildings of 20,000 sq ft or more, first release is incomplete | True, and the gap is large. See lber below. |
| BERDO covers non-residential buildings of 20,000 sq ft or more | True. It also covers residential buildings with 15 or more units. |
| ComStock publishes 15 minute profiles | Not checked. It is a Phase 3 source. |

## parcels

MassGIS Level 3 assessor parcels, all 351 towns including Boston.

- Endpoint: `services1.arcgis.com/hGdibHYSPO59RG1h/.../Massachusetts_Property_Tax_Parcels/FeatureServer/0`
- Terms: MassGIS public data. The license note says parcel lines are a
  representation, not a legal survey. No other restriction.
- Key fields: `LOC_ID` (polygon id), `PROP_ID` (assessor id), `TOWN_ID`,
  `OWNER1`, `SITE_ADDR`, `CITY`, `ZIP`, `USE_CODE`, `USE_DESC`,
  `BLD_AREA`, `YEAR_BUILT`, `LS_DATE` (text, YYYYMMDD), `LS_PRICE`,
  `STORIES`, `FY`, `TOTAL_VAL`.

Gaps:

- One polygon can have several rows, one per assessor record (condos,
  multiple buildings). Brockton has 27,175 rows on 25,036 polygons.
- `USE_CODE` format varies by town. Brockton uses 3 digits. Worcester uses
  4 characters with letter suffixes such as `9550`, `955V`, `049C`. About
  half of all rows statewide have 4 character codes.
- Code alone misses some sites. Worcester's largest hospital parcel
  (647,093 sq ft) is coded `049C`, "Other".
- In the pilot towns, among commercial, industrial and hospital parcels
  (codes 300 to 499, plus 979):

  | Town | Parcels | No BLD_AREA | No YEAR_BUILT | No LS_DATE | 20,000 sq ft or more |
  |---|---|---|---|---|---|
  | Brockton | 1,670 | 543 (33%) | 1,670 (100%) | 359 | 199 |
  | Worcester | 2,607 | 742 (28%) | 741 (28%) | 0 | 367 |

- The layer is edited live. The row count changed by 81 between two
  checks on the same day. Every load needs its own `ingest_runs` row and
  hash.
- `FY` (fiscal year of the assessment) differs by town. Some rows already
  show FY 2027.

## footprints

MassGIS Building Structures (2-D), roof outlines over 150 sq ft.

- Endpoint: `services1.arcgis.com/hGdibHYSPO59RG1h/.../Building_Structures/FeatureServer/0`
- Terms: public, attribution "Rolta, MassGIS, City of Boston".
- Key fields: `STRUCT_ID`, `AREA_SQ_FT` (roof area), `TOWN_ID`,
  `SOURCEDATE`, `ARCHIVED`.
- Brockton has 30,737 structures and Worcester 50,119.

Gaps:

- No parcel id and no address. Linking a footprint to a parcel needs a
  spatial join in PostGIS, which the plan already expects.
- Roof area is not floor area. Multi-story buildings need `STORIES` from
  the parcel.
- No archived rows are served. Removed buildings are simply absent.

## utility_territories

Electric provider for each town.

- Endpoint: `arcgisserver.digital.mass.gov/.../AGOL/ElectricityProviders/FeatureServer/0`
- Terms: public, source "Massachusetts Department of Public Utilities,
  MassGIS".
- Key fields: `TOWN_ID`, `TOWN`, `ELEC` (provider names), `ELEC_LABEL`
  ("Municipal" for municipal light plants).
- The service description says "as of 2015", but its values match all 351
  rows of the January 2026 MassGIS download (`pubutil.zip`), so it is
  current.

Gaps:

- These are town outlines, not true service territories. 18 towns list
  more than one provider in one text field (for example Middleborough:
  municipal plus Eversource). For those towns the provider of a single
  parcel is unknown.
- 50 towns have a municipal light plant, 41 of them as the only provider.
- Brockton and Worcester are both National Grid only, so the pilot is not
  affected.

## lber

DOER Large Building Energy Reporting, calendar 2024 results.

- Endpoint: `services1.arcgis.com/7iJyYTjCtKsZS1LR/.../2025_Annual_Report_Data/FeatureServer/0`
  (found behind the map on mass.gov's "Large Building Energy Reporting
  Results" page).
- Terms: EEA public data, "as is", no warranty of accuracy.
- Key fields: `UBID` (building id from footprint), `Street_Address`,
  `City`, `ZIP_Code`, `Property_Type`, `Gross_Floor_Area`,
  `Total_Electricity_Use_Purchased_From_Grid__kBtu_`,
  `Total_Energy_Use__kBtu_`, `Latitude`, `Longitude`.

Gaps:

- 24,624 of 33,185 buildings (74%) report zero grid electricity, and
  19,176 report zero total energy. Only 8,487 have electricity above zero.
  In the pilot: Brockton 181 of 486, Worcester 315 of 992.
- No owner and no parcel id. Matching to parcels uses the point location
  and the address.
- Electricity is in kBtu, not kWh (1 kWh = 3.412 kBtu). Values are single
  precision floats.
- The reporting year is only in a field name (`F2024_Total_GHG...`). The
  loader must record the year itself.
- 1,510 rows have floor area under 20,000 sq ft, below the reporting
  threshold.
- The layer belongs to a personal ArcGIS account at EEA, not an agency
  account. The calendar 2025 release, due October 31, 2026, will likely
  be a new layer at a new URL.

## berdo

Boston Building Emissions Reduction and Disclosure Ordinance.

- Endpoint: data.boston.gov CKAN `datastore_search`, resource
  `87521565-7f15-4b8d-a225-ac4df9e3f309`
  (file "2024-reported-energy-and-water-metrics", posted October 2024).
- Terms: Open Data Commons Public Domain Dedication and License.
- Key fields: `BERDO ID`, `Tax Parcel ID`, `Property Owner Name`,
  `Building Address`, `Reported Gross Floor Area (Sq Ft)`,
  `Largest Property Type`, `Electricity Usage (kWh)`.

Gaps:

- Every value is text. Zip codes have lost their leading zero (`2114`).
- No reporting year column. The year of this file is likely calendar 2023
  and must be confirmed from its data dictionary.
- 3,658 of 5,638 rows have electricity above zero. 71 rows have no parcel
  id.
- `Tax Parcel ID` matches the parcels' `PROP_ID` once padded to 10 digits
  (`303060001` is `0303060001`). That gives an exact join for Boston.
- Two newer files exist only as XLSX, with no datastore API:
  "2025-reported-energy-and-water-metrics" and
  "BERDO Disclosure 2026 (2025 Data)" (5,792 buildings). The 2026 file
  renames several columns and drops `Battery Storage`. Reading XLSX needs
  a library not in the Stack (openpyxl).
- The SQL endpoint (`datastore_search_sql`) returns 403. Only plain
  `datastore_search` works.

## Decisions needed

1. Hospital codes. The plan and success measure 3 name code 979, which
   only Boston uses. Proposal: classify exempt hospitals as 955, 9550,
   955V statewide plus 979 in Boston, and add owner name keywords
   ("HOSPITAL", "MEDICAL CENTER") in Phase 2 to catch cases like `049C`.
2. Missing building area. About 30% of pilot C&I parcels have no
   `BLD_AREA`, and all Brockton C&I parcels lack `YEAR_BUILT`. Proposal:
   in Phase 2, fill missing area from footprint area times stories and
   mark it as estimated. Treat year built as optional.
3. LBER sample size. Only 496 pilot buildings have electricity data.
   Proposal: validate statewide (8,487 buildings) with town holdout, and
   report pilot numbers separately. The calendar 2025 release on
   October 31, 2026 may add more.
4. Utility join. Territories are town outlines, so a `TOWN_ID` join gives
   the same answer as a spatial join. Proposal: join on `TOWN_ID` and
   flag the 18 mixed towns as unknown utility.
5. BERDO year. Proposal: load the datastore file now, and decide whether
   to add openpyxl so the newer 2025 data year can be loaded too.
