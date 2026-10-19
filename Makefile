-include .env
export

.PHONY: check lint test db-up db-down migrate probe ingest

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
