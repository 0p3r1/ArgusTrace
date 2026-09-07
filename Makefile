# Mirrors .github/workflows/ci.yml so a green `make check` locally means a
# green CI run. Nothing here needs Docker: the whole Python suite stubs
# `run_hardened`, so the tools themselves are never pulled or executed.
# Actually running a plugin against a real target stays a manual step.

.PHONY: help test cov lint fix web check

help:
	@echo "make test   - run the Python test suite"
	@echo "make cov    - run it with a coverage report"
	@echo "make lint   - ruff (correctness + security lint)"
	@echo "make fix    - apply ruff's safe autofixes"
	@echo "make web    - lint and build the frontend"
	@echo "make check  - everything CI runs"

test:
	uv run pytest -q

# Deliberately not part of `check`, and no threshold is enforced: the number
# measures the stubbed suite only. What it cannot see — a plugin against the
# real tool — is the part CLAUDE.md insists on doing by hand, and a green
# percentage here must never be mistaken for that.
cov:
	uv run pytest -q --cov --cov-report=term-missing

lint:
	uv run ruff check .

fix:
	uv run ruff check . --fix

web:
	cd web && npm run lint && npm run build

check: lint test web
