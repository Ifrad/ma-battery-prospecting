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
estimates it from public data and ranks buildings by expected savings, with a
range and the reasons, grouped by region.

## What "better than size ranking" means, measurably

1. On buildings with reported energy use (DOER LBER statewide, BERDO in
   Boston), the model's annual kWh estimate beats a size-only estimate on
   Spearman correlation and median absolute percent error, with whole towns
   held out.
2. Every site shows a P10 to P90 range, not a single score.
3. Nonprofit hospitals are included rather than silently filtered out
   (Boston code 979; the statewide equivalent is verified in Phase 2).
4. Every ranked site has an owner name and site address for outreach.

## Verified facts this plan relies on

- MassGIS L3 parcels include owner1, site_addr, bld_area, year_built, ls_date
  and use_code, and are served as a hosted ArcGIS feature layer with a 2,000
  record page size.
- Boston's assessor code list has 305 for private taxable hospitals, 979 for
  exempt hospitals and 414 for food processing plants.
- DOER's Large Building Energy Reporting covers buildings of 20,000 sq ft or
  more statewide. Utilities report usage, DOER publishes by October 31 each
  year, and the first release (calendar 2024) is incomplete.
- BERDO covers non-residential buildings of 20,000 sq ft or more in Boston.
- NREL's End-Use Load Profiles (ComStock) publish 15-minute profiles by
  commercial building type.

Anything not on this list gets verified in Phase 1 before it is relied on.

## Pilot scope

Start with two regions tied to chambers Powertown is publicly active in:
Metro South (Brockton) and Worcester. Statewide comes after the pilot works.

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
- [ ] `ci: run lint and tests on push and pull request`
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

- [ ] `feat(ingest): add HTTP client with retries and rate limiting`
      httpx plus tenacity, exponential backoff, a polite delay between pages,
      a user agent. Tests use a mocked transport.
- [ ] `feat(db): add migration runner and provenance table`
      Numbered SQL migrations, `make migrate`, an `ingest_runs` table with
      source, url, started_at, finished_at, rows, sha256 and status.
- [ ] `feat(ingest): add schema probe for data sources`
      A command that fetches one page from each source and prints field
      names and types. No database writes.
- [ ] `docs(data): record source schemas, licenses and gaps`
      docs/DATA.md from the probe output. Note anything in "Verified facts"
      that turned out wrong and stop if a core field is missing.
- [ ] `feat(config): define pilot regions by chamber territory`
      config/regions.yaml mapping chamber name to towns, each with the URL
      the town list came from. Start with Brockton and Worcester only and
      add towns by hand from the chambers' own sites.
- [ ] `feat(ingest): load MassGIS L3 parcels for pilot regions`
      Paged feature service queries, resumable by object id, upsert into
      `raw_parcels`. Fixture-based tests for paging and idempotency.
- [ ] `feat(ingest): load building footprints and utility territories`
      Into `raw_footprints` and `raw_utility_territories`.
- [ ] `feat(ingest): load DOER large building energy data`
      Into `raw_lber`. Record the reporting year on every row, since a new
      release lands each October 31.
- [ ] `feat(ingest): load Boston BERDO data for validation`
      Into `raw_berdo`.
- [ ] `chore(ingest): add ingest summary report`
      `make ingest` prints rows per source and region and any failures.

Kickoff prompt:

    Read CLAUDE.md and PLAN.md. Start Phase 1 on branch phase-1-ingestion.
    Begin with the schema probe tasks before writing any loader, and stop
    to show me docs/DATA.md before continuing.

---

## Phase 2: Sites  (branch `phase-2-sites`, tag v0.2.0)

Goal: one clean row per candidate building with owner, address, utility,
segment and any reported energy use.
Done when: the site table exists for both pilot regions, the LBER match rate
is reported, and exempt hospitals appear.

- [ ] `feat(config): add assessor use code classes`
      config/use_codes.yaml: 300 to 499 as commercial and industrial, plus
      979 exempt hospitals, with each code's source. Mark codes not yet
      checked against the statewide list as placeholders.
- [ ] `feat(sites): build site table from parcels and footprints`
      SQL migration creating `sites` with area, year built, use code, owner,
      site address and geometry.
- [ ] `feat(sites): assign electric utility and flag municipal light plants`
      Spatial join to utility territories in SQL.
- [ ] `feat(sites): match sites to LBER and BERDO records`
      Address normalization, match confidence, and a table of unmatched rows.
- [ ] `feat(sites): assign segments from use codes and owner text`
      Cold storage, food production, laundry, hospital, manufacturing,
      warehouse, generic. Keyword rules in config with tests.
