# ArgusTrace — project invariants

These are the rules the codebase is built around. Several were arrived at by
getting them wrong first, so the reasoning is kept alongside each one rather
than stated as bare policy. They are checked in deliberately: they used to
live only in an untracked local file, which meant a new contributor got none
of them.

## `Status` is tri-state, never a boolean

`FOUND` / `NOT_FOUND` / `ERROR`.

- `NOT_FOUND` = verified absent.
- `ERROR` = could not verify.

Never conflate them. A plugin, checker, container or HTTP failure becomes
`ERROR`, never a guessed `NOT_FOUND` and never a guessed "outdated". This
applies everywhere, not just to `Finding`s — version checks and Docker
failures follow the same "unknown on failure" rule.

The audits that found real bugs in this project nearly all found this one:
an IP lookup treating a transient empty response as "no record", a name API's
rate-limit reply parsed as "no data", a version check with an unpaginated
list reporting "unknown" as though it meant "fine".

## `Plugin` is a `typing.Protocol`, not a base class

Structural typing, no inheritance. Anything with `name`,
`supported_entities` and `async def run(entity, options) -> list[Finding]` is
a plugin.

Shared code lives in `plugins/_common.py` as **module-level functions**
(`error_finding`, `fetch_json`, `clamp_int`, the entity patterns). Do not
turn it into a base class — that would make inheritance the price of
admission, which is exactly what the Protocol avoids.

`run()` must never raise. Every failure comes back as a `Finding` with
`status=ERROR`.

## Every tool runs in a hardened container, never on the host

Go through `plugins/_docker_runner.run_hardened`. `HARDENING_FLAGS` is
deliberately **not** configurable: an environment variable able to drop
`--cap-drop=ALL` would itself be the vulnerability.

For tools that are just "fetch a JSON URL", use `_common.fetch_json`, which
runs the shared `argustrace-curl` image — don't build a new image for that.

Secrets go to a container through `--env-file`, never `-e KEY=value`: argv is
visible in `ps` to every local user for the container's lifetime.

## No scheduler, no auto-refresh, anywhere

Version checks and any future "check X" action are on-demand, triggered by a
human. This has been asked for explicitly more than once — don't reintroduce
it as a background job, a poll, or a cron.

## No API keys the user has to provision

If the only path to a source needs a key or a signup, either skip it or
surface the tradeoff and let the user decide. (Zefix for Swiss companies was
investigated and deliberately left out on these grounds.)

Toutatis is the one exception and it is opt-in: it takes an Instagram session
cookie the user supplies themselves, with the ToS risk spelled out in its
option description.

## `evidence` dict conventions

The frontend renders these specially, so match the pattern rather than
inventing a new shape:

- `headline` — a short, curated, human-written one-line summary for the
  results row. Not every plugin needs one; don't force it.
- `profile` / `related_ids` — Maigret-style extracted identity data, rendered
  with a photo and name.
- `coordinates` — `"lat,lon"`, becomes a clickable map link automatically.
- `reason` — why an `ERROR`/`NOT_FOUND` happened.

Everything else in `evidence` is still shown in the finding detail modal.
Never silently drop plugin data because the UI has no bespoke column for it.

## Pinning

Docker images are pinned by digest where possible. Locally-built images get a
`pinned_version` in `registry.py` next to the tag — bump both together;
`tests/test_registry_consistency.py` asserts the registry agrees with what
the Dockerfile actually installs.

Verify version-check methods against the real registry API before wiring
them up. Docker tags are sometimes git SHAs rather than semver, and GitHub's
tag listing paginates.

## Testing discipline

**Never trust a tool's docs — verify against the real image or API before
writing the parsing code.** This has caught a real bug essentially every time
it was done: Holehe's `--timeout` argparse bug, Maigret's CSV-vs-JSON status
gap, crt.sh's live flakiness, a `None`-in-list bug in theHarvester, a
rate-limit body that parsed as valid JSON. A quick `docker run` or `curl` is
cheap; a wrong assumption shipped into a plugin is not.

The automated suite never touches Docker or the network — `run_hardened` is
stubbed via the `fake_docker` fixture in `tests/conftest.py`. Running the
tools for real stays a manual step, and it is not optional before calling a
plugin done.

After any frontend change, do a real Playwright pass in **both** light and
dark. Mid-animation screenshots are a common false alarm — re-screenshot with
a short wait before concluding something is broken.

Use a scratch directory for throwaway verification scripts, not the repo.

## Conventions

- Conventional Commits, no `Co-Authored-By` trailer.
- Dependencies via `uv` (`pyproject.toml` + `uv.lock`, hashes verified).
- `make check` mirrors CI: ruff, pytest, and the frontend lint/build.
- Never commit or push without an explicit go-ahead in that turn — a prior
  approval does not carry forward to the next round of changes.
