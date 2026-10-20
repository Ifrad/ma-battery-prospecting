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
| 305 private hospital, 979 exempt hospital, 414 food processing | True for Boston only. All 189 parcels coded 979 are in Boston. Other towns use the state DOR code 955 (or 9550) for charitable hospitals, 522 parcels statewide (584 with `955V`, which is vacant land, not a hospital). |
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

Buildings, one row per footprint (359,299 in the pilot: 359,301 footprints
less 2 exact duplicates, same shape and struct id, which are dropped; 5
near-duplicates overlapping another by more than 90 percent are flagged
with near_duplicate_of and kept). Each is linked to
the smallest parcel containing its interior point; 363 lie in no parcel.
Sites group buildings on touching parcels of one owner: 246,364 sites, of
which 9,640 are candidates.

Area is set per site, after grouping (`sql/sites/03_area.sql`):

1. Pooled assessor area: the sum of `bld_area` over the site's parcels that
   have it, each parcel's `bld_area` following the multi-record rule above.
   Pooled footprint area: the sum of footprint area on those same parcels.
2. If pooled assessor area is below pooled footprint area times 0.5, those
   buildings get `assessor_below_footprint`.
3. If it is above pooled footprint area times 3 times the site's highest
   recorded stories, or times 10 when no parcel in the site records
   stories, they get `assessor_above_footprint`.
4. Otherwise they get `assessor`: pooled assessor area shared across those
   footprints in proportion to footprint area. The site's assessor total
   does not change (checked exactly on 219,050 sites).
5. Buildings in step 2 or 3, buildings on parcels with no `BLD_AREA`, and
   buildings on no parcel use footprint area times the parcel's stories,
   or footprint area alone. Steps 2 and 3 keep their flag as the area
   source; the others get `footprint_x_stories` or `footprint_only`.

The 0.5, 3 and 10 are placeholders in `config/sites.yaml` (`area_checks`).
178 sites (33 candidates) have `BLD_AREA` only on parcels with no
footprint, so their assessor area is not used.

| Area source | Pilot buildings | Candidate buildings |
|---|---|---|
| assessor | 308,034 | 12,202 |
| assessor_below_footprint | 14,224 | 2,490 |
| assessor_above_footprint | 678 | 53 |
| footprint_x_stories | 27,685 | 31 |
| footprint_only | 8,678 | 873 |

Candidate buildings are those on parcels with a commercial, industrial,
hospital or multi-use commercial class.

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

### UBID encoder and match detail

The project encodes UBIDs with `openlocationcode==1.0.1` (Google, Apache
2.0, no dependencies) and its own encoder, `prospect/sites/ubid.py`,
which follows PNNL's specification and reference code. The package is
an sdist from 2019; uv builds it cleanly on Python 3.11 and 3.14, and the
OLC and UBID specifications it implements are stable. In a throwaway
environment the encoder gave the same UBID as PNNL's `buildingid==2.3.0`
for 4,019 of 4,019 pilot footprints, including all 19 multipolygons. So
the mismatches below are in the data, not the encoder.

Every building gets a UBID in `make sites`. Exact match rate of pilot
LBER rows against those UBIDs:

| Region | Pilot LBER rows | Exact | Rows with grid electricity | Exact among them |
|---|---|---|---|---|
| Metro South | 1,950 | 1,816 (93.1%) | 608 | 556 (91.4%) |
| Worcester | 2,002 | 1,848 (92.3%) | 558 | 519 (93.0%) |
| Both | 3,952 | 3,664 (92.7%) | 1,166 | 1,075 (92.2%) |

Why the other 288 rows do not match exactly:

| Cause | Metro South | Worcester | Both | With grid electricity |
|---|---|---|---|---|
| One-cell offset: a footprint's box is within one grid cell on every edge, but a corner or the centroid falls in the next cell | 72 | 81 | 153 | 51 |
| Different footprint: footprints nearby, none within one cell (edited, split or merged since DOER encoded it) | 59 | 64 | 123 | 39 |
| No footprint nearby | 3 | 9 | 12 | 1 |

The point-in-footprint and point-in-parcel methods cover these rows.

Pilot rule, rechecked: the town polygon rule adds 50 rows whose `City`
is not a pilot town and drops 5 whose `City` is, a net 45. The 50 are
mostly villages of pilot towns (South Easton 22, North Easton 12,
Whitinsville 3, North and South Grafton 4, North Oxford 2), a few
neighboring town names (Plympton 2, Bellingham, New Braintree,
Weymouth) and two wrong ones (Andover, and Shrewsbury on a point in
Metro South). The point location is more reliable than the `City` text.

## LBER matching

`make sites` matches each pilot LBER row, once per reporting year, to one
building (`lber_matches`). Pilot rule: the LBER point lies inside a pilot
town's polygon. Methods run in order and stop at the first that finds a
building: exact UBID, point inside a footprint, point inside a parcel,
normalized address. When a method finds several buildings, the largest
footprint is used and the confidence reads "ambiguous, n buildings", so
one LBER row never gives kWh to two buildings. Confidence labels and
address abbreviations are placeholders in `config/sites.yaml`.

