<!-- Written by hand. make match-rates copies this file into the Hand review
section of docs/MATCH_RATES.md, so edit it here. -->

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
