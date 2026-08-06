# Mirrors .github/workflows/ci.yml so a green `make check` locally means a
# green CI run. Nothing here needs Docker: the whole Python suite stubs
# `run_hardened`, so the tools themselves are never pulled or executed.
# Actually running a plugin against a real target stays a manual step.

.PHONY: help test lint fix web check

help:
	@echo "make test   - run the Python test suite"
	@echo "make lint   - ruff (correctness + security lint)"
	@echo "make fix    - apply ruff's safe autofixes"
	@echo "make web    - lint and build the frontend"
	@echo "make check  - everything CI runs"

test:
	uv run pytest -q

lint:
	uv run ruff check .

fix:
	uv run ruff check . --fix

web:
	cd web && npm run lint && npm run build

check: lint test web