| Region | Pilot rows | UBID | Point in footprint | Point in parcel | Address | Unmatched |
|---|---|---|---|---|---|---|
| Metro South | 1,950 | 1,816 (93.1%) | 117 (6.0%) | 15 (0.8%) | 0 | 2 |
| Worcester | 2,002 | 1,848 (92.3%) | 117 (5.8%) | 29 (1.4%) | 0 | 8 |
| Both | 3,952 | 3,664 (92.7%) | 234 (5.9%) | 44 (1.1%) | 0 | 10 |

- 35 of the 44 parcel matches are ambiguous (up to 51 buildings on one
  parcel); 8 of those 35 have grid electricity.
- The 10 unmatched rows (`lber_unmatched`) all lie on a parcel with no
  footprint; 1 has grid electricity. The address method found none.
- A building's electricity source is measured only through a matched row
  with grid electricity, from its latest reporting year. 1,165 of the
  1,166 pilot rows with grid electricity are matched, each to a different
  building.

## Footprint area error

Measured on 2026-10-19 to decide how estimated building areas are used.
The decision is at the end of this section. Error is the absolute percent difference
between the estimate and the reference.

Against assessor `BLD_AREA`, at parcel level, since assessor area is
shared across a parcel's footprints: footprint_x_stories is the sum of
the parcel's footprint areas times its stories; footprint_only is that
sum alone. Parcels with known `BLD_AREA`, known stories and at least one
footprint.

| Parcels | n | footprint_x_stories median | p90 | footprint_only median | p90 |
|---|---|---|---|---|---|
| All | 218,105 | 31% | 66% | 46% | 66% |
| Candidate | 8,439 | 17% | 98% | 22% | 73% |
| Candidate, Metro South | 3,238 | 15% | 88% | 18% | 67% |
| Candidate, Worcester | 5,201 | 19% | 104% | 26% | 75% |

Another 6,839 parcels (1,203 candidates) have `BLD_AREA` and a footprint
but no stories, so only footprint_only could apply to them.

Against LBER `Gross_Floor_Area`, at building level, for buildings matched
by UBID or point in footprint with a single candidate. The assessor row
is the parcel's `BLD_AREA` share on that building, for reference.

| Matched buildings | Estimate | n | Median | p90 |
|---|---|---|---|---|
| All | footprint_x_stories | 3,144 | 20% | 78% |
| All | footprint_only | 3,891 | 50% | 75% |
| All | assessor share | 3,721 | 19% | 92% |
| Candidate | footprint_x_stories | 1,797 | 17% | 77% |
| Candidate | footprint_only | 2,111 | 32% | 68% |
| Candidate | assessor share | 2,068 | 5% | 77% |

- On candidates, footprint_x_stories has the lower median but a long
  tail: its 90th percentile (98% against `BLD_AREA`) is worse than
  footprint_only (73%), which points to unreliable stories values on
  some commercial parcels.
- Against LBER, the assessor share is closest at the median (5% on
  candidates), and both footprint estimates are clearly worse.

### Fields that could hold height, stories or type

The footprints carry no height, stories or floors. Their fields describe
source and editing only; one comment out of 359,301 mentions height. They
are roof outlines (`SOURCETYPE` ROOFPRINT 157,600 and ROOFPRINT_SHIFTED
200,994) except 707 true footprints, so they include roof overhangs.

Parcel fields, records with a usable value:

| Field | All records (326,015) | Candidate primary records (14,207) |
|---|---|---|
| `STORIES` (above 0) | 248,999 (76%) | 8,885 (63%) |
| `STYLE` (building style text) | 303,794 (93%) | 10,943 (77%) |
| `NUM_ROOMS` | 252,207 (77%) | 357 (3%) |
| `UNITS` | 72,253 (22%) | 919 (6%) |
| `BLD_AREA` | 255,713 (78%) | 10,184 (72%) |
| `RES_AREA` (never used for area) | 276,394 (85%) | 9,107 (64%) |
| `YEAR_BUILT` | 277,153 (85%) | 9,141 (64%) |
| `USE_CODE`, `USE_DESC` | 324,297 (99%) | 14,207 (100%) |

`STORIES` is the only height field. `STYLE` and the use code describe
building type.

### Direction of the error

Same parcel-level comparison as above. The ratio is estimate divided by
`BLD_AREA`; below 1 means the estimate is too low. Error is the absolute
percent difference.

