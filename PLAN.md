# PLAN.md

Build plan for the Massachusetts battery prospecting tool. Each phase is one
branch and one pull request. Each checkbox is one commit. Tick boxes in the
same commit that does the work.

Phase 0 is the exception. Its first commit goes directly on main so branch
protection has a base, and `phase-0-foundation` starts after it. PLAN.md is
not tracked until the second commit, so that commit ticks both boxes.

## The problem in one paragraph

Utilities bill commercial customers a demand charge based on their single
highest 15-minute spike each month. A battery can shave that spike. A company
that installs batteries at no upfront cost and shares the savings earns money
only if the site has large, predictable peaks, so choosing sites is choosing
revenue. Before a business shares meter data, nobody knows its peak. This tool
estimates it from public data and ranks sites by value per battery block: the
simulated yearly demand savings plus grid program revenue one standard battery
block could bring, gross, before any host share, with a band and the reasons,
grouped by region. Cost and profit are not modeled: the operator applies
its own installed cost and host share.

## What "better than size ranking" means, measurably

1. On buildings with reported grid electricity in DOER LBER, the model's
   annual kWh estimate beats a size-only estimate on Spearman correlation
   and median absolute percent error, with whole towns held out. Measured
   statewide, with the pilot towns reported separately. Zero or negative
   grid electricity counts as missing, never as zero.
2. Every site shows its value per block with a P10 to P90 band and its
   evidence flags, not a single point estimate. The annual energy
   estimate behind it is checked for calibration. Peak shape is
   unvalidated until real interval meter data tests it.
3. Nonprofit hospitals are included rather than silently filtered out:
   state code 955 or 9550, Boston code 979, or an owner name containing
   the whole word HOSPITAL or MEDICAL CENTER and not VETERINARY. Vacant
   land (`955V`) is not a hospital.
4. Every ranked site has an owner name and site address for outreach.

## Verified facts this plan relies on

- MassGIS L3 parcels include owner1, site_addr, bld_area, year_built, ls_date
  and use_code, and are served as a hosted ArcGIS feature layer with a 2,000
  record page size. In the pilot towns about 30% of commercial parcels have
  no bld_area, and Brockton has no year_built for any of them.
- Boston's assessor code list has 305 for private taxable hospitals, 979 for
  exempt hospitals and 414 for food processing plants. Code 979 is used
  only in Boston. Other towns use the state code 955 (or 9550) for
  charitable hospitals.
- DOER's Large Building Energy Reporting covers buildings of 20,000 sq ft or
  more statewide. Utilities report usage, DOER publishes by October 31 each
  year, and the first release (calendar 2024) is incomplete: 74% of its
  buildings report zero grid electricity.
- MassGIS electric providers are listed per town, keyed by TOWN_ID. 18 towns
  list more than one provider.
- NREL's End-Use Load Profiles (ComStock) publish 15-minute profiles by
  commercial building type.

Checked in Phase 1 on 2026-10-19. Details are in docs/DATA.md. Anything not
on this list gets verified before it is relied on.

## Pilot scope

Start with two regions I chose: Metro South (Brockton) and Worcester, each
defined by its chamber of commerce's service area. Nothing here claims where
Powertown operates. Statewide comes after the pilot works.

---

## Phase 0: Foundation  (branch `phase-0-foundation`, tag v0.0.1)

Goal: an empty repo that lints, tests and runs CI.
Done when: `make check` passes locally and in CI with a placeholder test.