- [ ] `feat(sites): add tenure signal from last sale date`
      Years since last sale, as a rough proxy for a locally rooted business.
- [ ] `docs(data): generate match rate report`
      docs/MATCH_RATES.md with counts by region, segment and match type.

---

## Phase 3: Priors and rates  (branch `phase-3-priors`, tag v0.3.0)

Goal: every model input is either sourced from public data or visibly marked
as a placeholder.
Done when: `prospect priors --list-placeholders` prints the remaining
placeholders and each sourced value names its source.

- [ ] `feat(priors): add config loader with sourced and placeholder status`
      Loader, schema checks and a CLI that lists placeholders.
- [ ] `feat(config): add utility demand rates with sources`
      Per-utility demand charge in dollars per kW-month from filed tariffs.
      Anything not read from a tariff stays a placeholder.
- [ ] `feat(priors): derive load factor priors from ComStock profiles`
      Fetch a small subset by building type through a loader in
      `prospect/ingest/`, then compute load factor distributions from the
      local copy and write them to config with source notes.
- [ ] `feat(priors): derive energy intensity priors from LBER`
      kWh per sq ft by segment, for sites without reported use.
- [ ] `docs(method): document priors and how to recalibrate`
      docs/METHOD.md section on priors, including what to rerun after each
      October 31 LBER release.

---

## Phase 4: Economics model  (branch `phase-4-model`, tag v0.4.0)

Goal: for each site, a distribution of annual savings from whole battery
blocks.
Done when: `make score` writes a scored row per site with P10, P50, P90,
expected blocks and top drivers, and model tests pass.

- [ ] `feat(model): estimate peak demand from annual energy and load factor`
      Monte Carlo draws, seeded per site id so results never depend on row
      order. Tests: determinism, known kWh narrows the range.
- [ ] `feat(model): size whole battery blocks and compute demand savings`
      Block size and count cap from config (placeholders). Tests: flat load
      gives zero, higher rate never lowers savings.
- [ ] `feat(model): add grid program revenue as a separate scenario`
      ConnectedSolutions only where the utility is eligible. Tests: municipal
      sites get none.
- [ ] `feat(model): split savings between host and operator`
      Host share as a parameter. Outputs: total savings created, host share,
      operator share minus annualized cost.
- [ ] `feat(model): attribute results to input drivers`
      Rank correlation between each input and the result.
- [ ] `feat(model): persist scores with run metadata`
      `site_scores` table with run id, config hash and timestamp.

---

## Phase 5: Validation  (branch `phase-5-validation`, tag v0.5.0)

Goal: one honest headline number.
Done when: docs/VALIDATION.md exists, is generated by `make validate`, and
states where the model wins and where it does not.

- [ ] `feat(validate): reproduce size-only baseline`
      Rank by building area, matching the earlier prototype's behavior.
- [ ] `feat(validate): compare energy estimates against LBER with town holdout`
      Spearman and median absolute percent error, model versus baseline.
- [ ] `feat(validate): check estimates against BERDO in Boston`
- [ ] `docs(validate): generate validation report`
      Metrics, sample sizes and a plain statement of limits.

---

## Phase 6: Export  (branch `phase-6-export`, tag v0.6.0)

Goal: static files the web app can load with no backend.
Done when: `make export` writes per-region files under 5 MB each that pass
schema validation.

- [ ] `feat(export): write ranked sites per region as GeoJSON and CSV`
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
- [ ] `feat(web): add site panel with savings range and reasons`
- [ ] `feat(web): add host share slider`
- [ ] `feat(web): compare model ranking with size-only ranking`
      Toggle between the two and highlight the sites that move most.
- [ ] `feat(web): add region CSV download`
- [ ] `feat(web): make layout work on phones`
- [ ] `feat(web): add assumptions and limits page`
      Lists every placeholder in use.
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
      how to run.
- [ ] `docs: add method, data and limits pages`
- [ ] `docs: add guide for plugging in operator data`
      docs/POWERTOWN_DATA.md: where real block size, cost, tariffs, meter
      data and outcome labels would go.
- [ ] `docs: add demo GIF and screenshots`
- [ ] `docs: credit prior work and list open questions`

---

## Later (not in v1)

- Refresh with the LBER release due October 31 each year.
- Utility hosting capacity layers as a grid feasibility signal.
- Statewide coverage beyond the pilot regions.
- An outcomes table (contacted, qualified, signed, rejected with reason) so
  ranking quality can be measured with precision at k.