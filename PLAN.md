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
estimates it from public data and ranks sites by model confidence, the
probability that a standard battery pays for itself and still leaves the host
a minimum yearly benefit, with a band and the reasons, grouped by region.

## What "better than size ranking" means, measurably

1. On buildings with reported grid electricity in DOER LBER, the model's
   annual kWh estimate beats a size-only estimate on Spearman correlation
   and median absolute percent error, with whole towns held out. Measured
   statewide, with the pilot towns reported separately. Zero or negative
   grid electricity counts as missing, never as zero.
2. Every site shows its model confidence: the probability that its total
   value exceeds the annualized battery cost plus a minimum yearly benefit
   for the host, with a band and its evidence flags, not a single point
   estimate. The annual energy estimate behind it is checked for
   calibration. Peak shape is unvalidated until real interval meter data
   tests it.
3. Nonprofit hospitals are included rather than silently filtered out:
   state code 955 or 9550, Boston code 979, or an owner name containing
   HOSPITAL or MEDICAL CENTER. Vacant land (`955V`) is not a
   hospital.
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
one town. Every building and site carries evidence flags that say how much
of its data is measured and how much is estimated.
Done when: buildings and sites exist for both pilot regions with their
evidence flags, the LBER match rate is reported by method (UBID exact match
first), exempt hospitals appear, and the footprint area error is recorded
in docs/DATA.md.

Evidence flags, per building and per site:

- electricity source: measured (LBER) or estimated
- area source: assessor, footprint_x_stories or footprint_only
- LBER match method and confidence
- utility: known, municipal, or unknown (multi-provider towns)
- segment, and how it was assigned (use code or owner keyword)
- local owner: owner mailing address in the same town, P.O. boxes included
- mixed residential and C&I parcel
- tenure, ignoring nominal sales

- [x] `feat(db): keep LBER reporting years side by side`
      `raw_lber` holds one release today and is keyed on object id alone.
      Add the reporting year to its key so a new October 31 release is
      loaded next to the old one instead of replacing it.
- [ ] `feat(config): add assessor use code classes`
      config/use_codes.yaml: 300 to 499 as commercial and industrial, plus
      exempt hospitals (955 and 9550 statewide, 979 in Boston), with each
      code's source. Normalize 4 character codes such as `9550`. A fourth
      character `V` means vacant land (`955V` is "EXEMPT VACANT LAND"), so
      those codes are never a hospital, even when the owner name matches.
      Mark codes not yet checked against the statewide list as placeholders.
      Municipal sites are not covered by these classes yet. Whether to add
      a municipal class is an open decision for the owner.
- [ ] `feat(sites): build the building table from footprints and parcels`
      SQL migration creating `buildings`: one row per footprint, linked to
      the parcel it sits in, with owner, site address, use code, year built
      (optional) and geometry. Building area comes from `BLD_AREA`, never
      `RES_AREA`, otherwise footprint area times stories, otherwise
      footprint area alone, with the area source flag. Parcels with several
      records (3,391 in the pilot) follow one documented rule, and the 52
      that mix residential and C&I records are flagged. No size floor: keep
      every building and let the model decide.
- [ ] `feat(sites): group buildings into outreach sites`
      A site is the buildings on touching parcels with the same normalized
      owner, within one town, for every owner, not only hospitals.
      Normalize owner names first (punctuation, INC, CORP, CO, THE, and
      names cut off at about 30 characters), since one owner appears as
      `BROCKTON HOSPITAL`, `... INC` and `... COMPANY THE`. This also joins
      cases like 1129 Auburn St, Whitman: two touching parcels, one owner,
      one address. Scattered parcels of one owner stay separate sites.
- [ ] `feat(sites): compute UBIDs for footprints`
      Unique Building Identifiers from the MassGIS footprints, so LBER's
      `UBID` field can be matched exactly. This needs PNNL's open source
      buildingid implementation, which is not in the Stack: propose the
      dependency and wait for approval before adding it.
- [ ] `feat(sites): match buildings to LBER records`
      In order, stopping at the first that works: (1) exact UBID match,
      (2) LBER point inside a footprint, (3) point inside a parcel,
      (4) normalized address. Record the method and a confidence for every
      match, and keep a table of unmatched LBER rows. Report the UBID exact
      match rate first. Matched buildings get electricity source measured.
