# CLAUDE.md

Standing instructions for Claude Code in this repository. Read this and PLAN.md
at the start of every session.

## What this project is

A prospecting tool for behind-the-meter battery storage in Massachusetts. It
ranks commercial and industrial buildings by estimated demand-charge savings
from a standard battery fleet, with an uncertainty range and the reasons for
each rank, grouped by region so someone preparing for a local chamber of
commerce event knows which buildings to talk to.

It uses public data only. It is not affiliated with Powertown and does not use
Powertown's data.

## How to work

- Follow PLAN.md in order. Work on exactly one commit-sized task at a time,
  and continue task by task until the stopping point I give for the session.
- Run `make check` (lint plus tests) before every commit, starting with the
  `chore: add Python project tooling` task that creates the Makefile. Never
  commit if it fails.
- One logical change per commit. Tests belong in the same commit as the code
  they test. Tick the task's checkbox in PLAN.md in that same commit.
- Commit each task as soon as it is done and `make check` passes. Do not wait
  for my approval.
- Commit, never push. I handle all pushes.
- Ask before adding any dependency not listed under Stack.
- If you discover the plan is wrong (a field does not exist, a source changed),
  stop and tell me. Do not silently work around it.

## Commit messages

Conventional Commits, imperative mood:

    type(scope): short summary under 72 characters

    Body explaining why, wrapped at 72 characters. Mention data sources
    or decisions a reviewer would want to know.

Types: feat, fix, test, docs, refactor, perf, chore, ci.
Scopes: ingest, db, sites, priors, model, validate, export, web, config, data, method.

Never use messages like "wip", "fix stuff", "update", or "changes".

## Fixing a commit before merge

Make a fixup commit, then squash it into its target without an editor:

    git commit --fixup <sha>
    GIT_SEQUENCE_EDITOR=: git rebase -i --autosquash main

Never rewrite history on main.

## Branches

- One branch per phase: `phase-0-foundation`, `phase-1-ingestion`,
  `phase-2-sites`, and so on. The one exception is the first commit,
  `chore: initialize repository`, which goes directly on main so branch
  protection has something to protect.
- Open a pull request per phase with a summary of what changed and how it was
  verified. Merge with "Rebase and merge" so the atomic commits land on main
  in a straight line.
- Tag the end of each phase on main (v0.0.1 after Phase 0, v0.1.0 after
  Phase 1, and so on).

## Never commit

- Anything under `data/` (raw downloads, interim files, large outputs). Only
  `data/README.md` is tracked.
- Secrets, `.env`, credentials, API keys.
- Notebook outputs.
- Generated web data larger than 5 MB per file. Exported files under
  `web/public/data` are committed, since CI cannot reach the data sources to
  regenerate them, so each must stay at or under 5 MB.

## Numbers and honesty rules

- Never invent a number. Every constant that is not from a cited source lives
  in `config/` with `status: placeholder` and a note. Sourced values carry
  `status: sourced` and a `source:` line.
- The CLI and the web app must show which placeholders are in use.
- Never describe outputs as accurate unless a validation metric in
  `docs/VALIDATION.md` supports it.
- Credit the earlier public prototype (github.com/thutch17/powertown-hackathon)
  as prior work. Do not call it a hackathon entry or say how it placed.
- Do not claim anything about Powertown's customers, contracts or revenue split.
- Use the generic term "battery block" in code, config and identifiers. The
  Powertown name appears only in docs.

## Network and tests

- Network calls only inside `prospect/ingest/`. Everything else reads from the
  database or local files.
- Tests never touch the network. Use small recorded fixtures under
  `tests/fixtures/`. CI has no network access to data sources.
- Ingestion must be idempotent: running it twice must not duplicate rows.

## Stack

- Python 3.11+, packaged with pyproject.toml. Use uv if installed, otherwise
  venv and pip.
- Python libraries: httpx, tenacity, psycopg (v3), pandas, numpy, pyyaml,
  pytest, ruff.
- Postgres 16 with PostGIS, run locally with docker compose. Spatial joins
  happen in SQL, not in Python.
- Web: React, TypeScript, Vite, MapLibre GL JS, Vitest. No backend. The app
  reads precomputed static JSON so the public demo cannot go down.
- Deploy: GitHub Pages via GitHub Actions.

## Layout

    prospect/            Python package
      ingest/            source clients and loaders (only place with network)
      sites/             site table building, matching, segmentation
      priors/            calibration from public datasets
      model/             Monte Carlo economics
      validate/          baseline and metrics
      export/            static JSON and CSV export
    sql/migrations/      numbered SQL migrations
    config/              YAML config with sourced and placeholder status
    tests/               pytest tests and fixtures
    web/                 React app
    docs/                METHOD, DATA, VALIDATION, LIMITS, MATCH_RATES,
                         POWERTOWN_DATA
    data/                ignored by git

## Commands

    make db-up        start PostGIS
    make migrate      apply SQL migrations
    make ingest       load sources for REGION (default: pilot regions)
    make sites        build the site table
    make priors       derive priors from public data
    make score        run the model and store results
    make validate     write docs/VALIDATION.md
    make export       write web/public/data
    make web-dev      run the app locally
    make check        lint and test everything

## Writing style for docs and UI text

Plain words and short sentences. No em dashes. No bold. Lead with what the
reader needs, then the detail.