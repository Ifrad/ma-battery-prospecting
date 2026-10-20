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

## Manual spot check

Three random commercial parcels from `raw_parcels` were checked by hand
against the Massachusetts Interactive Property Map in October 2026.

| Parcel | Result |
|---|---|
| 683 Southbridge St, Auburn | Owner, address and use code 3220 match. The map shows 7,186 sq ft, which is its Residential Area field. Our 8,146 sq ft is `BLD_AREA`, the gross building area. |
| 7-9 Chocksett Road, Sterling | Owner, address, use code 4020 and 9,990 sq ft match. The owner's mailing address is a P.O. Box in the same town. |
| 1129 Auburn St, Whitman | Owner and address match. The map shows use 104 (two-family, 1,924 sq ft). Our sample showed 332 (auto repair, 2,280 sq ft). Both are right: see below. |

1129 Auburn St in Whitman is two separate parcels with the same owner
(BOYER ELPHEGE H) and the same site address. They touch, and each has one
record:

| LOC_ID | Parcel id | Use code | BLD_AREA | RES_AREA | Land area |
|---|---|---|---|---|---|
| M_243849_869416 | 23A-8-361 | 104, two-family | 3,748 | 1,924 | 1,615 m2 |
| M_244061_869448 | 23A-8-362A | 332, auto repair | 2,280 | 2,280 | 52,271 m2 |

The map lookup by address landed on the house lot. The random sample
landed on the auto repair lot next to it. The map's 1,924 sq ft is again
`RES_AREA`, not `BLD_AREA`.

What this shows:

- Building area must come from `BLD_AREA`. The map's headline area is
  `RES_AREA`.
- A site address is not a unique key. One address can cover several
  parcels, which matters when matching LBER buildings by address.
- Several records on one parcel is a separate, real pattern. In the pilot,
  3,391 of 295,078 parcels (by `LOC_ID`) have more than one record,
  34,328 records in all, up to 361 on one parcel (condominiums). 304 of
  those parcels have a C&I record, and 52 mix residential (1xx) and C&I
  records.
- An owner mailing address in the same town, including a P.O. Box, is a
  usable sign of a local owner.

## Decisions taken

After review, recorded in PLAN.md on 2026-10-19:

1. Hospitals are state codes 955 and 9550, Boston code 979, or an owner
   name containing HOSPITAL or MEDICAL CENTER. `955V` is vacant land, not
   a hospital. Owner names containing HEALTH are other healthcare.
2. Missing `BLD_AREA` is filled from footprint area times stories, or
   footprint area alone, and flagged as estimated. Year built is optional.
3. LBER zero or negative grid electricity is missing, never zero.
   Validation is statewide, with the pilot towns reported separately.
4. Utilities join on `TOWN_ID`. Multi-provider towns are flagged as
   unknown utility.
5. BERDO moves to PLAN.md's Later section.

## Site table rules

`make sites` rebuilds `parcels` and `buildings` from the raw tables. The SQL
is in `sql/sites/`.

Parcels, one row per polygon (`LOC_ID`). When a polygon has several
assessor records (3,391 in the pilot, mostly condo units and ground leases,
often with different owners):

- Owner, address, use code, stories and year built come from the record
  with the largest `BLD_AREA`. Ties go to a record with a use class, then
  the lowest object id.
- `bld_area` is the sum of the records' `BLD_AREA`, since units and leases
  add up. When every nonzero value is the same (652 polygons), it counts
  once. `RES_AREA` is never used.
- `mixed_res_ci` is set when one record is residential (1xx) and another has
  a commercial, industrial or hospital class: 50 polygons. The Phase 1
  count of 52 included 4 polygons whose only C&I record was vacant land
  (`452V`), and missed 2 with multi-use commercial codes (`035R`, `0370`).
- `STORIES` is text. Its leading number is used, and 0 counts as missing.

Buildings, one row per footprint (359,301 in the pilot). Each is linked to
the smallest parcel containing its interior point; 363 lie in no parcel.
Area, in order:

