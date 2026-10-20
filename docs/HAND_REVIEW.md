<!-- Written by hand. make match-rates copies this file into the Hand review
section of docs/MATCH_RATES.md, so edit it here. -->

### Review results

The sample had 32 rows: 5 owner groups, 22 segment rows (up to 3 sites
per segment) and 5 parcels with identical assessor areas. The owner
reviewed 2 of the 32 rows using aerial photos, on 2026-10-19 and
2026-10-20. Row numbers refer to segments.csv as first drawn, before the
keyword fix. A rebuild after the fix draws a different sample.

- Row 7, PERFORMANCE FOOD GROUP, 1100 Pearl St, Brockton, was labeled
  food production and looks like a large warehouse. Its assessor code is
  400 (manufacturing) and the site is 105,770 sq ft, so it still gets food
  production. It is a known miss. The other sources disagree: LBER lists
  the building as warehouse or storage, while the company's
  [facility listing](https://www.performancefoodservice.com/products-and-services/custom-solutions/custom-cut-meats)
  names a meat cutting plant at this address (checked 2026-10-20).
- Row 8, JJ'S CREAMERY, 167 Milford St, Upton, is a small eatery that was
  labeled food production. It has code 326 and 1,640 sq ft, and is now
  generic.

The HOSPITALITY owners that matched the hospital keyword were found from
the keyword counts, not from the review. Whole word matching fixes them.

The other 30 rows are not reviewed. The owner group, hospital and
identical area samples are unchecked. The four keyword hospital sites
that remain are unverified, and two of them look like medical office
buildings: VERNON MEDICAL CENTER II (Worcester region) and HTA PEARL ST
MEDICAL CENTER LLC (Metro South). The other two are HARRINGTON MEMORIAL
HOSPITAL and FAIRLAWN HOSPITAL INC.

The two rows were picked because they looked suspicious, so they are not
a fair estimate of the error rate. The keyword fix improved precision on
14 of 9,640 candidate sites. Recall is not measured.

### Limits of the area sources

The [MassGIS parcel standard](https://www.mass.gov/doc/standard-for-digital-parcels-and-related-data-sets-version-3/download)
says BLD_AREA may mean gross, adjusted gross or finished area, depending
on the town. The
[DOER white paper, page 26](https://www.mass.gov/doc/2026-large-building-energy-reporting-white-paper/download)
says LBER building sizes mostly come from assessor data, with geospatial
estimates where needed, and that a parcel total was sometimes given to
single buildings. So comparing our areas with LBER measures agreement
between sources, not accuracy.

### Still needed

- A random review of owner grouping, mixed use records, keyword
  precision and assessor record pooling, large enough to estimate error
  rates.
- Building specific evidence for disputed areas and operating types.
- Confirmation of meter boundaries before an outreach site is treated as
  one battery installation.

### Segment changes from the keyword fix

The fix in `fix(sites): constrain owner keyword classifications` changed
the segment of 14 of the 9,640 candidate sites. No other site changed.
Areas are site areas in sq ft.

| Owner | Town | Before | After | Reason |
|---|---|---|---|---|
| AUBURN HOSPITALITY INC | Auburn | hospital (keyword) | generic | HOSPITALITY is not the whole word HOSPITAL |
| KARM HOSPITALITY LLC | Brockton | hospital (keyword) | generic | HOSPITALITY is not the whole word HOSPITAL |
| LNL HOSPITALITY LLC | Sturbridge | hospital (keyword) | generic | HOSPITALITY is not the whole word HOSPITAL |
| SHRI KRISHNA HOSPITALITY LLC | Sturbridge | hospital (keyword) | generic | HOSPITALITY is not the whole word HOSPITAL |
| SOMERSET HOSPITALITY LLC | Auburn | hospital (keyword) | generic | HOSPITALITY is not the whole word HOSPITAL |
| HOLDEN VETERINARY HOSPITAL, LLC | Holden | hospital (keyword) | other_healthcare (use code 342) | VETERINARY excludes the hospital keyword |
| JJ'S CREAMERY INC | Upton | food_production (keyword) | generic | Code 326, 1,640 sq ft: no 4xx code, under 20,000 sq ft |
| D E FOODS LLC | Stoughton | food_production (keyword) | generic | Code 326, 2,177 sq ft: no 4xx code, under 20,000 sq ft |
| D E FOODS LLC | Norwell | food_production (keyword) | generic | Code 326, 3,195 sq ft: no 4xx code, under 20,000 sq ft |
| D.E. FOODS LLC | Bridgewater | food_production (keyword) | generic | Code 326, 3,036 sq ft: no 4xx code, under 20,000 sq ft |
| NEW ENGLAND ROAST BEEF AND SEAFOOD LLC | Auburn | food_production (keyword) | generic | Code 326, 2,591 sq ft: no 4xx code, under 20,000 sq ft |
| SALTOS LIQUORS & FOOD LLC | Brockton | food_production (keyword) | generic | Code 325, 1,936 sq ft: no 4xx code, under 20,000 sq ft |
| BEACH HOUSE BREWING LLC | Charlton | food_production (keyword) | generic | Code 340, 4,324 sq ft: no 4xx code, under 20,000 sq ft |
| HONG LUNG SEAFOOD CO. INC | Holbrook | food_production (keyword) | warehouse (use code 316) | Code 316, 3,938 sq ft: no 4xx code, under 20,000 sq ft |

The new plural and variant keywords gave no site a new segment.
