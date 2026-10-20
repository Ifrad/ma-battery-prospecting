"""The parts of docs/VALIDATION.md that are written, not measured: peak shape
data search, what is unvalidated, and the limits."""

PEAK_SHAPE = [
    "## Peak shape",
    "",
    "Peak shape is unvalidated: no open interval dataset matched the scored"
    " sites well enough to test it, so it was only stress-tested (above).",
    "",
    "- Building Data Genome 2 (github.com/buds-lab/building-data-genome-project-2),"
    " assessed 2026-10-20 and not used: hourly readings, which cannot test"
    " 15-minute demand peaks; 1,578 buildings with electricity at 19 sites,"
    " mostly university campuses (education 604, office 296) with few of the"
    " scored kinds (warehouse 14, manufacturing 11, healthcare 27); no site in"
    " New England; years 2016 and 2017; licensed CC BY-SA 4.0 (share-alike).",
    "- EnerNOC open data, 100 commercial and industrial sites, 2012: assessed"
    " 2026-10-20, decision pending with the owner (see the Phase 5 plan).",
]

UNVALIDATED = [
    "## What is unvalidated",
    "",
    "- Peak shape: the monthly peak reduction share, load factor and event-window"
    " load all come from ComStock simulation (one weather year, 2018, perfect"
    " foresight reduced by a placeholder realization factor). Stress-tested only.",
    "- ConnectedSolutions delivery: the rate and terms are sourced from the"
    " program documents, but what a block actually delivers in events (the"
    " performance factor, the overlap with the building's own peaks, and"
    " whether the site exports) is a placeholder.",
    "- Installed cost is not in the model. Value per block is gross revenue;"
    " break-even cost is a translation, not a prediction.",
    "- The Eversource rate area for Canton and Sharon is unconfirmed: the rate"
    " is the Greater Boston one, and no Eversource document lists towns by area.",
    "- Factories, laundries, food plants, cold storage and auto repair have no"
    " open load profile: they take the widest simulated range in their size bin.",
    "- Matching LBER rows to buildings is reported in docs/MATCH_RATES.md, but"
    " ownership grouping and keyword segments were only hand-checked on a"
    " small, non-random sample.",
]

LIMITS = [
    "## Limits",
    "",
    "Value per block is a simulated, gross yearly revenue per battery block,"
    " before any host share. It is not profit and not accurate, and no"
    " measurement here supports an accuracy figure for it. What is tested is"
    " the annual energy estimate against LBER, which covers only buildings of"
    " about 20,000 sq ft and up and whose first release has many implausibly"
    " low values, the stability of the ranking under the model's own"
    " uncertainty, and its sensitivity to two data rules. A site's place in"
    " the list is a reason to talk to it, not a forecast of its savings.",
]
