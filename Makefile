.PHONY: check lint test db-up db-down

RUN := $(shell command -v uv >/dev/null 2>&1 && echo "uv run" || echo ".venv/bin/python -m")

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
