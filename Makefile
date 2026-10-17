.PHONY: check lint test

RUN := $(shell command -v uv >/dev/null 2>&1 && echo "uv run" || echo ".venv/bin/python -m")

check: lint test

lint:
	$(RUN) ruff check .
	$(RUN) ruff format --check .

test:
	$(RUN) pytest