| Area source | Rule | Pilot buildings | On candidate parcels |
|---|---|---|---|
| assessor | parcel `BLD_AREA`, shared by footprint area | 322,938 | 14,746 |
| footprint_x_stories | footprint area times stories | 27,685 | 31 |
| footprint_only | footprint area alone | 8,678 | 873 |

Candidate parcels are those with a commercial, industrial, hospital or
multi-use commercial class. How estimated areas are used is decided after
the footprint area error is measured.

## LBER UBID feasibility

Checked on 2026-10-19, read-only, before choosing any dependency. LBER's
`UBID` field was decoded with a throwaway script (Google's
`openlocationcode`, run outside the project, not added to pyproject.toml
or uv.lock), following PNNL's UBID specification
(https://github.com/pnnl/buildingid/blob/master/SPEC.md): a UBID is the
Open Location Code of the footprint's centroid cell plus its north, east,
south and west extents in grid cells, so it decodes to the footprint's
bounding box snapped outward to whole cells.

Pilot rule: an LBER row is in the pilot when its point lies inside the
town polygon of a pilot town (`raw_utility_territories`). That gives 3,952
rows, slightly more than matching the `City` text field (3,907), which can
name a village or mailing town.

| Region | Pilot LBER rows | With UBID | Box center inside a footprint | Box within one grid cell of a footprint's box | Exact UBID string match |
|---|---|---|---|---|---|
| Metro South | 1,950 | 1,950 | 1,751 (89.8%) | 1,857 (95.2%) | 1,816 (93.1%) |
| Worcester | 2,002 | 2,002 | 1,746 (87.2%) | 1,896 (94.7%) | 1,848 (92.3%) |
| Both | 3,952 | 3,952 | 3,497 (88.5%) | 3,753 (95.0%) | 3,664 (92.7%) |

- Every pilot row has a UBID, and every UBID decodes. All use an 11
  character code, a grid cell of about 2.8 m north to south.
- The exact match encodes a UBID from each nearby MassGIS footprint the
  same way (planar centroid, bounding box) and compares strings. No LBER
  UBID equals more than one footprint's.
- For comparison, the LBER point lies inside a footprint for 88.5% of
  pilot rows and inside a parcel for 99.9%. So DOER built its UBIDs from
  the MassGIS footprints, and an exact UBID match pins a footprint for
  about 4 percentage points more rows (about 170) than the point method.

Ten decoded boxes and the footprint each matched within one cell:

| UBID | Decoded box (south, west, north, east) | Footprint objectid |
|---|---|---|
| 87JC3XMJ+25F-13-13-10-10 | 42.082300, -71.019906, 42.082900, -71.019156 | 4985311 |
| 87JC68V7+QXJ-10-9-10-11 | 42.244200, -71.685469, 42.244725, -71.684812 | 4508625 |
| 87JC7648+49P-9-9-6-10 | 42.255175, -71.784375, 42.255575, -71.783750 | 3114043 |
| 87JC66R3+MG2-8-6-7-6 | 42.241450, -71.796438, 42.241850, -71.796031 | 4578650 |
| 87JC7632+57V-5-7-6-7 | 42.252825, -71.799563, 42.253125, -71.799094 | 3908643 |
| 87JC2XWW+F65-11-13-12-12 | 42.045825, -71.004781, 42.046425, -71.003969 | 4952417 |
| 87JC4W5M+JWG-11-16-12-15 | 42.108750, -71.065656, 42.109350, -71.064656 | 4729092 |
| 87JC3X7R+57R-22-12-22-8 | 42.062425, -71.009625, 42.063550, -71.008969 | 4952163 |
| 87JC54QV+6GJ-9-7-9-6 | 42.187850, -71.856438, 42.188325, -71.856000 | 2926908 |
| 87JC7692+828-14-15-13-18 | 42.267950, -71.800500, 42.268650, -71.799437 | 3452114 |