- [x] `chore: initialize repository` (directly on main)
      README with a one-line purpose and a "work in progress" note, MIT
      LICENSE, .gitignore (data/* except data/README.md, .env and .env.*
      except .env.example, venvs, caches, node_modules, dist, .DS_Store),
      .editorconfig.
- [x] `docs: add Claude Code instructions and build plan`
      CLAUDE.md and PLAN.md.
- [x] `chore: add Python project tooling`
      pyproject.toml, ruff config, pytest config, Makefile with `check`,
      empty `prospect/` package, one placeholder test.
- [x] `chore(db): add PostGIS via docker compose`
      docker-compose.yml, .env.example, `make db-up` and `make db-down`.
- [x] `ci: run lint and tests on push and pull request`
      GitHub Actions workflow for Python.

Kickoff prompt:

    Read CLAUDE.md and PLAN.md. We are continuing Phase 0 on branch
    phase-0-foundation. Do only the first unchecked task, run make check,
    show me the staged diff stat and commit message, then stop.

---

## Phase 1: Source verification and ingestion  (branch `phase-1-ingestion`, tag v0.1.0)

Goal: every source loads into Postgres reproducibly, with provenance.
Done when: `make ingest` loads all sources for both pilot regions, a second
run adds no duplicate rows, and `ingest_runs` shows row counts and hashes.

- [x] `feat(ingest): add HTTP client with retries and rate limiting`
      httpx plus tenacity, exponential backoff, a polite delay between pages,
      a user agent. Tests use a mocked transport.
- [x] `feat(db): add migration runner and provenance table`
      Numbered SQL migrations, `make migrate`, an `ingest_runs` table with
      source, url, started_at, finished_at, rows, sha256 and status.
- [x] `feat(ingest): add schema probe for data sources`
      A command that fetches one page from each source and prints field
      names and types. No database writes.
- [x] `docs(data): record source schemas, licenses and gaps`
      docs/DATA.md from the probe output. Note anything in "Verified facts"
      that turned out wrong and stop if a core field is missing.
- [x] `feat(config): define pilot regions by chamber territory`
      config/regions.yaml mapping chamber name to towns, each with the URL
      the town list came from. Start with Brockton and Worcester only and
      add towns by hand from the chambers' own sites.
- [x] `feat(ingest): load MassGIS L3 parcels for pilot regions`
      Paged feature service queries, resumable by object id, upsert into
      `raw_parcels`. Each load records its fetch date and row count in
      `ingest_runs`. Fixture-based tests for paging and idempotency.
- [x] `feat(ingest): load building footprints and utility territories`
      Into `raw_footprints` and `raw_utility_territories`. Utilities are a
      per-town table, joined later on TOWN_ID.
- [x] `feat(ingest): load DOER large building energy data`
      Into `raw_lber`. The layer URL and reporting year live in config,
      since each October 31 release is likely a new layer. Record the
      reporting year on every row. Zero or negative grid electricity is
      stored as missing.
- [x] `chore(ingest): add ingest summary report`
      `make ingest` prints rows per source and region and any failures.

Kickoff prompt:

    Read CLAUDE.md and PLAN.md. Start Phase 1 on branch phase-1-ingestion.
    Begin with the schema probe tasks before writing any loader, and stop
    to show me docs/DATA.md before continuing.

---

## Phase 2: Sites  (branch `phase-2-sites`, tag v0.2.0)

Goal: collect evidence, no scoring. Two levels: buildings (MassGIS
footprints) are the unit for energy and peak estimates, and outreach sites
group buildings on touching parcels with the same normalized owner, within
one town. Building area is set per site, after grouping. Every building
and site carries evidence flags that say how much of its data is measured
and how much is estimated.
Done when: buildings and sites exist for both pilot regions with their
evidence flags, the LBER match rate is reported by method (UBID exact match
first) in docs/MATCH_RATES.md, exempt hospitals appear, and the footprint
area error is recorded in docs/DATA.md.

`make sites` rebuilds the tables `use_code_classes`, `pilot_towns`,
`parcels`, `buildings`, `sites`, `lber_matches` and `lber_unmatched` in
one transaction. The views `building_evidence` and `site_evidence` read
from them.

Evidence flags, per building and per site:

- electricity source: measured only through a matched LBER row with
  usable grid electricity, from its latest reporting year, otherwise
  estimated
- area source: assessor, assessor_below_footprint,
  assessor_above_footprint, footprint_x_stories or footprint_only
- LBER match method and confidence
- utility: known, municipal, or unknown (multi-provider towns, none in
  the pilot)
- segment, and how it was assigned (use code, owner keyword or default)
- local owner: owner mailing state MA (or blank) and owner city equal to
  the parcel's town, or the same ZIP; P.O. boxes count like any address
- mixed residential and C&I parcel
- tenure, missing when the latest sale is nominal

- [x] `feat(db): keep LBER reporting years side by side`
      `raw_lber` holds one release today and is keyed on object id alone.
      Add the reporting year to its key so a new October 31 release is
      loaded next to the old one instead of replacing it.
- [x] `feat(config): add assessor use code classes`
      config/use_codes.yaml: 300 to 499 as commercial and industrial, plus
      exempt hospitals (955 and 9550 statewide, 979 in Boston), with each
      code's source. Normalize 4 character codes such as `9550`. A fourth
      character `V` means vacant land (`955V` is "EXEMPT VACANT LAND"), so
      those codes are never a hospital, even when the owner name matches.
      Mark codes not yet checked against the statewide list as placeholders.
      Two placeholder classes were added: mixed_commercial_industrial for
      the multiple-use codes 03x and 04x, a candidate class because
      Worcester's largest hospital parcel is coded 049C, and
      charitable_former for the retired 905 code, which is not a
      candidate. So a hospital still under 905 is not ranked: a known
      limitation, not tested.
      Municipal sites are not covered by these classes yet. Whether to add
      a municipal class is an open decision for the owner.
- [x] `feat(sites): build the building table from footprints and parcels`
      SQL migration creating `parcels`, one row per polygon, and
      `buildings`, one row per footprint, linked to the smallest parcel
      containing its interior point (363 lie in no parcel), with owner,
      site address, use code, year built (optional) and geometry. Parcels
      with several records (3,391 in the pilot) take owner, address, use
      code, stories and year built from the record with the largest
      `BLD_AREA`, and sum `BLD_AREA` unless every nonzero value is the
      same. 50 polygons that mix residential and C&I records are flagged;
      the Phase 1 count of 52 included vacant land and missed two
      multi-use codes (docs/DATA.md). Area comes from `BLD_AREA`, never
      `RES_AREA`, otherwise footprint area times stories, otherwise
      footprint area alone. The area allocation fix below moved this to
      the site level with five area sources. No size floor: keep every
      building and let the model decide.
- [x] `feat(sites): group buildings into outreach sites`
      A site is the buildings on touching parcels with the same normalized
      owner, within one town, for every owner, not only hospitals.
      Touching is measured in Massachusetts State Plane meters
      (EPSG:26986), with a 1 m tolerance (placeholder, `touch_tolerance_m`
      in config/sites.yaml). Normalize owner names first: punctuation is
      removed and the company words in config/sites.yaml are dropped (THE,
      INC, CORP, CO, COMPANY, LLC, LTD and long forms), since one owner
      appears as `BROCKTON HOSPITAL`, `... INC` and `... COMPANY THE`. A
      name within one character of the longest owner name in its town is
      treated as cut off: its last word is dropped and it may join a
      longer name that starts with it. This also joins cases like 1129
      Auburn St, Whitman: two touching parcels, one owner, one address.
      Scattered parcels of one owner stay separate sites.
- [x] `feat(sites): compute UBIDs for footprints`
      Unique Building Identifiers from the MassGIS footprints, so LBER's
      `UBID` field can be matched exactly. Computed with
      `openlocationcode==1.0.1` and our own encoder following PNNL's UBID
      specification, not PNNL's buildingid package: it reproduces DOER's
      UBIDs on the pilot data (92.7% of pilot LBER rows match a footprint
      exactly) and agrees with buildingid 2.3.0 on 4,019 of 4,019 sampled
      footprints. buildingid was not added because it brings in shapely,
      pyqtree, click, click-log, tldm and pandas 3, none of which the
      encoder needs, and it gives the same UBIDs. Feasibility check and
      match detail in docs/DATA.md.
- [x] `feat(sites): match buildings to LBER records`
      An LBER row is in the pilot when its point lies inside a pilot
      town's polygon (3,952 rows), and it matches once per reporting year.
      In order, stopping at the first that works: (1) exact UBID match,
      (2) LBER point inside a footprint, (3) point inside a parcel,
      (4) normalized address. When a method finds several buildings, the
      largest footprint is used and the match is flagged ambiguous, so one
      row never gives kWh to two buildings. Record the method and a
      confidence (placeholder labels) for every match, and keep a table
      of unmatched LBER rows. Report the UBID exact match rate first. Only
      rows with usable grid electricity make a building measured.
- [x] `feat(sites): assign electric utility and flag municipal light plants`
      Join on TOWN_ID, no spatial join. Utility flag is known, municipal,
      or unknown for multi-provider towns. In the pilot, six towns have a
      municipal light plant: Boylston, Holden, Paxton, Princeton, Sterling
      and West Boylston. No pilot town lists several providers, so no
      pilot site is unknown.
- [x] `feat(sites): assign segments from use codes and owner text`
      Cold storage, food production, laundry, hospital, other_healthcare,
      manufacturing, warehouse, generic. Keyword rules in config with
      tests, and a flag for how each segment was assigned. Hospital owner
      keywords: HOSPITAL, MEDICAL CENTER. HEALTH goes to other_healthcare.
      A site takes the segment of its candidate building with the most
      area.
- [x] `fix(sites): constrain owner keyword classifications`
      Keywords match whole words, with plural and variant forms listed in
      config. A VETERINARY exclusion applies to the hospital keyword rule
      only, never to a hospital use code. A food keyword needs a 4xx use
      code or at least 20,000 sq ft of site area (placeholder). No
      distributor exclusions. The 4 remaining keyword hospital sites are
      unverified.
- [x] `feat(sites): add local owner and tenure signals`
      Local owner: the owner mailing state is MA (or blank) and the owner
      city is the parcel's town, or the owner ZIP is the parcel ZIP. P.O.
      boxes count like any address. Tenure: years since the latest sale,
      as a rough proxy for a locally rooted business. L3 keeps only the
      latest sale, so tenure is missing when that sale is nominal (under
      $1,000 or no price, placeholder). Sale dates before 1900 are filler.
- [x] `feat(sites): collect evidence flags per building and per site`
      One place to read every flag listed above, for both levels: the
      views `building_evidence` and `site_evidence`. A site's flags
      summarize its buildings (for example, how many have measured
      electricity).
- [x] `docs(data): measure footprint area error`
      Compare footprint-based area with `BLD_AREA` at parcel level, and
      with LBER `Gross_Floor_Area` for matched buildings: median and 90th
      percentile error for footprint_x_stories and footprint_only, on all
      parcels with known `BLD_AREA` and stories and on candidates
      separately. docs/DATA.md also records the direction of the error, a
      use code ratio estimate that was tested and not adopted, the error at
      site level after pooling, and the decision: all five area sources
      stay, every source other than assessor is flagged as estimated, and
      the measured error sets the Phase 4 width.
- [x] `docs(data): generate match rate report`
      docs/MATCH_RATES.md, written by `make match-rates`, with counts by
      region, segment and match method, where LBER points land, the gaps
      behind the 1 m touch tolerance, the 979 parcel count and the `049C`
      parcel in the Worcester Memorial site. The hand review sample in
      `data/review/` was 5 owner groups, up to 3 sites per segment (22
      rows) and 5 multi-record parcels whose identical `BLD_AREA` values
      were counted once: 32 rows. Only 2 of the 32 were reviewed. The
      report's Hand review section comes from docs/HAND_REVIEW.md.

Phase 2 deviations:

- Planar meters (`fix(sites): measure parcel touching in planar meters`).
  The geography version of the 1 m touch test called 168 pilot parcel
  pairs touching that are 3 to 315 m apart, and two rebuilds gave
  different sites. Distance is now planar in Massachusetts State Plane
  meters.
- Area allocation (`fix(sites): pool assessor area per site and check it
  against footprints`). Assessor area shared within one parcel gave a
  footprint that straddles a parcel line the wrong parcel's area, and
  spread tiny `BLD_AREA` values over large roofs. Area is now pooled per
  site, with a floor check (0.5) and a ceiling check (3 times the site's
  highest stories, or 10), both placeholders in config/sites.yaml.
- Segment keyword fix (`fix(sites): constrain owner keyword
  classifications`). Matching at the start of a word made HOSPITALITY
  owners hospitals and small eateries food production. It changed 14 of
  9,640 candidate sites.

Phase 2 follow-up (migration 0016, made on `phase-4-model` before any
model code, after a schema review found integrity gaps):

- Exact duplicate footprints (2 in the pilot, same shape and struct id)
  are dropped, so their area is not counted twice; 5 near-duplicates
  (overlap over 90 percent, a placeholder) are flagged in
  `near_duplicate_of`.
- Parcels in a group with no building keep no `site_id` (33,051), so
  `parcels.site_id` can reference `sites`. New foreign keys:
  `parcels.site_id` and `sites.main_loc_id` (checked at commit), and
  `lber_matches` and `lber_unmatched` to `raw_lber` (removed with it).
- `buildings.town_id` is renamed `footprint_town_id`: at town lines it
  differs from the parcel's town (175 buildings), which is the one to use.
- Check constraints on segment, segment source and LBER match confidence.
- `make db-check` fails if a copied column drifts from its source.
- Effect: buildings 359,301 to 359,299, candidate buildings 15,650 to
  15,649; sites, candidate sites (9,640), LBER matches and funnel
  survivors (251 at 200 kW, 347 at 150 kW) unchanged. The touch tolerance
  table in docs/MATCH_RATES.md now leaves out pairs of parcels with no
  building.

---

## Phase 3: Priors and rates  (branch `phase-3-priors`, tag v0.3.0)

Goal: every model input is either sourced from public data or visibly marked
as a placeholder. Simulated values say they are simulated, and a
placeholder with no value yet says so rather than holding an invented
number.
Done when: `prospect priors --list-placeholders` prints the remaining
placeholders and each sourced value names its source.

- [x] `feat(config): add National Grid demand rate from its tariff`
      Read the demand charge in dollars per kW-month from National Grid's
      filed Massachusetts tariff. It serves 45 of the 53 pilot towns.
      config/rates.yaml holds a list of schedules per utility, each with
      eligibility, demand charge, dates, tariff number and source. National
      Grid has three: G-1 (no demand charge), G-2 ($15.24 per kW-month,
      billed on the all hours peak) and G-3 ($10.61, billed on the peak in
      the weekday 8 a.m. to 9 p.m. window, nine holidays excluded). G-1
      versus G-2 is the 10,000 kWh a month line, G-2 versus G-3 is 200 kW.
      The optional G-3 transmission coincident peak charge ($21.91 per kW)
      is recorded and not modeled. Demand is modeled in kW only; the
      tariff's 90 percent of kVA rule is a placeholder note.
- [x] `feat(priors): add config loader with sourced and placeholder status`
      Loader, schema checks and a CLI that lists placeholders. Every
      mapping in config/*.yaml with a status (or a prefixed one such as
      address_status) must be sourced with a source, or a placeholder with
      a note, a test and a replace (added with the assumptions page).
      `prospect priors --list-placeholders` runs the checks and lists each
      placeholder with its value and note.
- [x] `docs(method): generate assumptions page`
      docs/ASSUMPTIONS.md, generated by `make assumptions` from config
      status and notes. For each assumption: what it is, why, how it gets
      tested, and what would replace it. Covers data rules (touch
      tolerance, the 905 and 03x/04x classes, the area checks and
      fallbacks, the food keyword size gate, owner name cutoffs) and the
      battery and cost inputs. Parcels under the retired 905 code are not
      candidates, so a hospital that still sits under 905 is not ranked:
      a known limitation, not tested. Every placeholder in
      config carries note, test and replace fields, and the loader fails
      without them. The owner name cutoff width moved from code into
      config/sites.yaml (same value, 1 character) so the page covers it.
      A test fails when the page is stale.
- [x] `feat(config): add remaining utility demand rates with sources`
      Eversource (2 pilot towns) and the six municipal light plants, from
      filed tariffs. Anything not read from a tariff stays a placeholder.
      Eversource: Greater Boston G-1 (up to 100 kW, no demand charge by
      default), G-2 (over 100 kW, $33.95 per kW-month: $20.21
      distribution plus $13.74 transmission) and G-3 (primary voltage,
      $30.05), with off-peak demand discounted 55 and 70 percent and a
      seasonal peak window. Which service area serves Canton and Sharon is
      a placeholder (Greater Boston assumed). West Boylston: Large
      Commercial $8.66 per kW-month above 6,000 kWh a month. Holden,
      Sterling, Paxton, Princeton and Boylston: no schedule found online,
      so their demand charge is a placeholder with no value.
- [x] `feat(config): add battery block specification`
      config/battery.yaml for the standard deployment, one battery block:
      250 kW, 522 kWh and 97.5 percent PCS efficiency, status sourced, from
      the manufacturer's product page
      (https://www.powertownusa.com/product), read 2026-10-19. The page
      lists "typical deployment: two cabinets in parallel" with weight and
      dimensions per cabinet, and does not say whether 250 kW and 522 kWh
      are per cabinet or for the pair. We treat them as totals for the
      pair, marked as an assumption. Usable depth of discharge 90 percent
      stays a placeholder: the page does not state it. That gives about
      470 usable kWh, a little under 1.9 hours at full power before
      conversion losses. In config, `source:` lines say
      "manufacturer product page, see docs/METHOD.md", since the Powertown
      name appears only in docs. The page renders with JavaScript, so an
      automated recheck on 2026-10-20 could not read it; the values are
      as read by the owner on 2026-10-19.
      Superseded: the cost assumptions and minimum host benefit tasks below
      were removed in Phase 6 (`refactor(model): remove cost and profit
      layer`); cost and profit are no longer modeled.
- [x] `feat(config): add cost assumptions`
      Each with status and source. Installed cost $180,000 (low case) and
      $260,000 (middle case): both the owner's own estimates, unverified,
      pending Powertown's real number. Life 10 years: sourced, the stated
      warranty on the manufacturer's product page, with the page's 15 to 20
      year claim as a sensitivity case, not an input. Financing 8 percent:
      placeholder. O&M $4,000 a year: unverified estimate. The 30 percent
      ITC is a scenario setting, default off, with a note that FEOC
      sourcing rules decide eligibility. The page's claims of "1 to 3
      months off your bill" and recovering costs "by year two or three"
      are not inputs. In config/costs.yaml; the ITC rate is a placeholder
      too, since it was not read from IRS guidance. Since Phase 4 ranks by
      value per block, the installed cost cases are not model inputs: they
      are reference points next to the break-even column and an example
      cost for the optional model confidence.
- [x] `feat(config): add minimum host benefit`
      The minimum yearly benefit a host must get for the deal to be worth
      offering, in dollars a year, added to the annualized cost in the
      optional Phase 4 model confidence. A placeholder with status and a
      note until Powertown gives a real figure. In config/costs.yaml with
      no value; it is not used in scoring, only when a user supplies one.
- [x] `feat(ingest): download ComStock profiles for Massachusetts`
      A loader in `prospect/ingest/` that fetches 15-minute ComStock
      profiles for each building type in Massachusetts and saves them
      under `data/`, with an `ingest_runs` row for provenance. This is the
      only step in this work that uses the network. `make comstock` reads
      the 14 county metadata files of ComStock 2025 release 3 and takes a
      sample, not all 2,285 buildings: per building type, one building
      from each of 30 equal floor area groups, seed 20261020 (429
      buildings, 803 MB, 9 hospitals). It checks the first profile for
      15-minute steps before fetching the rest. Adds pyarrow and numpy,
      pinned.
- [x] `feat(priors): simulate the battery block on ComStock profiles`
      Read the downloaded profiles from local files. Simulate one battery
      block within its power and energy limits, and record the
      distribution of monthly peak reduction as a share of peak, per
      building type, twice: for the peak over all hours (G-2) and for the
      peak in the G-3 peak window only. Also record peak-to-average ratio
      and load factor per building type. Write them to config with source
      notes, labeled as simulated. `make simulate` writes
      config/simulation.yaml: per ComStock type and four bins of annual
      peak (under 200, 200 to 500, 500 to 1,000, 1,000 kW and up), p10,
      median, p90 and building count; cells under 10 buildings fall back
      to all types pooled, flagged. The dispatch rule (perfect foresight,
      each month starting empty) is in docs/METHOD.md, so results are an
      upper bound. config/profiles.yaml maps segments and generic use
      codes to types, gives factories, laundries, food plants, cold
      storage and auto repair (332) the widest simulated range ("no open
      profile, unvalidated"), and holds the realization factor
      (placeholder, no value yet). Eversource sites use the all-hours
      reduction, flagged.
- [x] `docs(method): tabulate simulated peak reduction by building size`
      A short table in docs/METHOD.md: median monthly peak reduction share
      against building peak size, by building type, with load factor,
      labeled simulated. No dollar ranking by segment, since factories,
      laundries, food plants and auto repair have no open profile. Say
      what the table shows about the spiky building hypothesis, which
      never goes into config.
- [x] `feat(config): add ConnectedSolutions assumptions`
      $200 per kW-season (vendor source), a performance factor
      (placeholder), and an overlap factor (placeholder) for event days
      that fall on the building's own peak, so grid revenue is not double
      counted with peak shaving. In config/connected_solutions.yaml: $200
      stays an unverified placeholder; the utility documents that agree
      are dated 2021 and 2022 and the live page could not be read. Both
      factors have no value yet. Eligible utilities are National Grid
      and Eversource; municipal light plant customers are not eligible.
      In Phase 4 the rate, event terms and eligibility became sourced from
      the National Grid Daily Dispatch page and the Mass Save offering
      materials (6/08/2023); both factors got placeholder values.
- [x] `feat(priors): derive energy intensity priors from LBER`
      kWh per sq ft by segment, for buildings without reported use. Only
      buildings with measured grid electricity count. `make intensity`
      writes config/intensity.yaml: per segment, the measured count, p10,
      median and p90 on our area and on LBER floor area, and the prior to
      use. Segments under 30 are flagged. Hospital uses the median of its
      13 measured pilot buildings (20.96 kWh per sq ft, a placeholder; the
      statewide Healthcare rows, 9.83, mix in clinics), changed in Phase 4;
      other_healthcare uses LBER's statewide Healthcare rows; food
      production, cold storage
      and laundry borrow the manufacturing spread ("proxy, likely
      understates"). The implausible low tail (p10 under 1 kWh per sq ft)
      is flagged, not floored; it does not shrink on LBER's floor area, so
      it is not an area error. The funnel uses each prior's median. LBER
      covers buildings of about 20,000 sq ft and up, so the priors may not
      apply to smaller buildings.
- [x] `feat(priors): count candidate sites through the funnel`
      `make funnel` rebuilds `site_funnel` (one row per candidate site)
      and writes docs/FUNNEL.md: sites surviving each filter by region
      and segment, in order: (1) a ConnectedSolutions utility (National
      Grid, Eversource; municipal plant sites dropped, flagged), (2) over
      10,000 kWh a month, from LBER measured kWh where available,
      otherwise the segment's median intensity, with the count of sites
      with no usable estimate, (3) estimated peak of at least 200 kW,
      from average kW and the simulated load factor (pooled median,
      flagged, where there is no open profile), with counts at 150, 200
      and 250 kW. Thresholds are placeholders in config/funnel.yaml.
      Dropped sites stay, flagged with the filter, never deleted. Tier 1
      has at least one building with LBER measured electricity, tier 2 is
      estimated and flagged. Spikiness is a Phase 4 score, not a filter.
      Survivors still carry unvalidated peak shape.
- [x] `docs(method): document priors and how to recalibrate`
      docs/METHOD.md section on priors, battery and cost assumptions,
      including what to rerun after each October 31 LBER release. Record
      the manufacturer product page URL
      (https://www.powertownusa.com/product) and its read date,
      2026-10-19, which the config `source:` lines point to.

---

## Phase 4: Economics model  (branch `phase-4-model`, tag v0.4.0)

Goal: for each site, the yearly value one battery block could bring
(demand savings plus ConnectedSolutions revenue, gross, before any host
share), with a P10 to P90 band, under each scenario. Sites are ranked by
value per block. Installed cost is not modeled; the operator applies its
own. Values are simulated and unvalidated, not profit.
Done when: `make score` writes a scored row per site and scenario with value
per block (P10, P50, P90), blocks, total, value by stream and top drivers,
and model tests pass.

Removed in Phase 6 (`refactor(model): remove cost and profit layer`): the
break-even cost, model confidence and payback check tasks below were built
here and later removed; their boxes stay ticked as a record.

Scoring scope: funnel survivors at the loosest reported peak line (150 kW),
with a flag for those that pass 200 kW. Tier 1 and tier 2 are both scored;
sites with no open profile are marked least certain. Sites the funnel
dropped stay in the database and are not scored, and municipal plant sites
are not scored.

Multiple blocks: revenue scales per block. The block count cap stays a
config placeholder.

- [x] `docs(method): research other revenue streams`
      For each of the G-3 optional coincident peak transmission charge
      ($21.91 per kW, recorded as unmodeled), ISO-NE capacity payments,
      Massachusetts clean peak credits, and the ITC and depreciation, read
      the primary source and write docs/REVENUE_STREAMS.md: what it pays,
      eligibility for a behind-the-meter battery of our size, the per-kW
      value with date and source, and what a model would need. A stream is
      modeled only if a sourced per-kW value and an eligibility rule can be
      read; otherwise it is recorded as unmodeled with what is missing. No
      unread number goes into config.
- [x] `feat(model): estimate peak demand from annual energy and load factor`
      Monte Carlo draws per building, seeded per building id so results
      never depend on row order. Tests: determinism, known kWh narrows the
      range.
- [x] `feat(model): widen or narrow uncertainty from evidence flags`
      Each evidence flag from Phase 2 sets how wide the draws are: measured
      electricity narrows them, an estimated area, a weak LBER match or
      an unknown utility widens them. Widths live in config as
      placeholders, except area: all area sources stay, every source other
      than assessor is flagged as estimated, and its width is the measured
      error from docs/DATA.md ("Footprint area error"), stored in config
      as a measured value. That error was measured only on parcels that
      have BLD_AREA, so the real error on parcels missing it may be larger.
      No pilot site has an unknown utility, so that flag widens nothing; a
      site with one would not be scored.
- [x] `feat(model): size whole battery blocks and compute demand savings`
      Block from config/battery.yaml, count cap from config (placeholder).
      Revenue scales per block and installed cost is per block, with no
      volume discount.
      Rate schedule per building from config/rates.yaml: G-1 versus G-2
      from the estimated monthly kWh, G-2 versus G-3 from the estimated
      peak. Buildings with an estimated peak of about 150 to 250 kW are
      weighted across G-2 and G-3 (band as a placeholder). G-2 savings use
      the all hours reduction and G-3 savings the peak window reduction.
      Peak shaving respects both the power limit and the energy limit, so
      long spikes are only partly shaved, using the Phase 3 simulation
      (its tests cover a flat load and long spikes). One block per 1,000 kW
      of estimated peak, at least one (placeholder); the share comes from
      the size bin of the peak per block, times the realization factor,
      and the kW cut per block is capped at the block's 250 kW. Sites with
      no open profile draw the share uniformly from the widest range in
      their size bin. A site whose cut reaches 250 kW in most draws is
      flagged capped. Eversource
      sites use G-2 with the all-hours reduction, flagged. Tests: G-1
      sites get nothing, higher rate never lowers savings, savings scale
      with the realization factor, the cut never exceeds block power.
- [x] `feat(model): add grid program revenue`
      ConnectedSolutions only where the utility is eligible, scaled by the
      performance factor and discounted by the overlap factor. The kW
      counted per block is the lesser of the block's power and 1.5 times
      the estimated site peak (the program's export cap, sourced), shared
      over the site's blocks. Tests: municipal sites get none, a 100 kW
      peak site counts at most 150 kW, a site at 167 kW or more is
      uncapped.
- [x] `feat(model): compute value per block`
      Per site and scenario: value per block per year (demand savings plus
      ConnectedSolutions revenue, gross, before any host share) at P10,
      P50 and P90, the expected number of blocks, and the total (value per
      block times blocks). Sites are ranked by P50 value per block, ties
      broken by expected blocks, then P50 total. Eversource sites in Canton
      and Sharon are flagged rate area unconfirmed.
- [x] `feat(model): compute break-even installed cost`
      Per site and scenario, the highest installed cost per block at which
      P50 value per block equals the annualized cost (life, financing and
      O&M from config), and the same at P10, with and without the ITC. It
      leaves out the host benefit and says so. A translation column, since
      installed cost is the least known input. Tests: break-even is higher
      for higher value, and a site with zero value has break-even zero.
- [x] `feat(model): compute model confidence for a given cost`
      Optional: only when a user supplies an installed cost and a minimum
      host benefit (`prospect score --installed-cost X --min-host-benefit
      Y`); `make score` does not compute it. Model confidence is the
      probability that value per block exceeds the annualized battery cost
      (installed cost over life at the financing rate, plus O&M, less the
      ITC when it is on) plus the minimum yearly host benefit. Tests:
      higher cost or a higher minimum host benefit never raises model
      confidence.
- [x] `feat(model): run scenarios`
      Two per site: demand savings only, and demand savings plus
      ConnectedSolutions. The ITC is a cost-side toggle, used only in the
      break-even column and the confidence option. Every score names its
      scenario.
- [x] `feat(model): report value by revenue stream`
      Per site and scenario, keep demand savings, ConnectedSolutions
      revenue and any modeled optional stream separate, and show each
      stream's share of P50 value.
- [x] `feat(model): attribute results to input drivers`
      Rank correlation between each input and the result.
- [x] `feat(model): persist scores with run metadata`
      `site_scores` table with run id, scenario, config hash and timestamp.
      Keep demand savings and grid revenue draws separate, in physical
      units (kW-months of peak reduction and eligible grid-program kW), so
      the report can recompute value when settings change. `make score`
      adds a run to `score_runs` (config hash, draws, time) and one
      `site_scores` row per site and scenario (migration 0017), and writes
      docs/SCORES.md. `prospect score --installed-cost X
      --min-host-benefit Y [--itc]` reprices the latest run's stored draws
      into model confidence. `make db-check` flags scores for sites no
      longer in scope.
- [x] `docs(method): check the payback claim`
      Powertown says it recovers costs in 2 to 3 years. Across the scored
      sites, report the median P50 yearly value and the installed cost per
      block implied by a 2 and a 3 year simple payback at that value. This
      is a consistency check on the owner's cost estimates, not evidence
      for or against the claim. The figures are generated in
      docs/SCORES.md; docs/METHOD.md explains the check.

---

## Phase 5: Validation  (branch `phase-5-validation`, tag v0.5.0)

Goal: validate what can be validated (annual energy estimates, building
matching, rank stability, data assumptions) and say plainly what cannot
(peak shape, ConnectedSolutions delivery). The headline stays value per
block; this phase gives no accuracy number for it. Revenue values are
simulated, gross, before the host split, and unvalidated.
Done when: `make validate` writes docs/VALIDATION.md, which states where the
model beats a size-only ranking and where it does not, whether the annual
energy bands are calibrated, how stable the rankings are, whether peak shape
was validated, and what is unvalidated.

- [x] `docs(config): record the Eversource rate source and division`
      Find which Eversource document and rate division the $33.95 G-2
      demand charge in config/rates.yaml came from, which towns that
      division covers, and whether Canton and Sharon are in it, from
      Eversource's own documents. If the source or division is wrong, or a
      different rate applies, stop and show the owner first. Otherwise
      record the source and division in the config note, and keep the
      rate area unconfirmed flag unless Eversource's documents confirm the
      towns. Result: source and division confirmed (rate 15, Greater
      Boston, M.D.P.U. No. 1-26-F); no Eversource document lists towns by
      area, so the flag stays.
- [x] `feat(model): cap ConnectedSolutions by event-window load`
      The payment cannot exceed the building's load during the 3 to 8 pm
      summer weekday event window unless the site exports, which needs an
      interconnection agreement, and then the 150 percent cap applies.
      Estimate the window load per building type from the ComStock
      profiles (window mean over annual peak), with a placeholder ratio
      for types with no open profile. For G-3 sites the 150 percent cap
      uses the 3 to 8 pm peak, not the annual peak. Rerun make score and
      report the value per block distribution before and after, the change
      in ConnectedSolutions share of P50 value, and how many sites move
      more than 10 places. `make simulate` adds per type the summer weekday
      3 to 8 pm mean and the all-year weekday 3 to 8 pm peak, each over the
      annual peak. Whether sites export is a placeholder (default no):
      without export the counted kW per block is the lesser of the block's
      average event output and the window mean load per block; with export
      the 150 percent cap applies. Types with no open profile take the
      pooled medians (placeholder). The report's sensitivity table now
      rescores instead of repricing, since the cap is not linear.
- [x] `feat(validate): reproduce size-only baseline`
      Rank by building area, as the earlier public prototype
      (github.com/thutch17/powertown-hackathon) did, credited as prior
      work. Report how much the model's top 50 per region overlaps with
      the size-only top 50. The prototype also used town permit history,
      but only for Boston, Cambridge and Somerville, so in the pilot it
      ranks by size alone. `make validate` writes the section, against all
      candidate sites and against scored sites only, with why the size
      top 50 sites that were not scored dropped out.
- [x] `feat(validate): compare energy estimates against LBER with town holdout`
      For LBER buildings with measured grid electricity (zero or negative
      is missing), estimate annual kWh as if unmeasured, with the Phase 3
      priors recomputed leaving out the held-out town. Spearman and median
      absolute percent error, model versus a size-only estimate (area
      times one global kWh per sq ft), by segment, for the pilot towns and
      statewide, with sample sizes. LBER covers only buildings of about
      20,000 sq ft and up, so this says nothing about smaller buildings.
      Statewide rows have no segment or area of ours, so the statewide line
      tests the same method on LBER property types and floor areas. Within
      a segment both estimates rank alike (area times a constant), so the
      model can only rank better across segments.
- [x] `feat(validate): check calibration of the annual energy estimate`
      This tests the annual energy estimate only, not peak shape. Hold out
      LBER buildings with measured electricity, estimate them as if
      unmeasured, and check how often the stated 80 percent band (P10 to
      P90) contains the measured value, by segment, with sample sizes. If
      the hit rate is far from 80 percent, recalibrate the band widths,
      store them in config as measured values sourced from
      docs/VALIDATION.md, rerun make score, and report the hit rates and
      ranking moves before and after. Result: 79 percent of 700 pilot
      buildings, within the 5 point tolerance (placeholder,
      config/validate.yaml), so the widths are not recalibrated and the
      scores do not move. Groups under 30 buildings are too few to judge.
- [x] `feat(validate): measure rank stability`
      From the stored draws, the probability that each scored site is in
      the top 15 and top 50 of its region by value per block. Report how
      many sites have a probability above 50 percent, and say plainly
      where the ranking is a tier and not an order. No new draws. Draw i
      of every site in a region is one joint outcome; sites vary
      independently, since each site's draws are seeded on their own.
- [x] `docs(validate): find an open interval meter dataset for peak shape`
      One pass. Candidate: Building Data Genome 2. Check its license,
      number of buildings, building types, climate and location, and
      whether readings are hourly or 15-minute (hourly cannot test
      15-minute demand peaks, only roughly the shape). Stop before any
      download and show the owner. If usable, download with a loader in
      `prospect/ingest/` and compare peak-to-average ratio, load factor
      and monthly peak reduction share with the ComStock-based estimates
      by building type. If not, record that peak shape is unvalidated.
      Building Data Genome 2 was assessed and not used (hourly,
      campus-heavy, no New England site, CC BY-SA 4.0), as recorded in
      docs/VALIDATION.md. The EnerNOC open dataset (100 sites, 2012,
      5-minute, CC BY-NC 3.0) is downloaded by `make enernoc` into data/
      only, never committed or redistributed, and used only as an
      out-of-sample test: no config value is derived or tuned from it. Its
      readings are skewed by an unknown linear factor per site, so only
      unit-free measures are compared (peak-to-average ratio, monthly load
      factor, summer 3 to 8 pm mean over peak), at 15 minutes: light
      industrial against the no-profile range, grocers and schools against
      ComStock. The block's peak reduction share by size bin depends on
      real kW and cannot be tested directly. As the owner asked, it is
      tested on shape given an assumed peak: each light industrial and
      grocery profile is scaled to each bin's midpoint (100, 350, 750 kW;
      for 1,000 kW and up, the median peak of the ComStock sample buildings
      there) and run through the same dispatch, against the no-profile
      range and ComStock Grocery. It has no warehouses.
- [x] `feat(validate): stress-test peak shape`
      Peak shape is unvalidated, so rescore with the simulated peak
      reduction share cut by 30 percent for all sites and by 50 percent for
      sites with no open profile (owner's stress values, placeholders in
      config/validate.yaml), and report top-15 and top-50 survival per
      region, the change in value per block, and which sites drop out.
      VALIDATION.md states that peak shape is unvalidated and was only
      stress-tested.
- [x] `feat(validate): run data assumption sensitivity`
      In a separate throwaway database, rerun the pipeline twice: touch
      tolerance 5 m instead of 1 m, and the 03x and 04x classes removed.
      Report how the top 50 per region move (overlap and rank changes)
      and how many scored sites change. The real tables are never changed.
      `make sensitivity` copies the database to a throwaway one per case
      (CREATE DATABASE ... TEMPLATE), overrides the assumption in memory,
      recomputes priors and funnel in memory, and writes
      data/validate/sensitivity.json, which `make validate` reads.
- [x] `docs(validate): generate validation report`
      `make validate` writes docs/VALIDATION.md: where the model beats
      size-only and where it does not, the energy comparison,
      calibration, rank stability, the peak shape result, the sensitivity
      results, sample sizes, a list of what is unvalidated (peak shape,
      ConnectedSolutions delivery, installed cost not in the model, the
      unconfirmed Eversource rate area, no open profile for factories),
      and a plain statement of limits. Everything simulated is labeled
      simulated. A generated summary leads the page; the sensitivity
      section reads the results of `make sensitivity`.

---

## Phase 6: Export and report  (branch `phase-6-export-report`, tag v0.7.0)

Export and report were planned as two phases (6 and 7) and are built as one;
there is no v0.6.0.

Goal: static files the report can load with no backend, and one
self-contained report.html that someone opens by double click, with no
network, backend or install, to see which buildings to approach next,
ranked by value per block.
Done when: `make export` writes per-region files under 5 MB each that pass
schema validation, `make report` writes report.html from the export, it
opens offline, and it lets a reader change the key assumptions and filter the
list.

- [x] `docs(plan): merge export and report phases`
      Merge the Export and Report phases into this one phase, keeping every
      task text from both.
- [x] `refactor(model): remove cost and profit layer`
      Cost and profit are no longer modeled. Remove break-even cost, model
      confidence, the minimum host benefit, the payback check, the owner's
      installed cost figures, the ITC setting, life, financing and O&M from
      code, config, docs and the export, with a new migration that drops
      the break-even columns from site_scores. No site's rank or P50 value
      per block may change. Installed cost stays only as an open question.
      Done: prospect/model/cost.py, the score flags and their tests are
      gone, config/costs.yaml is deleted, migration 0020 drops the columns,
      and the export, manifest, scores and validation pages carry no cost.
      Rescored: all 708 site and scenario rows keep their rank and every
      value (P10, P50, P90, blocks, total, both streams).
- [x] `feat(export): write ranked sites per region as GeoJSON and CSV`
      Value per block first: P50 with the P10 to P90 band, expected
      blocks, total, the value split by revenue stream, and the evidence
      flags,
      for both scenarios (demand savings only, and with
      ConnectedSolutions). The flags include capped, rate area
      unconfirmed and no open profile.
      `make export` writes export/<region>.geojson (one feature per scored
      site at its centroid, both scenarios, its parcels and buildings, the
      model rank and the size-only rank among all candidate sites) and
      export/<region>.csv (one row per site and scenario). It refuses to
      run if config/ changed since the latest score run.
- [x] `feat(export): include compact draws per site`
      A small fixed number of draws per site, split into demand savings
      and grid revenue in physical units (kW-months of peak reduction and
      eligible grid-program kW). The manifest carries the config values the
      report needs: demand rates, the realization factor and the
      ConnectedSolutions factors and caps. Built: all 1,000 stored draws per site, which fit
      the budget (Worcester 4.52 MB, Metro South 3.51 MB), so the report
      reproduces the stored P50s exactly: kW-months under G-2 and G-3,
      whole blocks, the drawn site peak and whether the draw is on G-3
      (both stored by make score since migration 0019), plus each site's
      event-window ratios, so the report can recompute the event-window
      and export caps. export/manifest.json also carries the block,
      realization factor, ConnectedSolutions terms and the placeholder
      list.
- [x] `test(export): validate export schema and size budget`
      Includes a parity test: value per block, expected blocks and stream
      shares recomputed from the export match the Python model at default
      settings, with ConnectedSolutions on or off, and with a changed
      demand rate. prospect/export/recompute.py recomputes them from the
      export alone, with the event-window and export caps, as the report
      does; the report's JavaScript mirrors it. Tests: the committed files
      pass the schema and are at most 5 MB each; their draws reproduce
      every exported P50 within $10 (the rounding of draws to 0.1); a
      model-scored site passed through the export matches the model draw
      by draw, with and without export.
- [x] `chore(export): add data manifest`
      Version, generated time, config hash, source reporting years.
      export/manifest.json opens with the version (git describe, or the
      package version outside git), the generation time, the config hash
      and the score run, and the sources: LBER reporting years, the
      ComStock release and weather year, each public source's ingest date
      and each utility's rates read date. EnerNOC is not listed, since the
      tool does not incorporate it.
- [x] `feat(report): build single-file report from the export`
      A script under `prospect/report/` writes one HTML file with data, CSS
      and JS inline and no external scripts, fonts or images. A region
      switch (Metro South, Worcester) and a sortable ranked table: owner,
      address, town, segment, value per block (P50, with the P10 to P90
      range) and its percentile rank inside the region, expected blocks,
      total, the share of value from each revenue stream, data quality as
      text from the evidence flags, and the size-only rank next to the
      model rank. No profit colors. Both scenarios show side by side. The
      report says ConnectedSolutions pays every eligible site the same per
      block unless the building's 3 to 8 pm load or the export cap limits
      it, and counts the sites where it does. The report computes the
      ConnectedSolutions share of P50 value from the export and states it,
      never hardcoded (docs/SCORES.md currently shows 56 percent). It shows
      the flags capped, rate area unconfirmed and no open profile in plain
      words.
      Basic responsive CSS. Built: `make report` writes report.html (about
      8 MB, all 1,000 draws embedded; it loads in about a third of a
      second and re-sorts in under a tenth). report.html is gitignored and
      never committed; the owner attaches it to each GitHub release from
      v0.7.0. prospect/report/compute.js mirrors
      prospect/export/recompute.py and is inlined with the UI script.
- [x] `feat(report): add site detail view`
      Evidence flags, top drivers, the buildings and parcels in the site,
      and a map link by coordinates for outreach (an external link,
      nothing embedded). Clicking a row (or Enter on it) opens the panel;
      drivers are in plain words, and the link opens OpenStreetMap at the
      site's centroid only when clicked.
- [x] `feat(report): add settings and filters`
      Settings the reader can change, recomputed in the browser from the
      export: ConnectedSolutions on or off, demand rate. A column showing
      how far each site moved from the defaults. Filters: segment,
      utility, minimum value per block, hide existing customers. Built:
      a G-2 and G-3 rate input per utility, prefilled from the manifest,
      a reset to model defaults, and a Moved column (up or down from the
      default rank). Results are cached per region and settings; a
      recompute takes under a tenth of a second. Hide existing customers
      arrives with the customer status task.
- [x] `feat(report): load a customer status file`
      An optional CSV the reader picks in the browser: owner or address,
      and a status (customer, contacted, declined). Matching sites get a
      status tag and are hidden by default. The file is read locally,
      never uploaded, and never committed. Document how rows are matched
      (normalized owner or address). Add docs/customer_status.example.csv
      with obviously fake rows. Built: columns owner, address, town
      (optional) and status; owners are normalized as sites are grouped
      (punctuation removed, company words dropped) and addresses with the
      LBER street abbreviations, both carried in the manifest; a given
      town must match. A "Hide sites in the status file" filter is on by
      default. The page and README.md describe the matching;
      customer_status*.csv is gitignored.
- [x] `feat(report): add assumptions and limits section`
      Lists every placeholder in use. Explains value per block: simulated,
      gross revenue before any host share, not profit. Says installed cost
      and the host share are not modeled, and the reader applies their
      own. Says peak shape is unvalidated until real meter data tests it.
      Lists what the ranking does not model: space for cabinets, utility
      interconnection capacity, owner willingness. Also states, with each
      figure read at build time from docs/VALIDATION.md (the build fails if
      one is missing) or computed from the export: the ConnectedSolutions
      share of P50 value; peak shape only stress-tested, with top-15
      survival; Worcester's top a tier, not an order; how many of Metro
      South's top 10 are Eversource Canton and Sharon sites with the rate
      area unconfirmed; the number of sites with no open profile; the
      modest gain over size-only (Spearman, and where it is no closer);
      the energy band hit rate; EnerNOC used only as a local out-of-sample
      test; and factories' higher 3 to 8 pm load than modeled, so their
      ConnectedSolutions revenue is probably understated.
- [ ] `test(report): check offline use and parity`
      The built file makes no network requests, and its value per block,
      expected blocks and stream shares match the Python model at default
      settings, with ConnectedSolutions on or off, and with a changed
      demand rate.

---

## Phase 8: Docs and demo  (branch `phase-8-docs`, tag v1.0.0)

Goal: someone at Powertown reads the brief in 2 minutes, opens the report,
and can audit the method in 15.
Done when: the README follows that structure and every link works on a phone.

- [ ] `docs: write one-page brief for Powertown`
      docs/BRIEF.md: what the tool does, the headline finding (value per
      block), one worked
      example (Brockton Hospital: its evidence flags and why it ranks where
      it does), what is unvalidated, and the open questions. It can be
      drafted and sent once Phase 5 gives a validation result. Check that
      Brockton Hospital is scored before using it as the worked example;
      if it is not, stop and ask the owner.
- [ ] `docs: write layered README`
      Top: problem sentence, what it does, a screenshot, and a "Start
      here" path to the brief and report.html. Middle: 2 minute
      walkthrough link. Bottom: method, validation, limits, how to run.
      The headline is value per block. State that values are gross before
      any host share and not profit, that cost is not modeled, and that
      shape estimates are unvalidated until real meter data tests them. List open questions for Powertown:
      how they find sites today, a list of current and contacted sites,
      installed cost, ITC eligibility, whether ConnectedSolutions stacks
      with peak shaving, the savings split, and how their own meter data
      could replace the type-based shape estimates, and a Canton or
      Sharon commercial bill, or Eversource's list of towns by rate
      division, to settle which rate area serves the two Eversource towns.
      Also list two product page claims to check, which are not inputs:
      "1 to 3 months off your bill" and recovering costs "by year two or
      three".
- [ ] `docs: add method, data and limits pages`
- [ ] `docs: add guide for plugging in operator data`
      docs/POWERTOWN_DATA.md: where real block size, cost, tariffs, meter
      data and outcome labels would go.
- [ ] `docs: add screenshots`
- [ ] `docs: credit prior work`

---

## Later (not in v1)

- Refresh with the LBER release due October 31 each year.
- Boston BERDO as a second validation set. Its `Tax Parcel ID` joins to the
  parcels' `PROP_ID` padded to 10 digits. The newest years are XLSX only,
  so loading them needs openpyxl. See docs/DATA.md.
- Utility hosting capacity layers as a grid feasibility signal.
- Statewide coverage beyond the pilot regions.
- An outcomes table (contacted, qualified, signed, rejected with reason) so
  ranking quality can be measured with precision at k.
- Learn building load shape from Powertown's real meter data where they
  share it, replacing the type-based priors.
- Split value between host and operator, moved from Phase 4: host share
  as a parameter that changes only the site detail numbers (host share and
  operator share), never the ranking, with a host share slider in the
  report.
- Phase 4, if area uncertainty is too wide: test floors derived from
  building height, and the Overture buildings probe for multi-story types.
- Key `raw_parcels`, `raw_footprints` and `raw_utility_territories` by
  release as well as object id, as `raw_lber` is by reporting year, so a new
  MassGIS release cannot overwrite rows in place or reuse an object id.
- The building parcel overlap allocation is parked on
  `wip/building-parcel-overlap`. It needs wiring into `make sites`, its
  config value, a TRUNCATE CASCADE fix and a remeasured area error.
  Revisit only if area uncertainty is too wide.
