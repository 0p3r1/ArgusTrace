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
    User(["You: \"check this username\""])
    CLI["ArgusTrace CLI"]
    Mock["Mock plugin<br/>(demo, no real check)"]
    SherlockPlugin["Sherlock plugin"]
    Findings["Findings:<br/>found / not found / error"]
    Output(["JSON result"])

    subgraph Container["Sandboxed Docker container<br/>(spun up, used once, destroyed)"]
        Sherlock["Sherlock<br/>(the actual OSINT tool)"]
    end

    User --> CLI
    CLI --> Mock
    CLI --> SherlockPlugin
    SherlockPlugin -- "runs it in isolation,<br/>never touches your machine" --> Sherlock
    Sherlock -- "results come back" --> SherlockPlugin
    Mock --> Findings
    SherlockPlugin --> Findings
    Findings --> Output
```

Any failure inside the container (timeout, docker missing, bad output) is
caught by `SherlockPlugin` and turned into a `Finding(status=ERROR)` — it
never propagates as an exception.

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
│   ├── mock_plugin.py   # hardcoded findings, no I/O — proves the pipeline
│   └── sherlock_plugin.py  # runs Sherlock in a hardened Docker container
└── cli.py                # `investigate` command
```

## Setup

Dependencies are managed with [uv](https://docs.astral.sh/uv/); `uv.lock`
pins exact versions and hashes for every package.

```bash
uv sync
```

Docker Desktop (or another Docker engine) must be running for the `sherlock`
and `sherlock-full` plugins.

## Usage

```bash
uv run python -m argustrace.cli <entity> --plugin mock           # no network, proves the pipeline
uv run python -m argustrace.cli <username> --plugin sherlock       # curated ~10-site list, a few seconds
uv run python -m argustrace.cli <username> --plugin sherlock-full  # full ~400+ site scan, 1-3 minutes
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

## Testing

```bash
uv run pytest -v
```

Tests lock the `Status`/`Finding`/`Plugin` contracts using `MockPlugin` —
no Docker or network access required. The Sherlock plugin is exercised
manually against real targets, not in the automated suite.