| Parcels | n x stories | Ratio median | Error median | p90 | n footprint only | Ratio median | Error median | p90 |
|---|---|---|---|---|---|---|---|---|
| All with `BLD_AREA` and a footprint | 218,105 | 0.84 | 31% | 66% | 224,944 | 0.56 | 46% | 66% |
| Candidates | 8,439 | 1.03 | 17% | 98% | 9,642 | 0.98 | 22% | 72% |
| Candidates, commercial_industrial | 7,360 | 1.03 | 15% | 86% | 8,501 | 0.99 | 18% | 69% |
| Candidates, hospital | 35 | 0.97 | 28% | 84% | 48 | 0.41 | 60% | 73% |
| Candidates, mixed_commercial_industrial | 1,044 | 1.12 | 32% | 231% | 1,093 | 0.63 | 51% | 119% |
| Candidates, 1 footprint | 6,265 | 1.00 | 13% | 53% | 7,237 | 0.95 | 17% | 63% |
| Candidates, 2 to 3 footprints | 1,747 | 1.25 | 32% | 194% | 1,940 | 1.06 | 33% | 145% |
| Candidates, 4 or more footprints | 427 | 2.50 | 150% | 1057% | 465 | 1.96 | 96% | 879% |
| Candidates with no stories | | | | | 1,203 | 0.96 | 21% | 67% |

On all parcels, mostly homes, both estimates run low. On candidates they
are centered, and close for single-footprint parcels. Parcels with several
footprints run far too high: the next part shows why.

Of the 20 worst candidate mismatches (`data/area_review.csv`, not
committed, with satellite links), 11 involved a footprint straddling a
parcel line, 8 a tiny or partial `BLD_AREA` (84 to 1,702 sq ft on large
buildings) and 1 neither. Across all 15,650 candidate buildings, 569
overlap a second parcel by more than 20% of their footprint (607 pairs:
186 in the same site, 421 across sites). That led to the site pooling and
area checks in "Site table rules".

### Use code ratios, towns held out

A third estimate was tested and not adopted: footprint area times the
median `BLD_AREA` to footprint ratio of the parcel's use code (first three
characters), or of its use class when the code has under 30 parcels,
learned only on other towns (each town held out in turn). Candidate parcels
with `BLD_AREA`:

| Parcels | n | Ratio estimate median | p90 | Footprint only median | p90 | n with stories | x stories median | p90 |
|---|---|---|---|---|---|---|---|---|
| All candidates | 9,642 | 20% | 86% | 22% | 72% | 8,439 | 17% | 98% |
| commercial_industrial | 8,501 | 17% | 76% | 18% | 69% | 7,360 | 15% | 86% |
| hospital | 48 | 38% | 127% | 60% | 73% | 35 | 28% | 91% |
| mixed_commercial_industrial | 1,093 | 39% | 261% | 51% | 120% | 1,044 | 32% | 232% |
| Use code 340 (offices) | 948 | 33% | 99% | 46% | 69% | 788 | 24% | 59% |
| Use code 316 (warehouses) | 827 | 11% | 95% | 12% | 97% | 729 | 11% | 134% |
| Use code 400 (manufacturing) | 833 | 10% | 65% | 9% | 64% | 722 | 9% | 92% |

Against LBER `Gross_Floor_Area` (2,111 matched candidate buildings): ratio
estimate 25% median, 67% p90; footprint only 32%, 68%; footprint x stories
(1,797 with stories) 17%, 77%. No clear gain over the two existing
estimates, so it is recorded only.

### After site pooling and the area checks

Site level (summed footprints on the site's `BLD_AREA` parcels against
pooled `BLD_AREA`), next to the parcel-level numbers above:

| Sites | Estimate | Parcel level n | Median | p90 | Site level n | Median | p90 |
|---|---|---|---|---|---|---|---|
| Candidates | footprint_x_stories | 8,439 | 17% | 98% | 8,119 | 17% | 93% |
| Candidates | footprint_only | 9,642 | 22% | 72% | 9,284 | 23% | 71% |
| All | footprint_x_stories | 218,105 | 31% | 66% | 215,803 | 31% | 66% |
| All | footprint_only | 224,944 | 46% | 66% | 222,529 | 46% | 66% |

Building level, each building's stored area against LBER
`Gross_Floor_Area`, before and after (UBID or point matches with a single
candidate):

| Buildings | Before n | Median | p90 | After n | Median | p90 |
|---|---|---|---|---|---|---|
| Candidates, any area source | 2,111 | 5% | 77% | 2,111 | 6% | 66% |
| Candidates, assessor source | 2,068 | 5% | 77% | 1,916 | 4% | 63% |
| All matched, any area source | 3,891 | 22% | 92% | 3,891 | 17% | 71% |
| All matched, assessor source | 3,721 | 19% | 92% | 3,165 | 10% | 70% |

For the 148 matched candidate buildings now flagged
`assessor_below_footprint`, the footprint fallback is closer to LBER than
the old assessor share for 133 (median error 50% against 88%). Of the 20
worst mismatches, 15 are now flagged (10 below, 5 above) and 5 are fixed by
pooling within their site.

### Area decision

Decided on 2026-10-19:

- All area sources stay: assessor, assessor_below_footprint,
  assessor_above_footprint, footprint_x_stories and footprint_only.
  Everything other than assessor is flagged as estimated.
- The measured error of each estimated source is carried into the model as
  wider uncertainty (PLAN.md, Phase 4). The widths go in config as measured
  values from this section, not as placeholders.
- The error was measured only on parcels that have `BLD_AREA`. The real
  error on parcels missing it may be larger.
