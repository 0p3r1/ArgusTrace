# ArgusTrace

![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue)
![Managed with uv](https://img.shields.io/badge/managed%20with-uv-de5fe9)
![Tests: pytest](https://img.shields.io/badge/tests-pytest-0a9edc)
![Status: skeleton](https://img.shields.io/badge/status-early--skeleton-yellow)
![License: TBD](https://img.shields.io/badge/license-TBD-lightgrey)

A modular OSINT framework. This is an early-stage skeleton proving out the
core pipeline — entity in, plugin runs, structured findings out — before any
scheduler, correlation engine, scoring, graph, or REST API gets built on top.

## Architecture

```mermaid
%%{init: {"flowchart": {"subGraphTitleMargin": {"top": 10, "bottom": 15}}}}%%
flowchart LR
    User(["You: \"check this username, email, or phone\""])
    CLI["ArgusTrace CLI"]
    Mock["Mock plugin<br/>(demo, no real check)"]
    ToolPlugin["Tool plugin<br/>(Sherlock, Holehe, Ignorant, ...)"]
    Findings["Findings:<br/>found / not found / error"]
    Output(["JSON result"])

    subgraph Container["Sandboxed Docker container<br/>(spun up, used once, destroyed)"]
        Tool["The actual OSINT tool"]
    end

    User --> CLI
    CLI --> Mock
    CLI --> ToolPlugin
    ToolPlugin -- "runs it in isolation,<br/>never touches your machine" --> Tool
    Tool -- "results come back" --> ToolPlugin
    Mock --> Findings
    ToolPlugin --> Findings
    Findings --> Output
```

Any failure inside the container (timeout, docker missing, bad output) is
caught by the plugin and turned into a `Finding(status=ERROR)` — it never
propagates as an exception.

## Core design

- **`Status` is tri-state, not a boolean.** `FOUND` / `NOT_FOUND` / `ERROR`.
  `NOT_FOUND` means "checked, doesn't exist." `ERROR` means "could not check"
  (timeout, rate-limit, crash). Never conflate the two — an `ERROR` reported
  as `NOT_FOUND` is a false negative.
- **`Plugin` is a `Protocol`**, not a base class: `name`, `supported_entities`,
  and `async def run(entity: str) -> list[Finding]`. Any object with that
  shape works as a plugin, no inheritance required.
- **Every plugin must catch its own failures.** `run()` should never raise —
  timeouts, missing binaries, bad output, etc. must come back as a
  `Finding(status=ERROR)` so one broken plugin can't take down a run.

## Project layout

```
argustrace/
├── core/
│   └── models.py       # Status, Finding
├── plugins/
│   ├── base.py          # Plugin protocol
│   ├── _docker_runner.py  # shared hardened `docker run` helper
│   ├── mock_plugin.py   # hardcoded findings, no I/O — proves the pipeline
│   ├── sherlock_plugin.py  # runs Sherlock in a hardened Docker container
│   ├── holehe_plugin.py    # runs Holehe in a hardened Docker container
│   └── ignorant_plugin.py  # runs Ignorant in a hardened Docker container
└── cli.py                # `investigate` command

docker/
├── holehe/
│   └── Dockerfile        # builds argustrace-holehe (no official image exists)
└── ignorant/
    ├── Dockerfile        # builds argustrace-ignorant (no official image exists)
    └── ignorant_json.py  # thin wrapper: calls ignorant's library directly, prints JSON
```

## Setup

Dependencies are managed with [uv](https://docs.astral.sh/uv/); `uv.lock`
pins exact versions and hashes for every package.

```bash
uv sync
```

Docker Desktop (or another Docker engine) must be running for the
`sherlock`, `sherlock-full`, `holehe`, and `ignorant` plugins.

Sherlock is pulled straight from a pinned registry image. Holehe and
Ignorant have no official image, so each must be built locally once:

```bash
docker build -t argustrace-holehe:1.61 -f docker/holehe/Dockerfile .
docker build -t argustrace-ignorant:1.2 -f docker/ignorant/Dockerfile .
```

## Usage

```bash
uv run python -m argustrace.cli <entity> --plugin mock             # no network, proves the pipeline
uv run python -m argustrace.cli <username> --plugin sherlock       # curated ~10-site list, a few seconds
uv run python -m argustrace.cli <username> --plugin sherlock-full  # full ~400+ site scan, 1-3 minutes
uv run python -m argustrace.cli <email> --plugin holehe             # ~120 sites, ~10 seconds
uv run python -m argustrace.cli <phone> --plugin ignorant            # 3 sites, E164 format e.g. +33612345678
```

Output is a JSON array of `Finding` objects.

## The Sherlock plugin

[Sherlock](https://github.com/sherlock-project/sherlock) never runs on the
host. It's invoked through `docker run` against an image pinned by SHA256
digest, with:

- `--cap-drop=ALL`, `--security-opt=no-new-privileges`
- `--read-only` root filesystem (only the output volume is writable)
- Memory, CPU, and PID limits

Sherlock's own per-site result is mapped onto our `Status`:

| Sherlock status  | `Status`                                                     |
| ---------------- | ------------------------------------------------------------ |
| `Claimed`        | `FOUND`                                                      |
| `Available`      | `NOT_FOUND`                                                  |
| `Unknown`, `WAF` | `ERROR`                                                      |
| `Illegal`        | dropped (username invalid for that site — no check happened) |

## The Holehe plugin

[Holehe](https://github.com/megadose/holehe) checks whether an email is
registered on ~120 sites via their "forgot password" flow. Same isolation
as Sherlock (`--cap-drop=ALL`, `--read-only`, `--security-opt=no-new-privileges`,
resource limits), but built from a local Dockerfile pinned to a specific
`pip` version and base image digest, since no official image exists.

Holehe's own per-site result is mapped onto our `Status`:

| Holehe result                | `Status`    |
| ----------------------------- | ----------- |
| `rateLimit: True`             | `ERROR`     |
| `exists: True`                | `FOUND`     |
| `exists: False`, no rate limit | `NOT_FOUND` |

Note: Holehe's own code treats *any* exception raised while checking a site
(network error, parsing failure, actual rate limiting, ...) as `rateLimit:
True` — it's a catch-all, not a precise signal, which is exactly why our
`ERROR` status exists as a separate bucket from `NOT_FOUND`.

The plugin deliberately never passes `--timeout` to Holehe: in v1.61,
argparse stores an explicit value as a string instead of an int, which
makes every single module raise immediately. Omitting the flag keeps the
(int) default and avoids the bug entirely.

## The Ignorant plugin

[Ignorant](https://github.com/megadose/ignorant) checks whether a phone
number is registered on Amazon, Instagram, and Snapchat — same author and
design as Holehe, same isolation model, also built from a local Dockerfile
(no official image exists).

Ignorant's CLI has no CSV/JSON export, so the image bakes in a small
wrapper ([`ignorant_json.py`](docker/ignorant/ignorant_json.py)) that
calls the library's own scan functions directly and prints JSON — more
reliable than parsing colored terminal output. Same status mapping as
Holehe: `rateLimit: true` → `ERROR`, `exists: true` → `FOUND`, otherwise
`NOT_FOUND`.

Entities are parsed with the [`phonenumbers`](https://pypi.org/project/phonenumbers/)
library (Google's libphonenumber) rather than a hand-rolled regex —
splitting a raw number like `+33612345678` into country code (`33`) and
national number (`612345678`) isn't reliably doable with pattern matching,
since country codes vary from 1 to 3 digits with no delimiter in the string.

**Why not PhoneInfoga?** It was the first candidate, but its free (no
API key) scanners don't actually check anything — the "OSINT" scanner
just generates Google search URLs (e.g. `site:instagram.com intext:"+1..."`)
for a human to open and read themselves, and the "local" scanner only
validates formatting/carrier, with no found/not-found signal at all.
Forcing that into `FOUND`/`NOT_FOUND` would misrepresent what was actually
verified, which is exactly what the tri-state `Status` exists to prevent.

## Testing

```bash
uv run pytest -v
```

Tests lock the `Status`/`Finding`/`Plugin` contracts using `MockPlugin`, plus
the entity validation and result-to-`Status` mapping logic of the Sherlock,
Holehe, and Ignorant plugins against fixture data — none of it needs Docker
or network access. Actually running these tools against real targets is
exercised manually, not in the automated suite.
