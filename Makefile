-include .env
export

.PHONY: check lint test db-up db-down migrate probe ingest sites match-rates assumptions comstock simulate intensity funnel db-check

RUN := $(shell command -v uv >/dev/null 2>&1 && echo "uv run" || echo ".venv/bin/python -m")
PY := $(shell command -v uv >/dev/null 2>&1 && echo "uv run python" || echo ".venv/bin/python")

check: lint test

lint:
	$(RUN) ruff check .
	$(RUN) ruff format --check .

test:
	$(RUN) pytest

db-up:
	docker compose up -d --wait

# Keeps the pgdata volume. Use `docker compose down -v` to wipe it.
db-down:
	docker compose down

migrate:
	$(PY) -m prospect.migrate

probe:
	$(PY) -m prospect.ingest.probe

# REGION=metro_south limits the load to one region (default: all regions).
ingest:
	$(PY) -m prospect.ingest.run $(REGION)

# Download the ComStock profile sample into data/comstock/ (about 1 GB).
comstock:
	$(PY) -m prospect.ingest.comstock

# Simulate the battery block on the ComStock sample; writes config/simulation.yaml.
simulate:
	$(PY) -m prospect.priors.simulate

# Derive kWh per sq ft priors from LBER; writes config/intensity.yaml.
intensity:
	$(PY) -m prospect.priors.intensity

# Count candidate sites through the funnel; rerun after make sites.
funnel:
	$(PY) -m prospect.priors.funnel

# Check that derived tables agree with their sources; run after make sites
# and make funnel.
db-check:
	$(PY) -m prospect.sites.checks

# Rebuild parcels, buildings and sites from the raw tables.
sites:
	$(PY) -m prospect.sites.build

# Write docs/MATCH_RATES.md and the hand review sheets in data/review/.
match-rates:
	$(PY) -m prospect.sites.match_rates

# Write docs/ASSUMPTIONS.md from config status and notes.
assumptions:
	$(PY) -m prospect.priors.assumptions