- [ ] `feat(sites): assign electric utility and flag municipal light plants`
      Join on TOWN_ID, no spatial join. Utility flag is known, municipal,
      or unknown for multi-provider towns. In the pilot, six towns have a
      municipal light plant: Boylston, Holden, Paxton, Princeton, Sterling
      and West Boylston.
- [ ] `feat(sites): assign segments from use codes and owner text`
      Cold storage, food production, laundry, hospital, other_healthcare,
      manufacturing, warehouse, generic. Keyword rules in config with
      tests, and a flag for how each segment was assigned. Hospital owner
      keywords: HOSPITAL, MEDICAL CENTER. HEALTH goes to other_healthcare.
- [ ] `feat(sites): add local owner and tenure signals`
      Local owner: the owner mailing address is in the same town, P.O.
      boxes included. Tenure: years since the last sale, ignoring nominal
      sales ($1, $100 and similar), as a rough proxy for a locally rooted
      business.
- [ ] `feat(sites): collect evidence flags per building and per site`
      One place to read every flag listed above, for both levels. A site's
      flags summarize its buildings (for example, how many have measured
      electricity).
- [ ] `docs(data): measure footprint area error`
      Compare footprint-based area with `BLD_AREA`, and with LBER
      `Gross_Floor_Area` for matched buildings: median and 90th percentile
      error for footprint_x_stories and footprint_only. Record it in
      docs/DATA.md, then stop and show the owner before deciding how
      estimated areas are used.
- [ ] `docs(data): generate match rate report`
      docs/MATCH_RATES.md with counts by region, segment and match method.
      Review by hand and record the results: 20 owner groups for false
      merges, about 10 sites per segment for keyword precision, and where
      LBER points land (C&I parcel, residential parcel, none).

---

## Phase 3: Priors and rates  (branch `phase-3-priors`, tag v0.3.0)

Goal: every model input is either sourced from public data or visibly marked
as a placeholder.
Done when: `prospect priors --list-placeholders` prints the remaining
placeholders and each sourced value names its source.

- [ ] `feat(config): add National Grid demand rate from its tariff`
      Read the demand charge in dollars per kW-month from National Grid's
      filed Massachusetts tariff. It serves 45 of the 53 pilot towns.
- [ ] `feat(priors): add config loader with sourced and placeholder status`
      Loader, schema checks and a CLI that lists placeholders.
- [ ] `feat(config): add remaining utility demand rates with sources`
      Eversource (2 pilot towns) and the six municipal light plants, from
      filed tariffs. Anything not read from a tariff stays a placeholder.
