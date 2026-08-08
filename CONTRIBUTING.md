# Contributing to ArgusTrace

Read [CLAUDE.md](CLAUDE.md) first. It holds the invariants the codebase is
built around — the tri-state `Status`, the Protocol-not-base-class rule, the
container boundary, the `evidence` conventions — and most of them exist
because getting them wrong caused a real bug.

## Setup

```bash
uv sync --dev
cd web && npm install
```

Docker must be running for anything except `mock`, and the locally-built
images need building once (see the README's Setup section).

## The checks

```bash
make check     # exactly what CI runs: ruff, pytest, frontend lint + build
```

`make test`, `make lint` and `make web` run the pieces individually. None of
them need Docker: the suite stubs `run_hardened`, so no OSINT tool is ever
pulled or executed by a test.

That is also the limit of what they prove. **Running a plugin against a real
target is a manual step and it is not optional** — see the testing section of
CLAUDE.md for why.

## Adding a plugin

1. Write `argustrace/plugins/<tool>_plugin.py`. Anything with `name`,
   `supported_entities` and `async def run(entity, options) -> list[Finding]`
   qualifies; there is nothing to inherit from.
2. Use `plugins/_common.py`. `fetch_json` covers "fetch a JSON URL" including
   retries and shape checking, `error_finding` builds the ERROR Finding, and
   the entity patterns are already there. Anything else goes through
   `run_hardened` — never run a tool on the host.
3. Register it in `plugins/registry.py`, in both `PLUGINS` and
   `TOOL_FAMILIES`. `tests/test_registry_consistency.py` will tell you if the
   two disagree.
4. Declare options in the registry with their type, bounds and choices.
   `plugins/options.py` validates against that declaration, so plugins should
   not re-implement bounds checking as their primary defence.
5. Add tests using the `fake_docker` fixture from `tests/conftest.py`.
6. Add `docs/plugins/<tool>.md` and a row in the README's tool table.
7. **Run it against something real** before calling it done, and say what you
   observed.

## Commits

Conventional Commits. Explain *why*, and when a decision was reached by
testing against the real thing, say what the test showed — that reasoning is
the part that is expensive to reconstruct later.