- [ ] `feat(config): add battery block specification`
      config/battery.yaml for the standard deployment, one battery block:
      250 kW, 522 kWh and 97.5 percent PCS efficiency, status sourced, from
      the manufacturer's product page
      (https://www.powertownusa.com/product), read 2026-10-19. The page
      lists "typical deployment: two cabinets in parallel" with weight and
      dimensions per cabinet, and does not say whether 250 kW and 522 kWh
      are per cabinet or for the pair. We treat them as totals for the
      pair, marked as an assumption. Usable depth of discharge 90 percent
      stays a placeholder: the page does not state it. That gives about
      1.8 hours at full power. In config, `source:` lines say
      "manufacturer product page, see docs/METHOD.md", since the Powertown
      name appears only in docs.
- [ ] `feat(config): add cost assumptions`
      Each with status and source. Installed cost $180,000 (low case) and
      $260,000 (middle case): both the owner's own estimates, unverified,
      pending Powertown's real number. Life 10 years: sourced, the stated
      warranty on the manufacturer's product page, with the page's 15 to 20
      year claim as a sensitivity case, not an input. Financing 8 percent:
      placeholder. O&M $4,000 a year: unverified estimate. The 30 percent
      ITC is a scenario setting, default off, with a note that FEOC
      sourcing rules decide eligibility. The page's claims of "1 to 3
      months off your bill" and recovering costs "by year two or three"
      are not inputs.
- [ ] `feat(config): add minimum host benefit`
      The minimum yearly benefit a host must get for the deal to be worth
      offering, in dollars a year, added to the annualized cost in the
      Phase 4 hurdle. A placeholder with status and a note until Powertown
      gives a real figure.
- [ ] `feat(ingest): download ComStock profiles for Massachusetts`
      A loader in `prospect/ingest/` that fetches 15-minute ComStock
      profiles for each building type in Massachusetts and saves them
      under `data/`, with an `ingest_runs` row for provenance. This is the
      only step in this work that uses the network.
- [ ] `feat(priors): simulate the battery block on ComStock profiles`
      Read the downloaded profiles from local files. Simulate one battery
      block within its power and energy limits, and record the
      distribution of monthly peak reduction as a share of peak, per
      building type. Load factor is a secondary output. Write both to
      config with source notes.
- [ ] `feat(config): add ConnectedSolutions assumptions`
      $200 per kW-season (vendor source), a performance factor
      (placeholder), and an overlap factor (placeholder) for event days
      that fall on the building's own peak, so grid revenue is not double
      counted with peak shaving.
- [ ] `feat(priors): derive energy intensity priors from LBER`
      kWh per sq ft by segment, for buildings without reported use. Only
      buildings with measured grid electricity count.
- [ ] `docs(method): document priors and how to recalibrate`
      docs/METHOD.md section on priors, battery and cost assumptions,
      including what to rerun after each October 31 LBER release. Record
      the manufacturer product page URL
      (https://www.powertownusa.com/product) and its read date,
      2026-10-19, which the config `source:` lines point to.

---

## Phase 4: Economics model  (branch `phase-4-model`, tag v0.4.0)

Goal: for each site, its model confidence that a standard battery
deployment clears the profit hurdle (annualized cost plus the minimum host
benefit), with a band, under each scenario.
Done when: `make score` writes a scored row per site and scenario with the
model confidence, P10, P50 and P90 of total value, expected
blocks and top drivers, and model tests pass.

- [ ] `feat(model): estimate peak demand from annual energy and load factor`
      Monte Carlo draws per building, seeded per building id so results
      never depend on row order. Tests: determinism, known kWh narrows the
      range.
- [ ] `feat(model): widen or narrow uncertainty from evidence flags`
      Each evidence flag from Phase 2 sets how wide the draws are: measured
      electricity narrows them, footprint_only area, a weak LBER match or
      an unknown utility widens them. Widths live in config as
      placeholders.
- [ ] `feat(model): size whole battery blocks and compute demand savings`
      Block from config/battery.yaml, count cap from config (placeholder).
      Peak shaving respects both the power limit and the energy limit, so
      long spikes are only partly shaved, using the Phase 3 simulation.
      Tests: flat load gives zero, higher rate never lowers savings, a
      longer spike never raises the shaved share.
- [ ] `feat(model): add grid program revenue`
      ConnectedSolutions only where the utility is eligible, discounted by
      the overlap factor. Tests: municipal sites get none.
- [ ] `feat(model): compute model confidence for the profit hurdle`
      Model confidence is the probability that total value (demand
      savings plus grid revenue) exceeds the annualized battery cost
      (installed cost over life at the financing rate, plus O&M) plus the
      minimum yearly host benefit from config. It does not depend on the
      host share split. Tests: higher cost or a higher minimum host
      benefit never raises model confidence.
- [ ] `feat(model): run scenarios`
      With and without ITC, and with and without ConnectedSolutions. Every
      score names its scenario.
- [ ] `feat(model): split savings between host and operator`
      Host share as a parameter. It only changes the site panel numbers
      (host share, operator share minus annualized cost), never model
      confidence.
- [ ] `feat(model): attribute results to input drivers`
      Rank correlation between each input and the result.
- [ ] `feat(model): persist scores with run metadata`
      `site_scores` table with run id, scenario, config hash and timestamp.

---

## Phase 5: Validation  (branch `phase-5-validation`, tag v0.5.0)

Goal: one honest headline number, and a clear line between what is
validated and what is not.
Done when: docs/VALIDATION.md exists, is generated by `make validate`, and
states where the model wins, where it does not, whether the annual energy
bands are calibrated, and whether peak shape was validated.

- [ ] `feat(validate): reproduce size-only baseline`
      Rank by building area, matching the earlier prototype's behavior.
- [ ] `feat(validate): compare energy estimates against LBER with town holdout`
      Spearman and median absolute percent error, model versus baseline.
      Statewide, with the pilot towns reported separately. Buildings with
      zero grid electricity are excluded as missing.
- [ ] `feat(validate): check calibration of the annual energy estimate`
      This tests the annual energy estimate only, not peak shape. Hold out
      LBER buildings with measured electricity, estimate them as if
      unmeasured, and check each band's hit rate: a band should contain
      the measured value about as often as it claims. If not, recalibrate
      before anything is shown in the app.
- [ ] `docs(validate): find an open interval meter dataset for peak shape`
      Look for an open dataset of interval meter readings to test the
      peak-shape estimates. Building Data Genome 2 is a candidate: verify
      its license and its coverage of comparable commercial buildings
      first. If one is usable, test the shape estimates against it, with
      any download done by a loader in `prospect/ingest/`. If none is
      usable, record in docs/VALIDATION.md that shape is unvalidated.
- [ ] `feat(validate): report cost sensitivity`
      How rankings change between the low ($180,000) and middle ($260,000)
      installed cost cases.
- [ ] `docs(validate): generate validation report`
      Metrics, energy calibration, the peak shape result, cost
      sensitivity, sample sizes and a plain statement of limits.

---

## Phase 6: Export  (branch `phase-6-export`, tag v0.6.0)

Goal: static files the web app can load with no backend.
Done when: `make export` writes per-region files under 5 MB each that pass
schema validation.

- [ ] `feat(export): write ranked sites per region as GeoJSON and CSV`
      Every site includes its model confidence, its band, and its
      evidence flags.
- [ ] `feat(export): include compact savings draws for the share slider`
      A small fixed number of draws per site so the browser can recompute
      host and operator shares exactly.
- [ ] `test(export): validate export schema and size budget`
- [ ] `chore(export): add data manifest`
      Version, generated time, config hash, source reporting years.

---

## Phase 7: Web app  (branch `phase-7-web`, tag v0.7.0)

Goal: a phone-friendly map someone can understand in 10 seconds.
Done when: the deployed site loads a region, shows a ranked list and map, and
works on a phone.

- [ ] `feat(web): scaffold Vite React TypeScript app with MapLibre`
      Pick a free basemap whose terms allow this use, and note it in docs.
- [ ] `feat(web): show ranked list and map for a region`
      Ranked by model confidence.
- [ ] `feat(web): color sites by model confidence`
      One scale: 90 and above green, 80 to under 90 yellow, 70 to under 80
      orange, 50 to under 70 deep orange, under 50 red. Always show the
      number and a short label next to the color, never color alone. Red
      sites are hidden by default and shown with one click, with the reason
      each is red.
- [ ] `feat(web): add site panel with savings range and reasons`
      Data quality appears as text labels from the evidence flags, not as
      a second color scale.
- [ ] `feat(web): add host share slider`
- [ ] `feat(web): compare model ranking with size-only ranking`
      Toggle between the two and highlight the sites that move most.
- [ ] `feat(web): add region CSV download`
- [ ] `feat(web): make layout work on phones`
- [ ] `feat(web): add assumptions and limits page`
      Lists every placeholder in use. Shows the installed cost assumption
      and says it is pending Powertown's confirmation. Explains model
      confidence, and states that shape estimates are unvalidated until
      real meter data tests them.
- [ ] `test(web): add component tests and build check to CI`
- [ ] `ci: deploy site to GitHub Pages`

---

## Phase 8: Docs and demo  (branch `phase-8-docs`, tag v1.0.0)

Goal: someone at Powertown understands it in 10 seconds, sees it work in 2
minutes, and can audit it in 15.
Done when: the README follows that structure and every link works on a phone.

- [ ] `docs: write layered README`
      Top: problem sentence, what it does, GIF, live link, "Start here" path.
      Middle: 2 minute walkthrough link. Bottom: method, validation, limits,
      how to run. Use the term model confidence. State the low cost
      assumption and the cost sensitivity result, and that shape estimates
      are unvalidated until real meter data tests them. List open questions
      for Powertown: how they find sites today, installed cost, ITC
      eligibility, whether ConnectedSolutions stacks with peak shaving, the
      savings split, and how their own meter data could replace the
      type-based shape estimates. Also list two product page claims to
      check, which are not used as inputs: "1 to 3 months off your bill"
      and recovering costs "by year two or three".
- [ ] `docs: add method, data and limits pages`
- [ ] `docs: add guide for plugging in operator data`
      docs/POWERTOWN_DATA.md: where real block size, cost, tariffs, meter
      data and outcome labels would go.
- [ ] `docs: add demo GIF and screenshots`
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
